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
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.exceptions import RunAlreadyTerminalError, RunNotFoundError, StarMapError
from app.models.pipeline_models import DataSourceRecord, PipelineRun

# ── Domain exceptions (imported from app.exceptions for global handler mapping) ──

# Module-level constants
ZOMBIE_THRESHOLD = timedelta(minutes=30)

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
 StageName.CLEAN.value: [StageName.DEDUP.value], # 串行，等 dedup 标记 duplicate 后再清洗
 StageName.IMPORT.value: [StageName.CLEAN.value], # 串行，等 clean 完成（clean 已隐含 dedup 完成）
 StageName.GRAPH_SYNC.value: [StageName.IMPORT.value],
 StageName.TIMESERIES.value: [StageName.GRAPH_SYNC.value],
}

# Stages that can be skipped without blocking downstream
OPTIONAL_STAGES = frozenset({StageName.GRAPH_SYNC.value, StageName.TIMESERIES.value})

def _now -> datetime:
 return datetime.now(UTC)

def _build_initial_stages(selected: list[str] | None = None) -> list[dict[str, Any]]:
 """Return a fresh stages list for a new pipeline run.

 If *selected* is provided, only those stages are PENDING; others are SKIPPED.
 Phase 3.7: 初始化 current_activity/recent_samples/sub_breakdown 字段
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
 "warnings": [], # 非致命提示（如 crawl 0 条入库），不触发 failed
 "retry_count": 0,
 "error_type": "", # classify failures for observability
 "depends_on": STAGE_DEPS.get(stage.value, []),
 # : 实时活动字段
 "current_activity": "",
 "recent_samples": [],
 "sub_breakdown": {},
 "elapsed_ms": 0,
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
 selected_sources: list[str] | None = None,
) -> PipelineRun:
 """Create a new PipelineRun record with DAG-aware stage initialization."""
 # Validate run_type
 _VALID_RUN_TYPES = {"full", "incremental"} # noqa: N806
 if run_type not in _VALID_RUN_TYPES:
 raise ValueError(f"Invalid run_type: {run_type!r}. Must be one of {sorted(_VALID_RUN_TYPES)}")
 run = PipelineRun(
 id=uuid.uuid4,
 run_type=run_type,
 status=RunStatus.RUNNING.value,
 started_at=_now,
 completed_at=None,
 stages=_build_initial_stages(selected_stages),
 total_records=0,
 new_records=0,
 updated_records=0,
 quality_score=0.0,
 error_log=None,
 selected_stages=selected_stages,
 selected_sources=selected_sources,
 )
 session.add(run)
 await session.flush
 return run

async def update_stage_status(
 session: AsyncSession,
 run_id: uuid.UUID,
 stage_name: str,
 *,
 status: str,
 duration_ms: int = 0,
 records_processed: int = 0,
 records_seen: int = 0, 
 records_new: int | None = None, # crawl 真正新增行
 records_duplicate: int | None = None, # crawl 重复行
 errors: list[str] | None = None,
 warnings: list[str] | None = None, # 非致命警告（0 条采集等），仅提示不判失败
 retry_count: int | None = None,
 error_type: str = "", # failure classification
 current_activity: str = "",
 recent_samples: list[dict] | None = None,
 sub_breakdown: dict[str, int] | None = None,
 elapsed_ms: int = 0,
 progress: float | None = None,
) -> PipelineRun | None:
 """Update a single stage inside a pipeline run's stages JSON array.

 增加 current_activity/recent_samples/sub_breakdown 字段，
 让前端刷新页面后还能看到每个 stage 的最近活动/样本/分解数据。
 """
 result = await session.execute(
 select(PipelineRun).where(PipelineRun.id == run_id)
 )
 run = result.scalar_one_or_none
 if run is None:
 return None

 stages: list[dict] = list(run.stages or [])
 idx = _stage_index(stages, stage_name)
 stage = stages[idx]
 stage["status"] = status
 if status == StageStatus.RUNNING.value:
 stage["started_at"] = _now.isoformat
 if status in (StageStatus.COMPLETED.value, StageStatus.FAILED.value):
 stage["completed_at"] = _now.isoformat
 # : stage 完成/失败时强制 progress=1.0 (避免显示 0%)
 if status == StageStatus.COMPLETED.value and progress is None:
 stage["progress"] = 1.0
 elif progress is not None:
 stage["progress"] = progress
 stage["duration_ms"] = duration_ms
 stage["records_processed"] = records_processed
 if records_seen:
 stage["records_seen"] = records_seen : 抓到 vs 入库区分
 if records_new is not None:
 stage["records_new"] = records_new
 if records_duplicate is not None:
 stage["records_duplicate"] = records_duplicate
 if errors:
 stage["errors"] = errors
 if warnings is not None:
 stage["warnings"] = warnings
 if retry_count is not None:
 stage["retry_count"] = retry_count
 if error_type:
 stage["error_type"] = error_type
 # : 实时活动上下文持久化
 if current_activity:
 stage["current_activity"] = current_activity
 if recent_samples is not None:
 stage["recent_samples"] = list(recent_samples)[-10:]
 if sub_breakdown is not None:
 stage["sub_breakdown"] = sub_breakdown
 if elapsed_ms:
 stage["elapsed_ms"] = elapsed_ms

 await session.execute(
 update(PipelineRun).where(PipelineRun.id == run_id).values(stages=stages)
 )
 await session.flush

 result = await session.execute(
 select(PipelineRun).where(PipelineRun.id == run_id)
 )
 return result.scalar_one_or_none

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

 Run completion triggers authority score update
 and auto-pauses sources with quality < 0.3.
 """
 await session.execute(
 update(PipelineRun)
 .where(PipelineRun.id == run_id)
 .values(
 status=status,
 completed_at=_now,
 total_records=total_records,
 new_records=new_records,
 updated_records=updated_records,
 quality_score=quality_score,
 error_log=error_log,
 )
 )
 await session.flush

 # : 更新所有数据源权威分
 try:
 from app.core.pipeline.source_authority import update_authority_scores
 await update_authority_scores(session)
 except StarMapError:
 raise
 except Exception:
 logger.exception("update_authority_scores failed (non-fatal)")

 # : quality < 0.3 的数据源标记 paused
 try:
 from sqlalchemy import select as sa_select
 ds_result = await session.execute(
 sa_select(DataSourceRecord)
 .where(DataSourceRecord.authority_score < 0.3)
 .where(DataSourceRecord.status == "active")
 )
 low_quality_sources = ds_result.scalars.all
 for ds in low_quality_sources:
 ds.status = "paused"
 logger.warning("Auto-paused source '{}' (authority_score={})", ds.name, ds.authority_score)
 if low_quality_sources:
 await session.flush
 except StarMapError:
 raise
 except Exception:
 logger.exception("auto-pause failed (non-fatal)")

 result = await session.execute(
 select(PipelineRun).where(PipelineRun.id == run_id)
 )
 return result.scalar_one_or_none

