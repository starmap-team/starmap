"""Celery task entrypoints for extraction, graph building, evolution analysis, and pipeline stages."""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Celery
from loguru import logger

from app.config import settings
from app.core.pipeline.orchestrator import StageName
from app.tasks.stage3_services import (
    run_analyze_evolution_trends,
    run_batch_extract_jd,
    run_build_graph_from_extractions,
)
from app.utils.async_helpers import run_async

celery_app = Celery(
    "starmap",
    broker=settings.redis_uri,
    backend=settings.redis_uri,
)
celery_app.conf.update(
    task_default_queue="starmap",
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_time_limit=settings.pipeline_stage_timeout,
    task_soft_time_limit=settings.pipeline_stage_timeout - 30,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def batch_extract_jd(self, jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Batch-extract skills from a JD via Celery."""
    try:
        logger.info("batch_extract_jd started chars={}", len(jd_text))
        return run_async(run_batch_extract_jd(jd_text, options=options))
    except Exception as exc:
        logger.exception("batch_extract_jd failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, Any]:
    """Build Neo4j graph triples from persisted extraction records."""
    try:
        logger.info("build_graph_from_extractions started limit={}", limit)
        return run_async(run_build_graph_from_extractions(limit))
    except Exception as exc:
        logger.exception("build_graph_from_extractions failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, Any]:
    """Analyze skill and position evolution from recent extraction records."""
    try:
        logger.info("analyze_evolution_trends started days={}", days)
        return run_async(run_analyze_evolution_trends(days))
    except Exception as exc:
        logger.exception("analyze_evolution_trends failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    max_retries=settings.pipeline_retry_max,
    default_retry_delay=settings.pipeline_retry_backoff,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_pipeline_stage(self, run_id: str, stage_name: str) -> dict[str, Any]:
    """Execute a single pipeline stage and advance the DAG.

    On success: marks stage completed, then calls advance_pipeline to dispatch next stages.
    On failure: retries with backoff; after max retries, marks stage failed and advances.

    Phase 1 D-04: STOP flag 检查 — if Redis flag `pipeline:stop:{run_id}` is set,
    raise PipelineCancelled to gracefully skip this stage (no retry).
    """
    from app.core.pipeline.executor import STAGE_EXECUTORS, advance_pipeline

    # Phase 1 D-04: Check STOP flag at the START of each stage execution
    try:
        from app.core.pipeline.orchestrator import is_run_cancelled
        from app.services.resources import resources as app_resources
        redis_client = app_resources.redis_client
        if run_async(is_run_cancelled(redis_client, uuid.UUID(run_id))):
            logger.info(
                "execute_pipeline_stage run_id={} stage={}: STOP flag detected, marking cancelled",
                run_id, stage_name,
            )
            run_async(_mark_stage_cancelled(run_id, stage_name))
            return {"status": "cancelled", "stage": stage_name, "reason": "STOP flag set"}
    except Exception as exc:
        logger.warning("STOP flag check failed (continuing): {}", exc)

    logger.info("execute_pipeline_stage run_id={} stage={} attempt={}", run_id, stage_name, self.request.retries)

    executor = STAGE_EXECUTORS.get(stage_name)
    if executor is None:
        logger.error("No executor for stage {}", stage_name)
        run_async(_mark_stage_failed(run_id, stage_name, [f"Unknown stage: {stage_name}"]))
        return {"status": "failed", "error": f"Unknown stage: {stage_name}"}

    start = time.monotonic()
    try:
        # ponytail: only crawl accepts run_type; others take run_id only
        if stage_name == StageName.CRAWL.value:
            result = executor(run_id, run_type="full")  # type: ignore[operator]
        else:
            result = executor(run_id)  # type: ignore[operator]
        duration_ms = int((time.monotonic() - start) * 1000)

        # Update stage status
        run_async(_mark_stage_completed(
            run_id, stage_name,
            duration_ms=duration_ms,
            records_processed=result.get("records_processed", 0),
            errors=result.get("errors", []),
        ))

        # Advance DAG — dispatch next ready stages
        run_async(advance_pipeline(uuid.UUID(run_id)))

        return {"status": "completed", "stage": stage_name, **result}

    except Exception as exc:
        logger.exception("Stage {} failed for run {}: {}", stage_name, run_id, exc)
        # Retry with backoff
        retry_delay = settings.pipeline_retry_backoff * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay) from exc


async def _mark_stage_cancelled(run_id: str, stage_name: str) -> None:
    """Mark a stage as cancelled in the pipeline_runs.stages JSONB (Phase 1 D-04)."""
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.core.pipeline.orchestrator import StageStatus
    from app.models.pipeline_models import PipelineRun
    from app.services.resources import resources as app_resources

    pg_engine = app_resources.pg_engine
    if pg_engine is None:
        return
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(pg_engine) as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
        )
        run = result.scalar_one_or_none()
        if run is None or not run.stages:
            return
        for stage in run.stages:
            if stage.get("name") == stage_name and stage.get("status") in (
                StageStatus.RUNNING.value,
                StageStatus.PENDING.value,
            ):
                stage["status"] = "cancelled"
                stage["completed_at"] = datetime.now(UTC).isoformat()
                flag_modified(run, "stages")
                break
        await session.commit()


@celery_app.task
def advance_pipeline_task(run_id: str) -> None:
    """Async advance_pipeline wrapper for Celery dispatch."""
    import uuid

    from app.core.pipeline.executor import advance_pipeline
    run_async(advance_pipeline(uuid.UUID(run_id)))


@celery_app.task
def scheduled_pipeline_run(schedule_id: str) -> None:
    """Phase 2 CRON-04: 读取 schedule 并触发 pipeline。"""
    run_async(_execute_scheduled_run(schedule_id))


async def _execute_scheduled_run(schedule_id: str) -> None:
    """读取 schedule → trigger → 更新 last/next_run_at。"""
    from datetime import timedelta

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_session_factory
    from app.models.pipeline_models import PipelineSchedule

    sm = get_session_factory()
    async with sm() as session:
        result = await session.execute(
            select(PipelineSchedule).where(PipelineSchedule.id == uuid.UUID(schedule_id))
        )
        schedule = result.scalar_one_or_none()
        if schedule is None:
            logger.warning("Schedule {} not found", schedule_id)
            return

        from app.core.pipeline.executor import trigger_and_start
        await trigger_and_start(run_type=schedule.run_type, selected_stages=schedule.selected_stages)

        schedule.last_run_at = datetime.now(UTC)
        try:
            from app.core.pipeline.cron_scheduler import compute_next_cron
            schedule.next_run_at = compute_next_cron(schedule.cron_expression, schedule.last_run_at)
        except Exception:
            schedule.next_run_at = schedule.last_run_at + timedelta(hours=1)
        await session.commit()


@celery_app.task(bind=True, max_retries=0)
def sweep_orphan_runs(self) -> dict[str, Any]:
    """Phase 2 WATCHDOG: 清理超过 stage_timeout*2 仍 running 的任务。"""
    run_async(_sweep_orphan_runs_async())
    return {"status": "completed"}


async def _sweep_orphan_runs_async() -> dict[str, Any]:
    from datetime import timedelta

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.pipeline.orchestrator import RunStatus
    from app.db.session import get_session_factory
    from app.models.pipeline_models import PipelineRun

    sm = get_session_factory()
    async with sm() as session:
        threshold = datetime.now(UTC) - timedelta(seconds=settings.pipeline_stage_timeout * 2)
        result = await session.execute(
            select(PipelineRun)
            .where(PipelineRun.status == RunStatus.RUNNING.value)
            .where(PipelineRun.started_at < threshold)
        )
        orphans = list(result.scalars().all())
        for run in orphans:
            run.status = RunStatus.FAILED.value
            run.completed_at = datetime.now(UTC)
            run.error_log = "orphaned by watchdog"
            logger.warning("Watchdog: orphaned run {} (started={})", run.id, run.started_at)
        await session.commit()
        return {"orphans_found": len(orphans)}


# ── Helpers ──
async def _mark_stage_completed(
    run_id: str, stage_name: str,
    *, duration_ms: int = 0, records_processed: int = 0, errors: list[str] | None = None,
) -> None:
    from app.core.pipeline.orchestrator import update_stage_status
    from app.db.session import get_session_factory
    sm = get_session_factory()
    async with sm() as session:
        async with session.begin():
            await update_stage_status(
                session, uuid.UUID(run_id), stage_name,
                status="completed",
                duration_ms=duration_ms,
                records_processed=records_processed,
                errors=errors,
            )


async def _mark_stage_failed(
    run_id: str, stage_name: str, errors: list[str],
) -> None:
    from app.core.pipeline.orchestrator import update_stage_status
    from app.db.session import get_session_factory
    sm = get_session_factory()
    async with sm() as session:
        async with session.begin():
            await update_stage_status(
                session, uuid.UUID(run_id), stage_name,
                status="failed",
                errors=errors,
            )


# ── Beat schedule (LOOP-06: 定时演化分析) ──

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "evolution-analyze": {
        "task": "app.tasks.celery_app.analyze_evolution_trends",
        "schedule": crontab(hour="*/6", minute=0),  # 每6小时
        "kwargs": {"days": 90},
    },
}
