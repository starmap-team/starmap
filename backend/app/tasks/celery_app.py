"""Celery task entrypoints for extraction, graph building, evolution analysis, and pipeline stages."""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from celery import Celery

from app.config import settings
from app.tasks.stage3_services import (
    run_analyze_evolution_trends,
    run_async,
    run_batch_extract_jd,
    run_build_graph_from_extractions,
)

logger = logging.getLogger(__name__)

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
        logger.info("batch_extract_jd started chars=%d", len(jd_text))
        return run_async(run_batch_extract_jd(jd_text, options=options))
    except Exception as exc:
        logger.exception("batch_extract_jd failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, Any]:
    """Build Neo4j graph triples from persisted extraction records."""
    try:
        logger.info("build_graph_from_extractions started limit=%d", limit)
        return run_async(run_build_graph_from_extractions(limit))
    except Exception as exc:
        logger.exception("build_graph_from_extractions failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, Any]:
    """Analyze skill and position evolution from recent extraction records."""
    try:
        logger.info("analyze_evolution_trends started days=%d", days)
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
    """
    from app.core.pipeline.executor import STAGE_EXECUTORS, advance_pipeline
    from app.core.pipeline.orchestrator import StageStatus

    logger.info("execute_pipeline_stage run_id=%s stage=%s attempt=%d", run_id, stage_name, self.request.retries)

    executor = STAGE_EXECUTORS.get(stage_name)
    if executor is None:
        logger.error("No executor for stage %s", stage_name)
        _run_async(_mark_stage_failed(run_id, stage_name, [f"Unknown stage: {stage_name}"]))
        return {"status": "failed", "error": f"Unknown stage: {stage_name}"}

    start = time.monotonic()
    try:
        result = executor(run_id, run_type="full")
        duration_ms = int((time.monotonic() - start) * 1000)

        # Update stage status
        _run_async(_mark_stage_completed(
            run_id, stage_name,
            duration_ms=duration_ms,
            records_processed=result.get("records_processed", 0),
            errors=result.get("errors", []),
        ))

        # Advance DAG — dispatch next ready stages
        import uuid
        _run_async(advance_pipeline(uuid.UUID(run_id)))

        return {"status": "completed", "stage": stage_name, **result}

    except Exception as exc:
        logger.exception("Stage %s failed for run %s: %s", stage_name, run_id, exc)
        # Retry with backoff
        retry_delay = settings.pipeline_retry_backoff * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay) from exc


@celery_app.task
def advance_pipeline_task(run_id: str) -> None:
    """Async advance_pipeline wrapper for Celery dispatch."""
    import uuid
    from app.core.pipeline.executor import advance_pipeline
    _run_async(advance_pipeline(uuid.UUID(run_id)))


@celery_app.task
def scheduled_pipeline_run(schedule_id: str) -> None:
    """Trigger a pipeline run from a cron schedule."""
    import uuid
    from app.core.pipeline.executor import trigger_and_start

    # ponytail: load schedule config from DB, run with those params
    _run_async(trigger_and_start(run_type="incremental"))


# ── Helpers ──

def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a Celery worker."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


async def _mark_stage_completed(
    run_id: str, stage_name: str,
    *, duration_ms: int = 0, records_processed: int = 0, errors: list[str] | None = None,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.pipeline.orchestrator import update_stage_status
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            async with session.begin():
                await update_stage_status(
                    session, uuid.UUID(run_id), stage_name,
                    status="completed",
                    duration_ms=duration_ms,
                    records_processed=records_processed,
                    errors=errors,
                )
    finally:
        await engine.dispose()


async def _mark_stage_failed(
    run_id: str, stage_name: str, errors: list[str],
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.pipeline.orchestrator import update_stage_status
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            async with session.begin():
                await update_stage_status(
                    session, uuid.UUID(run_id), stage_name,
                    status="failed",
                    errors=errors,
                )
    finally:
        await engine.dispose()
