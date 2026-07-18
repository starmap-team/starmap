"""ETL pipeline orchestrator with DAG execution.

Manages the full data pipeline lifecycle:
  crawl → (dedup ∥ clean) → import → graph_sync

DAG dependencies:
  - crawl: no deps (root)
  - dedup: depends on crawl
  - clean: depends on crawl
  - import: depends on dedup + clean
  - graph_sync: depends on import

Each stage tracks status, duration, records processed, retry count, and errors.
Actual execution is dispatched to Celery tasks; this module handles state tracking
and DAG scheduling logic.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.exceptions import RunAlreadyTerminalError, RunNotFoundError
from app.models.pipeline_models import DataSourceRecord, PipelineRun

# ── Domain exceptions (imported from app.exceptions for global handler mapping) ──


class StageName(StrEnum):
    CRAWL = "crawl"
    DEDUP = "dedup"
    CLEAN = "clean"
    IMPORT = "import"
    GRAPH_SYNC = "graph_sync"
    TIMESERIES = "timeseries"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALL_STAGES = list(StageName)

# DAG: stage -> list of stages it depends on
STAGE_DEPS: dict[str, list[str]] = {
    StageName.CRAWL.value: [],
    StageName.DEDUP.value: [StageName.CRAWL.value],
    StageName.CLEAN.value: [StageName.CRAWL.value],
    StageName.IMPORT.value: [StageName.DEDUP.value, StageName.CLEAN.value],
    StageName.GRAPH_SYNC.value: [StageName.IMPORT.value],
    StageName.TIMESERIES.value: [StageName.GRAPH_SYNC.value],
}

# Stages that can be skipped without blocking downstream
OPTIONAL_STAGES = frozenset({StageName.GRAPH_SYNC.value, StageName.TIMESERIES.value})


def _now() -> datetime:
    return datetime.now(UTC)


def _build_initial_stages(selected: list[str] | None = None) -> list[dict[str, Any]]:
    """Return a fresh stages list for a new pipeline run.

    If *selected* is provided, only those stages are PENDING; others are SKIPPED.
    """
    selected_set = set(selected) if selected else {s.value for s in ALL_STAGES}
    return [
        {
            "name": stage.value,
            "status": StageStatus.SKIPPED.value if stage.value not in selected_set else StageStatus.PENDING.value,
            "started_at": None,
            "completed_at": None,
            "duration_ms": 0,
            "records_processed": 0,
            "errors": [],
            "retry_count": 0,
            "depends_on": STAGE_DEPS.get(stage.value, []),
        }
        for stage in ALL_STAGES
    ]


def _stage_index(stages: list[dict], stage_name: str) -> int:
    for i, s in enumerate(stages):
        if s["name"] == stage_name:
            return i
    raise ValueError(f"Stage '{stage_name}' not found in stages list")


def get_ready_stages(stages: list[dict]) -> list[str]:
    """Return stage names that are PENDING and whose deps are all COMPLETED/SKIPPED."""
    status_map = {s["name"]: s["status"] for s in stages}
    ready = []
    for s in stages:
        if s["status"] != StageStatus.PENDING.value:
            continue
        deps = STAGE_DEPS.get(s["name"], [])
        if all(status_map.get(d) in (StageStatus.COMPLETED.value, StageStatus.SKIPPED.value) for d in deps):
            ready.append(s["name"])
    return ready


def get_failed_stages(stages: list[dict]) -> list[str]:
    """Return stage names that are FAILED."""
    return [s["name"] for s in stages if s["status"] == StageStatus.FAILED.value]


def all_stages_done(stages: list[dict]) -> bool:
    """True when no stage is PENDING or RUNNING."""
    return all(s["status"] in (StageStatus.COMPLETED.value, StageStatus.FAILED.value, StageStatus.SKIPPED.value) for s in stages)


async def create_run(
    session: AsyncSession,
    *,
    run_type: str = "full",
    selected_stages: list[str] | None = None,
) -> PipelineRun:
    """Create a new PipelineRun record with DAG-aware stage initialization."""
    # Validate run_type
    _VALID_RUN_TYPES = {"full", "incremental"}  # noqa: N806
    if run_type not in _VALID_RUN_TYPES:
        raise ValueError(f"Invalid run_type: {run_type!r}. Must be one of {sorted(_VALID_RUN_TYPES)}")
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=run_type,
        status=RunStatus.RUNNING.value,
        started_at=_now(),
        completed_at=None,
        stages=_build_initial_stages(selected_stages),
        total_records=0,
        new_records=0,
        updated_records=0,
        quality_score=0.0,
        error_log=None,
        selected_stages=selected_stages,
    )
    session.add(run)
    await session.flush()
    return run


async def update_stage_status(
    session: AsyncSession,
    run_id: uuid.UUID,
    stage_name: str,
    *,
    status: str,
    duration_ms: int = 0,
    records_processed: int = 0,
    errors: list[str] | None = None,
    retry_count: int | None = None,
) -> PipelineRun | None:
    """Update a single stage inside a pipeline run's stages JSON array."""
    result = await session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    stages: list[dict] = list(run.stages or [])
    idx = _stage_index(stages, stage_name)
    stage = stages[idx]
    stage["status"] = status
    if status == StageStatus.RUNNING.value:
        stage["started_at"] = _now().isoformat()
    if status in (StageStatus.COMPLETED.value, StageStatus.FAILED.value):
        stage["completed_at"] = _now().isoformat()
    stage["duration_ms"] = duration_ms
    stage["records_processed"] = records_processed
    if errors:
        stage["errors"] = errors
    if retry_count is not None:
        stage["retry_count"] = retry_count

    await session.execute(
        update(PipelineRun).where(PipelineRun.id == run_id).values(stages=stages)
    )
    await session.flush()

    result = await session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    )
    return result.scalar_one_or_none()


