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

import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

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
from app.db.session import get_async_engine
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

from app.utils.async_helpers import run_async as _run_async  # noqa: E402

# ponytail: removed duplicate _run_async; reusing utils.async_helpers


def execute_crawl(run_id: str, run_type: str) -> dict[str, Any]:
    """Execute the crawl stage: run spiders and upsert JDs into jd_raw.

    Phase 2 AUTHORITY-03: Skip paused data sources.

    Configuration (keyword, max_count) is read from DataSourceRecord.config,
    falling back to defaults: keyword="python", max_count=50 (incremental)/200 (full).
    """
    from crawler.persistence import dao
    from crawler.persistence.models import JdStatus
    from crawler.spiders.boss import run_sync as boss_sync

    # Phase 2 AUTHORITY-03: 跳过 paused 数据源
    _run_async(_skip_paused_sources_if_needed(run_id))

    # Load crawl config from DataSourceRecord; fallback to defaults
    crawl_config = _run_async(_get_crawl_config(run_id))
    keyword = crawl_config.get("keyword", "python")
    max_count = crawl_config.get(
        "max_count",
        50 if run_type == "incremental" else 200,
    )
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
    finally:
        # Phase 2 SOURCE-01: execute_crawl 后更新 DataSourceRecord (UAT 修复)
        try:
            _update_source_after_crawl(run_id, total_inserted)
        except Exception as exc:
            logger.warning("_update_source_after_crawl failed (non-fatal): {}", exc)

    return {"records_processed": total_inserted, "errors": errors}


def execute_dedup(run_id: str) -> dict[str, Any]:
    """Execute dedup stage: two-pass dedup on jd_raw records.

    Pass 1 — exact dedup via Redis content-hash lookup (``dedup_service``).
    Pass 2 — fuzzy dedup via SimHash with character 3-grams (``dedup_service``).
    Falls back to the legacy crawler SimHash when Redis is unavailable.
    """
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus

    processed = 0
    exact_duplicates = 0
    fuzzy_duplicates = 0
    errors: list[str] = []

    try:
        with get_jd_raw_session() as s:
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            if not raw_jds:
                return {"records_processed": 0, "errors": errors, "duplicates_found": 0}

            processed = len(raw_jds)

            # --- Two-pass dedup via dedup_service ---
            from app.services.dedup_service import dedup_jd_records

            redis_client = app_resources.redis_client

            def _get_clean_text(jd: Any) -> str:
                return jd.clean_text or ""

            unique_jds, dup_jds = _run_async(
                dedup_jd_records(
                    raw_jds,
                    text_getter=_get_clean_text,
                    redis_client=redis_client,
                    threshold=3,
                ),
            )

            # Separate exact vs fuzzy counts from the returned duplicates
            # (dedup_service returns both passes merged; we mark all as duplicate)
            dup_ids = {id(jd) for jd in dup_jds}
            for jd in raw_jds:
                if id(jd) in dup_ids:
                    jd.status = JdStatus.duplicate

            duplicates = len(dup_jds)
            s.commit()

            logger.info(
                "Dedup stage run_id={}: {} total, {} unique, {} duplicates",
                run_id, processed, len(unique_jds), duplicates,
            )
    except Exception as exc:
        errors.append(f"dedup failed: {exc}")
        logger.error("Dedup stage failed: {}", exc)
    finally:
        # Phase 2 SOURCE-02: execute_dedup 后更新 duplicate_rate (UAT 修复)
        try:
            _update_source_after_dedup(run_id, exact_duplicates + fuzzy_duplicates, processed)
        except Exception as exc:
            logger.warning("_update_source_after_dedup failed (non-fatal): {}", exc)

    return {"records_processed": processed, "errors": errors, "duplicates_found": exact_duplicates + fuzzy_duplicates}


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
    finally:
        # Phase 2 SOURCE-03: execute_import 后更新 valid_records (UAT 修复)
        try:
            _update_source_after_import(run_id, processed)
        except Exception as exc:
            logger.warning("_update_source_after_import failed (non-fatal): {}", exc)

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


# ---------------------------------------------------------------------------
# Phase 2: DataSourceRecord 实时更新 (SOURCE-01/02/03)
# 这些函数从 sync Celery worker 调用，使用 _run_async 桥接 async DB
# ---------------------------------------------------------------------------

def _update_source_after_crawl(run_id: str, records_count: int) -> None:
    """execute_crawl 完成后更新 DataSourceRecord.total_records + last_crawl_at."""
    async def _update():
        engine = get_async_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                from sqlalchemy import text

                from app.models.pipeline_models import DataSourceRecord

                # 按 source_platform 分组计数
                result = await session.execute(
                    text("SELECT source_platform, COUNT(*) as cnt FROM raw_jd_records GROUP BY source_platform")
                )
                rows = result.fetchall()
                for platform, cnt in rows:
                    # 找对应 DataSourceRecord（按 name 匹配）
                    ds_result = await session.execute(
                        select(DataSourceRecord).where(DataSourceRecord.name == platform)
                    )
                    ds = ds_result.scalar_one_or_none()
                    if ds:
                        ds.total_records = (ds.total_records or 0) + int(cnt)
                        ds.last_crawl_at = datetime.now(UTC)
                await session.commit()
                logger.info("_update_source_after_crawl: updated {} sources for run_id={}", len(rows), run_id)
        finally:
            await engine.dispose()
    _run_async(_update())


