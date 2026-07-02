"""Pipeline execution service — bridges DAG orchestrator to Celery tasks.

This module implements the DAG execution loop:
1. Create a PipelineRun via orchestrator
2. Dispatch ready stages to Celery tasks
3. Each Celery task calls back into advance_pipeline on completion
4. advance_pipeline updates stage status and dispatches next ready stages
5. When all stages are done, complete the run

Progress is broadcast via Redis pub/sub for SSE consumption.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.dashboard.sse_broadcaster import publish_event
from app.core.pipeline.orchestrator import (
    OPTIONAL_STAGES,
    STAGE_DEPS,
    RunStatus,
    StageName,
    StageStatus,
    all_stages_done,
    create_run,
    get_failed_stages,
    get_ready_stages,
    update_stage_status,
)
from app.models.pipeline_models import PipelineRun
from app.services.resources import resources as app_resources


# ---------------------------------------------------------------------------
# SSE progress helpers
# ---------------------------------------------------------------------------

async def _publish_stage_progress(
    run_id: str,
    stage_name: str,
    status: str,
    progress: float = 0.0,
    records_processed: int = 0,
    message: str = "",
) -> None:
    """Broadcast a pipeline stage progress event via Redis pub/sub."""
    redis = app_resources.redis_client
    await publish_event(redis, "pipeline_update", {
        "run_id": run_id,
        "stage": stage_name,
        "status": status,
        "progress": progress,
        "records_processed": records_processed,
        "message": message,
    })


# ---------------------------------------------------------------------------
# Stage execution functions (sync, called from Celery workers)
# ---------------------------------------------------------------------------

def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a Celery worker process."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def execute_crawl(run_id: str, run_type: str) -> dict[str, Any]:
    """Execute the crawl stage: run spiders and upsert JDs into jd_raw."""
    from crawler.spiders.boss import run_sync as boss_sync
    from crawler.persistence import dao
    from crawler.persistence.models import JdStatus

    keyword = "python"
    max_count = 50 if run_type == "incremental" else 200
    total_inserted = 0
    errors: list[str] = []

    # ponytail: run one spider (boss) as the default; add more via config later
    try:
        items = boss_sync(keyword=keyword, max_count=max_count)
        for it in items:
            rec = {
                "source_site": it["source_site"],
                "source_url": it["source_url"],
                "raw_html": it["raw_html"],
                "clean_text": it["clean_text"],
                "job_title": it["job_title"],
                "company": it["company"],
                "salary_min": it["salary_min"],
                "salary_max": it["salary_max"],
                "location": it["location"],
                "publish_date": it["publish_date"],
                "content_hash": it["content_hash"],
                "status": JdStatus.raw,
            }
            r = dao.upsert_jd(rec)
            if r == "inserted":
                total_inserted += 1
    except Exception as exc:
        errors.append(f"boss crawl failed: {exc}")
        logger.error("Crawl stage boss failed: {}", exc)

    return {"records_processed": total_inserted, "errors": errors}


def execute_dedup(run_id: str) -> dict[str, Any]:
    """Execute dedup stage: SimHash-based dedup on jd_raw records."""
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus
    from crawler.dedup import simhash, is_near_duplicate

    processed = 0
    duplicates = 0
    errors: list[str] = []

    try:
        with get_jd_raw_session() as s:
            # Find raw JDs that haven't been dedup-checked yet
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            hashes: dict[int, str] = {}  # simhash -> source_url (first seen)

            for jd in raw_jds:
                h = simhash(jd.clean_text or "")
                # Check against existing hashes
                is_dup = any(is_near_duplicate(h, eh) for eh in hashes)
                if is_dup:
                    jd.status = JdStatus.duplicate
                    duplicates += 1
                else:
                    hashes[h] = jd.source_url
                processed += 1
            s.commit()
    except Exception as exc:
        errors.append(f"dedup failed: {exc}")
        logger.error("Dedup stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors, "duplicates_found": duplicates}


def execute_clean(run_id: str) -> dict[str, Any]:
    """Execute clean stage: normalize and validate JD records."""
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus

    processed = 0
    errors: list[str] = []

    try:
        with get_jd_raw_session() as s:
            # Clean raw JDs that passed dedup (status=raw means not duplicate)
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            for jd in raw_jds:
                # Basic cleaning: strip whitespace, normalize
                if jd.clean_text:
                    jd.clean_text = jd.clean_text.strip()
                    if not jd.job_title:
                        # Try to extract title from text
                        first_line = jd.clean_text.split("\n")[0][:200]
                        jd.job_title = first_line or "Unknown"
                processed += 1
            s.commit()
    except Exception as exc:
        errors.append(f"clean failed: {exc}")
        logger.error("Clean stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors}


def execute_import(run_id: str) -> dict[str, Any]:
    """Execute import stage: extract skills from JDs and persist to PostgreSQL + Neo4j."""
    from app.tasks.stage3_services import run_batch_extract_jd

    processed = 0
    errors: list[str] = []

    try:
        # Get cleaned JDs from jd_raw that haven't been extracted yet
        from crawler.persistence.database import get_jd_raw_session
        from crawler.persistence.models import JdRaw, JdStatus

        with get_jd_raw_session() as s:
            clean_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).limit(100).all()
            jd_texts = []
            for jd in clean_jds:
                if jd.clean_text:
                    jd_texts.append(jd.clean_text)
                    jd.status = JdStatus.extracted
            s.commit()

        # Extract skills from each JD via LLM
        for text in jd_texts:
            try:
                result = _run_async(run_batch_extract_jd(text))
                if result.get("status") == "completed":
                    processed += 1
                else:
                    errors.append(f"extraction failed: {result.get('error', 'unknown')}")
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.warning("JD extraction failed in import stage: {}", exc)

    except Exception as exc:
        errors.append(f"import failed: {exc}")
        logger.error("Import stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors}


def execute_graph_sync(run_id: str) -> dict[str, Any]:
    """Execute graph_sync stage: build Neo4j graph from extraction records."""
    from app.tasks.stage3_services import run_build_graph_from_extractions

    processed = 0
    errors: list[str] = []

    try:
        result = _run_async(run_build_graph_from_extractions(limit=500))
        processed = result.get("processed", 0)
        if result.get("status") != "completed":
            errors.append(f"graph sync incomplete: {result}")
    except Exception as exc:
        errors.append(f"graph_sync failed: {exc}")
        logger.error("Graph sync stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors}


STAGE_EXECUTORS = {
    StageName.CRAWL.value: execute_crawl,
    StageName.DEDUP.value: execute_dedup,
    StageName.CLEAN.value: execute_clean,
    StageName.IMPORT.value: execute_import,
    StageName.GRAPH_SYNC.value: execute_graph_sync,
}


# ---------------------------------------------------------------------------
# DAG advance logic (async, updates DB + dispatches next Celery tasks)
# ---------------------------------------------------------------------------

async def advance_pipeline(run_id: uuid.UUID) -> None:
    """Check stage statuses and dispatch the next ready stages.

    Called after each stage completes (or fails). Handles:
    - Dispatching ready stages to Celery
    - Skipping optional stages whose deps failed
    - Completing the run when all stages are done
    """
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sessionmaker_ = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker_() as session:
            async with session.begin():
                result = await session.execute(
                    select(PipelineRun).where(PipelineRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run is None:
                    return

                stages = run.stages or []

                # Skip optional stages whose deps failed
                for s in stages:
                    if s["status"] != StageStatus.PENDING.value:
                        continue
                    deps = STAGE_DEPS.get(s["name"], [])
                    any_dep_failed = any(
                        any(ds["name"] == d and ds["status"] == StageStatus.FAILED.value for ds in stages)
                        for d in deps
                    )
                    if any_dep_failed and s["name"] in OPTIONAL_STAGES:
                        s["status"] = StageStatus.SKIPPED.value
                        s["completed_at"] = datetime.now(UTC).isoformat()
                    elif any_dep_failed and s["name"] not in OPTIONAL_STAGES:
                        # Required dep failed -> mark run as failed
                        pass  # handled below when we check all_stages_done

                # Check if all stages are done
                if all_stages_done(stages):
                    failed = get_failed_stages(stages)
                    total_records = sum(s.get("records_processed", 0) for s in stages)
                    run_status = RunStatus.FAILED.value if failed else RunStatus.COMPLETED.value
                    error_log = f"Failed stages: {failed}" if failed else None
                    await session.execute(
                        update(PipelineRun)
                        .where(PipelineRun.id == run_id)
                        .values(
                            stages=stages,
                            status=run_status,
                            completed_at=datetime.now(UTC),
                            total_records=total_records,
                            error_log=error_log,
                        )
                    )
                    # Broadcast completion
                    await _publish_stage_progress(
                        str(run_id), "pipeline", run_status,
                        progress=1.0 if run_status == RunStatus.COMPLETED.value else 0.0,
                        message=f"Pipeline {run_status}",
                    )
                    return

                # Write back any skipped stage updates
                await session.execute(
                    update(PipelineRun).where(PipelineRun.id == run_id).values(stages=stages)
                )

            # Dispatch ready stages (outside transaction so each dispatch is independent)
            ready = get_ready_stages(stages)
            for stage_name in ready:
                # Mark as running
                await update_stage_status(session, run_id, stage_name, status=StageStatus.RUNNING.value)
                await _publish_stage_progress(
                    str(run_id), stage_name, StageStatus.RUNNING.value,
                    progress=0.0, message=f"Stage {stage_name} started",
                )
                # Dispatch Celery task
                from app.tasks.celery_app import execute_pipeline_stage
                execute_pipeline_stage.delay(str(run_id), stage_name)

    finally:
        await engine.dispose()


async def trigger_and_start(
    run_type: str = "full",
    selected_stages: list[str] | None = None,
) -> PipelineRun:
    """Create a pipeline run and start executing the first ready stage(s)."""
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sessionmaker_ = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker_() as session:
            async with session.begin():
                run = await create_run(session, run_type=run_type, selected_stages=selected_stages)
                run_id = run.id

        # Advance the DAG — dispatches first stage(s)
        await advance_pipeline(run_id)

        # Re-fetch and return
        async with sessionmaker_() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            return result.scalar_one()
    finally:
        await engine.dispose()


async def retry_stage(run_id: uuid.UUID, stage_name: str) -> PipelineRun | None:
    """Reset a failed stage to PENDING and advance the pipeline."""
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sessionmaker_ = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker_() as session:
            # Reset the stage
            await update_stage_status(
                session, run_id, stage_name,
                status=StageStatus.PENDING.value,
                errors=[],
                retry_count=0,
            )
        # Re-advance
        await advance_pipeline(run_id)
        async with sessionmaker_() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            return result.scalar_one_or_none()
    finally:
        await engine.dispose()


async def resume_run(run_id: uuid.UUID) -> PipelineRun | None:
    """Resume a failed pipeline run by resetting all failed stages and advancing."""
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sessionmaker_ = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker_() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return None

            stages = list(run.stages or [])
            for s in stages:
                if s["status"] == StageStatus.FAILED.value:
                    s["status"] = StageStatus.PENDING.value
                    s["errors"] = []
                    s["retry_count"] = 0
                    s["started_at"] = None
                    s["completed_at"] = None

            # Reset run status to running
            run.status = RunStatus.RUNNING.value
            run.completed_at = None
            await session.execute(
                update(PipelineRun)
                .where(PipelineRun.id == run_id)
                .values(stages=stages, status=RunStatus.RUNNING.value, completed_at=None)
            )

        await advance_pipeline(run_id)

        async with sessionmaker_() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            return result.scalar_one_or_none()
    finally:
        await engine.dispose()