async def complete_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    status: str = RunStatus.COMPLETED.value,
    total_records: int = 0,
    new_records: int = 0,
    updated_records: int = 0,
    quality_score: float = 0.0,
    error_log: str | None = None,
) -> PipelineRun | None:
    """Mark a pipeline run as completed (or failed).

    Phase 2 AUTHORITY-01: Run completion triggers authority score update
    and auto-pauses sources with quality < 0.3.
    """
    await session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == run_id)
        .values(
            status=status,
            completed_at=_now(),
            total_records=total_records,
            new_records=new_records,
            updated_records=updated_records,
            quality_score=quality_score,
            error_log=error_log,
        )
    )
    await session.flush()

    # Phase 2 AUTHORITY-01: 更新所有数据源权威分
    try:
        from app.core.pipeline.source_authority import update_authority_scores
        await update_authority_scores(session)
    except Exception as exc:
        logger.warning(f"update_authority_scores failed (non-fatal): {exc}")

    # Phase 2 AUTHORITY-02: quality < 0.3 的数据源标记 paused
    try:
        from sqlalchemy import select as sa_select
        ds_result = await session.execute(
            sa_select(DataSourceRecord)
            .where(DataSourceRecord.authority_score < 0.3)
            .where(DataSourceRecord.status == "active")
        )
        low_quality_sources = ds_result.scalars().all()
        for ds in low_quality_sources:
            ds.status = "paused"
            logger.warning("Auto-paused source '{}' (authority_score={})", ds.name, ds.authority_score)
        if low_quality_sources:
            await session.flush()
    except Exception as exc:
        logger.warning(f"auto-pause failed (non-fatal): {exc}")

    result = await session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    )
    return result.scalar_one_or_none()


async def get_status(session: AsyncSession) -> dict[str, Any]:
    """Return global pipeline status overview."""
    running_result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.status == RunStatus.RUNNING.value)
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )
    running_run = running_result.scalar_one_or_none()

    last_result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.status == RunStatus.COMPLETED.value)
        .order_by(PipelineRun.completed_at.desc())
        .limit(1)
    )
    last_run = last_result.scalar_one_or_none()

    # Recent failed run (for resume/retry button — only if nothing currently running)
    failed_result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.status == RunStatus.FAILED.value)
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )
    failed_run = failed_result.scalar_one_or_none() if running_run is None else None

    counts_result = await session.execute(
        select(PipelineRun.status, func.count()).group_by(PipelineRun.status)
    )
    run_counts = {row[0]: row[1] for row in counts_result.all()}

    ds_count_result = await session.execute(
        select(func.count())
        .select_from(DataSourceRecord)
        .where(DataSourceRecord.status == "active")
    )
    active_sources = ds_count_result.scalar() or 0

    return {
        "is_running": running_run is not None,
        "current_run": _serialize_run(running_run) if running_run else None,
        "last_run": _serialize_run(last_run) if last_run else None,
        "recent_failed_run": _serialize_run(failed_run) if failed_run else None,
        "run_counts": run_counts,
        "active_data_sources": active_sources,
    }