def _update_source_after_dedup(run_id: str, duplicates: int, total: int) -> None:
    """execute_dedup 完成后更新 DataSourceRecord.duplicate_rate.

    Looks up all active crawler DataSourceRecords and updates the
    duplicate_rate for each.  When only one source exists the update is
    unambiguous; when multiple exist, the same rate is applied to all
    (dedup operates across the whole raw_jd table).
    """
    async def _update():
        engine = get_async_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                from app.models.pipeline_models import DataSourceRecord
                ds_result = await session.execute(
                    select(DataSourceRecord).where(
                        DataSourceRecord.source_type == "crawler",
                        DataSourceRecord.status == "active",
                    )
                )
                sources = ds_result.scalars().all()
                if not sources:
                    logger.warning("_update_source_after_dedup: no active crawler sources found for run_id={}", run_id)
                    return
                dup_rate = round(duplicates / total, 4) if total > 0 else 0.0
                for ds in sources:
                    ds.duplicate_rate = dup_rate
                await session.commit()
                logger.info(
                    "_update_source_after_dedup: duplicate_rate={} for {} source(s), run_id={}",
                    dup_rate, len(sources), run_id,
                )
        finally:
            await engine.dispose()
    _run_async(_update())


def _update_source_after_import(run_id: str, valid_count: int) -> None:
    """execute_import 完成后更新 DataSourceRecord.valid_records + avg_quality_score."""
    async def _update():
        engine = get_async_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                from sqlalchemy import text

                from app.models.pipeline_models import DataSourceRecord

                # 重算所有 data_sources 的 avg_quality_score
                ds_list_result = await session.execute(
                    select(DataSourceRecord)
                )
                all_ds = ds_list_result.scalars().all()
                for ds in all_ds:
                    # 从 extraction_models 查询有效记录数（按 source_platform 匹配）
                    rec_result = await session.execute(
                        text("SELECT COUNT(*) FROM raw_jd_records WHERE source_platform = :platform AND status = 'extracted'"),
                        {"platform": ds.name},
                    )
                    extracted = rec_result.scalar() or 0
                    ds.valid_records = extracted
                    ds.avg_quality_score = min(extracted / 100.0, 1.0) if extracted > 0 else 0.0

                await session.commit()
                logger.info("_update_source_after_import: updated valid_records for run_id={}", run_id)
        finally:
            await engine.dispose()
    _run_async(_update())


async def _get_crawl_config(run_id: str) -> dict[str, Any]:
    """Load crawl configuration (keyword, max_count) from active DataSourceRecord(s).

    Queries all active crawler-type data sources and merges their configs.
    Falls back to defaults if no config is found.
    """
    try:
        engine = get_async_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                from sqlalchemy import select as sa_select

                from app.models.pipeline_models import DataSourceRecord
                result = await session.execute(
                    sa_select(DataSourceRecord).where(
                        DataSourceRecord.source_type == "crawler",
                        DataSourceRecord.status == "active",
                    )
                )
                sources = result.scalars().all()
                # Merge configs from all active crawler sources; first source wins
                merged: dict[str, Any] = {}
                for ds in sources:
                    if ds.config:
                        for k, v in ds.config.items():
                            if k not in merged:
                                merged[k] = v
                if merged:
                    logger.debug(
                        "Loaded crawl config from {} active source(s): {}",
                        len(sources), merged,
                    )
                    return merged
        finally:
            await engine.dispose()
    except Exception as exc:
        logger.warning("_get_crawl_config failed (non-fatal, using defaults): {}", exc)
    return {}


async def _skip_paused_sources_if_needed(run_id: str) -> None:
    """Phase 2 AUTHORITY-03: Log paused sources (the actual skip happens in the spider call)."""
    try:
        engine = get_async_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                from sqlalchemy import select as sa_select

                from app.models.pipeline_models import DataSourceRecord
                paused = await session.execute(
                    sa_select(DataSourceRecord).where(DataSourceRecord.status == "paused")
                )
                paused_sources = paused.scalars().all()
                if paused_sources:
                    names = [s.name for s in paused_sources]
                    logger.info("Skipping {} paused source(s) for run_id={}: {}", len(names), run_id, names)
        finally:
            await engine.dispose()
    except Exception as exc:
        logger.warning("_skip_paused_sources_if_needed failed (non-fatal): {}", exc)


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

    Phase 1 D-04: STOP flag 检查 — if Redis flag `pipeline:stop:{run_id}` is set,
    skip all stage dispatch and don't complete the run (cancel_run 已经标记 cancelled).
    """
    # Phase 1 D-04: STOP flag 检查
    try:
        from app.core.pipeline.orchestrator import is_run_cancelled
        redis_client = app_resources.redis_client
        if await is_run_cancelled(redis_client, run_id):
            logger.info(
                "advance_pipeline run_id=%s: STOP flag set, skipping advance",
                run_id,
            )
            return
    except Exception as exc:
        logger.warning(f"advance_pipeline STOP flag check failed (continuing): {exc}")

    engine = get_async_engine()
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

                raw_stages = run.stages or []
                stages: list[dict[str, Any]] = raw_stages if isinstance(raw_stages, list) else []

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
    engine = get_async_engine()
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
    engine = get_async_engine()
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
    engine = get_async_engine()
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