async def get_status(session: AsyncSession) -> dict[str, Any]:
 """Return global pipeline status overview.

 注：自动检测"僵尸"run — 当一条 run 长时间 status=running 但所有 stage
 都已经 completed/cancelled/failed 时，前端不应显示"正在执行"。
 这种情况通常是 Celery worker 重启 / 任务丢失导致的状态卡死。
 """
 running_result = await session.execute(
 select(PipelineRun)
 .where(PipelineRun.status == RunStatus.RUNNING.value)
 .order_by(PipelineRun.started_at.desc)
 .limit(1)
 )
 running_run = running_result.scalar_one_or_none

 # 检测僵尸 run：所有 stage 已结束但 run 还卡在 running > 30 分钟
 if running_run is not None:
 # P0-AUDIT-FIX (2026-08-13): started_at 可能为 naive（DateTime(timezone=True)
 # 规范化前的历史行，或 SQLite 测试库）。aware-now 减 naive 会抛 TypeError。
 # 假定 naive = UTC，统一后比较。
 started_at = running_run.started_at
 if started_at is not None and started_at.tzinfo is None:
 started_at = started_at.replace(tzinfo=UTC)
 age = datetime.now(UTC) - started_at
 stages = running_run.stages or []
 all_done = bool(stages) and all(
 s.get("status") in {"completed", "cancelled", "failed", "skipped"}
 for s in stages
 )
 if age > ZOMBIE_THRESHOLD and (all_done or not stages):
 # 直接修正数据库状态（无需等待用户手动 force-reset）
 running_run.status = RunStatus.CANCELLED.value
 running_run.completed_at = datetime.now(UTC)
 running_run.error_log = (
 f"[system] Auto-cleaned: stuck running for {age.total_seconds / 60:.0f} min, "
 "no active stages. Likely Celery worker restart."
 )
 await session.flush
 logger.warning(
 "Auto-cleaned zombie pipeline run {} (age={:.0f}min)",
 running_run.id, age.total_seconds / 60,
 )
 running_run = None

 last_result = await session.execute(
 select(PipelineRun)
 .where(PipelineRun.status == RunStatus.COMPLETED.value)
 .order_by(PipelineRun.completed_at.desc)
 .limit(1)
 )
 last_run = last_result.scalar_one_or_none

 # Recent failed run (for resume/retry button — only if nothing currently running)
 failed_result = await session.execute(
 select(PipelineRun)
 .where(PipelineRun.status == RunStatus.FAILED.value)
 .order_by(PipelineRun.started_at.desc)
 .limit(1)
 )
 failed_run = failed_result.scalar_one_or_none if running_run is None else None

 counts_result = await session.execute(
 select(PipelineRun.status, func.count).group_by(PipelineRun.status)
 )
 run_counts = {row[0]: row[1] for row in counts_result.all}

 ds_count_result = await session.execute(
 select(func.count)
 .select_from(DataSourceRecord)
 .where(DataSourceRecord.status == "active")
 )
 active_sources = ds_count_result.scalar or 0

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
 stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc)
 if status_filter:
 stmt = stmt.where(PipelineRun.status == status_filter)
 stmt = stmt.offset(offset).limit(limit)
 result = await session.execute(stmt)
 return list(result.scalars.all)