def _normalize_stages(stages: Any) -> list[dict[str, Any]]:
    """Normalize pipeline stages to a list of StageInfo-compatible dicts.

    Pipeline runs store stages as list[dict] (each dict has name/status/duration/etc).
    Loop runs store stages as a single dict with result metadata (no 'name' field).
    Handle both by wrapping dicts and returning empty list for unknown shapes.
    """
    if stages is None:
        return []
    if isinstance(stages, list):
        # Pipeline run: list of stage dicts
        return stages
    if isinstance(stages, dict):
        # Loop run: single dict with result metadata — wrap as a single stage
        # Check if it looks like a loop result (no 'name' key or has 'run_id' key)
        if "name" not in stages and "run_id" in stages:
            return []
        return [stages]
    return []


async def get_run_history(
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
) -> list[PipelineRun]:
    """Return paginated pipeline run history, newest first."""
    stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc())
    if status_filter:
        stmt = stmt.where(PipelineRun.status == status_filter)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _serialize_run(run: PipelineRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": str(run.id),
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "stages": _normalize_stages(run.stages),
        "total_records": run.total_records,
        "new_records": run.new_records,
        "updated_records": run.updated_records,
        "quality_score": run.quality_score,
        "error_log": run.error_log,
        "selected_stages": run.selected_stages,
    }


# ---------------------------------------------------------------------------
# Phase 1: Cancel run (D-04: 软取消 + STOP flag + Celery 阶段开始时检查)
# ---------------------------------------------------------------------------

class RunCancelResult:
    """Result of cancel_run for the API layer."""

    def __init__(
        self,
        run_id: uuid.UUID,
        status: str,
        cancelled_at: datetime,
        stopped_stage_names: list[str],
    ):
        self.run_id = run_id
        self.status = status
        self.cancelled_at = cancelled_at
        self.stopped_stage_names = stopped_stage_names


async def cancel_run(
    session: AsyncSession,
    redis_client: Any | None,
    run_id: uuid.UUID,
) -> RunCancelResult:
    """Cancel a running pipeline (D-04).

    Steps in a single transaction:
    1. UPDATE pipeline_runs SET status='cancelled', completed_at=now(), error_log='cancelled by user'
    2. UPDATE stages[] 中所有 status='running' -> 'cancelled'
    3. Redis SET pipeline:stop:{run_id} = '1' (TTL 1 hour)
    4. Invalidate status cache

    Raises:
        RunNotFoundError if run not found
        RunAlreadyTerminalError if run already in terminal state
    """
    result = await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(f"Pipeline run {run_id} not found")

    terminal_states = {
        RunStatus.COMPLETED.value,
        RunStatus.FAILED.value,
        "cancelled",
    }
    if run.status in terminal_states:
        raise RunAlreadyTerminalError(f"Run already in terminal state: {run.status}")

    cancelled_at = _now()

    # 1. UPDATE pipeline_runs
    run.status = "cancelled"
    run.completed_at = cancelled_at
    run.error_log = "cancelled by user"

    # 2. UPDATE stages[] - 将所有 status='running' 的 stage 标记为 'cancelled'
    stopped_stage_names: list[str] = []
    if run.stages:
        for stage in run.stages:
            if stage.get("status") == StageStatus.RUNNING.value:
                stage["status"] = "cancelled"
                stage["completed_at"] = cancelled_at.isoformat()
                stopped_stage_names.append(stage.get("name", "unknown"))
        # SQLAlchemy 需要标记 JSONB 字段变更
        flag_modified(run, "stages")

    await session.commit()

    # 3. Redis STOP flag (best-effort, 不影响 cancel 本身)
    if redis_client is not None:
        try:
            await redis_client.setex(f"pipeline:stop:{run_id}", 3600, "1")
        except Exception as exc:
            logger.debug("Redis STOP flag set failed (non-fatal): {}", exc)

        # 4. Invalidate status cache
        try:
            from app.core.pipeline.status_aggregator import invalidate_status_cache
            await invalidate_status_cache(redis_client)
        except Exception as exc:
            logger.debug("Status cache invalidation failed (non-fatal): {}", exc)

    return RunCancelResult(
        run_id=run.id,
        status=run.status,
        cancelled_at=cancelled_at,
        stopped_stage_names=stopped_stage_names,
    )


async def is_run_cancelled(redis_client: Any | None, run_id: uuid.UUID) -> bool:
    """Check Redis STOP flag. Returns True if run was cancelled."""
    if redis_client is None:
        return False
    try:
        flag = await redis_client.get(f"pipeline:stop:{run_id}")
        return flag == b"1" or flag == "1"
    except Exception:
        return False