def _serialize_run(run: PipelineRun | None) -> dict[str, Any] | None:
 if run is None:
 return None
 return {
 "id": str(run.id),
 "run_type": run.run_type,
 "status": run.status,
 "started_at": run.started_at.isoformat if run.started_at else None,
 "completed_at": run.completed_at.isoformat if run.completed_at else None,
 "stages": _normalize_stages(run.stages),
 "total_records": run.total_records,
 "new_records": run.new_records,
 "updated_records": run.updated_records,
 "quality_score": run.quality_score,
 "error_log": run.error_log,
 "selected_stages": run.selected_stages,
 }

# ---------------------------------------------------------------------------
# : Cancel run (: 软取消 + STOP flag + Celery 阶段开始时检查)
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
 """Cancel a running pipeline .

 Steps in a single transaction:
 1. UPDATE pipeline_runs SET status='cancelled', completed_at=now, error_log='cancelled by user'
 2. UPDATE stages[] 中所有 status='running' -> 'cancelled'
 3. Redis SET pipeline:stop:{run_id} = '1' (TTL 1 hour)
 4. Invalidate status cache

 Raises:
 RunNotFoundError if run not found
 RunAlreadyTerminalError if run already in terminal state
 """
 result = await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
 run = result.scalar_one_or_none
 if run is None:
 raise RunNotFoundError(f"Pipeline run {run_id} not found")

 terminal_states = {
 RunStatus.COMPLETED.value,
 RunStatus.FAILED.value,
 "cancelled",
 }
 if run.status in terminal_states:
 raise RunAlreadyTerminalError(f"Run already in terminal state: {run.status}")

 cancelled_at = _now

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
 stage["completed_at"] = cancelled_at.isoformat
 stopped_stage_names.append(stage.get("name", "unknown"))
 # SQLAlchemy 需要标记 JSONB 字段变更
 flag_modified(run, "stages")

 await session.commit

 # 3. Redis STOP flag (best-effort, 不影响 cancel 本身)
 if redis_client is not None:
 try:
 await redis_client.setex(f"pipeline:stop:{run_id}", 3600, "1")
 except StarMapError:
 raise
 except Exception:
 logger.exception("Redis STOP flag set failed (non-fatal)")

 # 4. Invalidate status cache
 try:
 from app.core.pipeline.status_aggregator import invalidate_status_cache
 await invalidate_status_cache(redis_client)
 except StarMapError:
 raise
 except Exception:
 logger.exception("Status cache invalidation failed (non-fatal)")

 # 5. FIX: 通过 SSE 广播 cancel 事件，让前端立即响应
 try:
 from app.core.dashboard.sse_broadcaster import publish_event
 await publish_event(redis_client, "pipeline_update", {
 "run_id": str(run.id),
 "stage": "pipeline",
 "status": "cancelled",
 "progress": 1.0,
 "records_processed": 0,
 "message": f"Pipeline cancelled by user (stopped stages: {stopped_stage_names})",
 "cancelled_at": cancelled_at.isoformat,
 })
 except StarMapError:
 raise
 except Exception:
 logger.exception("Cancel SSE broadcast failed (non-fatal)")

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
 except StarMapError:
 raise
 except Exception:
 return False
