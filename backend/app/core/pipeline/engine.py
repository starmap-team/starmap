"""Pipeline DAG 执行引擎（Phase 03 Plan 03 拆分：从 executor.py 迁出）。

包含 DAG 推进 / 触发 / 重试 / 续跑逻辑与 STAGE_EXECUTORS 映射。
executor.py 保留兼容重导出（D-11），存量调用方零改动；新代码请直接
from app.core.pipeline.engine import ...。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select, update

from app.core.pipeline.orchestrator import (
    OPTIONAL_STAGES,
    STAGE_DEPS,
    RunStatus,
    StageName,
    StageStatus,
    all_stages_done,
    complete_run,
    create_run,
    get_failed_stages,
    get_ready_stages,
    update_stage_status,
)
from app.core.pipeline.stages import (
    execute_clean,
    execute_crawl,
    execute_dedup,
    execute_graph_sync,
    execute_import,
    execute_timeseries,
)
from app.core.pipeline.stages.common import publish_stage_progress
from app.db.session import get_session_factory
from app.exceptions import PipelineStageError, StarMapError
from app.models.pipeline_models import PipelineRun
from app.services.resources import resources as app_resources

STAGE_EXECUTORS: dict[str, Any] = {
    StageName.CRAWL.value: execute_crawl,
    StageName.DEDUP.value: execute_dedup,
    StageName.CLEAN.value: execute_clean,
    StageName.IMPORT.value: execute_import,
    StageName.GRAPH_SYNC.value: execute_graph_sync,
    StageName.TIMESERIES.value: execute_timeseries,
}


# ---------------------------------------------------------------------------
# DAG advance logic (async, updates DB + dispatches next Celery tasks)
# ---------------------------------------------------------------------------

def _derive_run_record_counts(crawl_stage: dict, crawl_records: int) -> tuple[int, int]:
    """从 crawl 阶段推导 run 级 new/updated 记录数（P1-7）。

    records_new=0 是合法值（全部重复），不得用 `or` 回退到 crawl_records；
    仅当字段缺省（None）时回退。
    """
    _rn = crawl_stage.get("records_new")
    new_records = int(_rn) if _rn is not None else crawl_records
    _rd = crawl_stage.get("records_duplicate")
    updated_records = int(_rd) if _rd is not None else 0
    return new_records, updated_records


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
    except PipelineStageError:
        raise
    except Exception:
        logger.exception("advance_pipeline STOP flag check failed (continuing)")

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return

            raw_stages = run.stages or []
            stages: list[dict[str, Any]] = raw_stages if isinstance(raw_stages, list) else []

            # Skip or fail stages whose deps failed
            # Phase 3.8.7: also fail required stages (not just skip optional ones)
            for s in stages:
                if s["status"] != StageStatus.PENDING.value:
                    continue
                deps = STAGE_DEPS.get(s["name"], [])
                any_dep_failed = any(
                    any(ds["name"] == d and ds["status"] == StageStatus.FAILED.value for ds in stages)
                    for d in deps
                )
                if any_dep_failed:
                    if s["name"] in OPTIONAL_STAGES:
                        s["status"] = StageStatus.SKIPPED.value
                    else:
                        # Phase 3.8.7 FIX: Required dep failed -> 标记下游 stage 为 failed
                        s["status"] = StageStatus.FAILED.value
                    s["completed_at"] = datetime.now(UTC).isoformat()
                    if s["name"] not in OPTIONAL_STAGES:
                        # P0-AUDIT-FIX (2026-08-13): previously `error_log` was
                        # never populated on cascade-fail, so when admins
                        # inspected a stuck run they could not tell which
                        # upstream stage was the root cause. Record the
                        # failed-dep names so the UI can show "cascaded from X".
                        failed_deps = [
                            d for d in deps
                            if any(ds["name"] == d and ds["status"] == StageStatus.FAILED.value for ds in stages)
                        ]
                        s["error_log"] = f"cascaded from failed dep(s): {', '.join(failed_deps)}"
                        logger.warning(
                            "advance_pipeline: marking {} as FAILED (required dep failed: {})",
                            s["name"], failed_deps,
                        )

            # Check if all stages are done
            if all_stages_done(stages):
                failed = get_failed_stages(stages)
                # 2026-08-12 (pipeline 修复): total_records 只计本轮 crawl 新增入库数。
                # 原实现 Σ 全部 stage records_processed，把 graph_sync 的 outbox 回补与
                # timeseries 时间窗数混入 —— failed run 因此出现误导性的 "总记录 435"
                # （其实是 timeseries 窗口数），completed run 的 709=50+224+435 也无法
                # 表达"本轮采集入库了多少"。现在 failed run 的总记录 = 本轮采集量。
                crawl_records = next(
                    (
                        int(s.get("records_new", 0))
                        for s in stages
                        if s.get("name") == StageName.CRAWL.value
                    ),
                    0,
                )
                total_records = crawl_records
                run_status = RunStatus.FAILED.value if failed else RunStatus.COMPLETED.value
                error_log = f"Failed stages: {failed}" if failed else None
                # P1-3 fix (functional-review 2026-08-13): 完成分支此前内联
                # update(PipelineRun) 只写 stages/status/completed_at/total_records/
                # error_log，从不写 new_records/updated_records/quality_score ——
                # 导致 /quality/trends、/dashboard/trends、/datasources/{id}/stats
                # 的质量分与新增记录恒 0（complete_run 定义了完整回写却无人调用，
                # 成为死代码）。改为经 complete_run 收口：聚合 crawl 阶段的
                # records_new/records_duplicate 并计算 data_sources 加权质量分。
                crawl_stage = next(
                    (
                        s for s in stages
                        if s.get("name") == StageName.CRAWL.value
                    ),
                    {},
                )
                # P1-7 fix (2026-08-15): records_new=0 是合法值（全部重复），
                # 原 `records_new or crawl_records` 把 0 误判为缺省 → 回退成
                # total（85），导致 run 级 new=total=updated 同值。改用显式 None 判断。
                new_records, updated_records = _derive_run_record_counts(crawl_stage, crawl_records)
                quality_score = 0.0
                try:
                    from app.core.pipeline.quality_monitor import compute_source_quality

                    qm = await compute_source_quality(session)
                    quality_score = qm.overall_score
                except StarMapError:
                    raise
                except Exception:
                    logger.exception(
                        "advance_pipeline quality_score compute failed (non-fatal)"
                    )
                # complete_run 不写 stages —— 先持久化本事务内对 stages 的
                # cascade-fail/skip 修改，再收口 run 级指标。
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == run_id)
                    .values(stages=stages)
                )
                await complete_run(
                    session,
                    run_id,
                    status=run_status,
                    total_records=total_records,
                    new_records=new_records,
                    updated_records=updated_records,
                    quality_score=quality_score,
                    error_log=error_log,
                )
                # Broadcast completion
                await publish_stage_progress(
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
        logger.info(f"advance_pipeline run_id={run_id}: ready_stages={ready}")
        for stage_name in ready:
            # Mark as running
            logger.info(f"advance_pipeline run_id={run_id}: marking {stage_name} as RUNNING")
            await update_stage_status(session, run_id, stage_name, status=StageStatus.RUNNING.value)
            await session.commit()  # Phase 3.8 FIX: 显式 commit 确保 running 状态立即持久化
            logger.info(f"advance_pipeline run_id={run_id}: {stage_name} marked running and committed")
            await publish_stage_progress(
                str(run_id), stage_name, StageStatus.RUNNING.value,
                progress=0.0, message=f"Stage {stage_name} started",
            )
            # Dispatch Celery task
            from app.tasks.celery_app import execute_pipeline_stage
            execute_pipeline_stage.delay(str(run_id), stage_name)


async def trigger_and_start(
    run_type: str = "full",
    selected_stages: list[str] | None = None,
    selected_sources: list[str] | None = None,
) -> PipelineRun:
    """Create a pipeline run and start executing the first ready stage(s).

    Before creating a new run, cancels any existing runs stuck in 'running'
    status (older than 30 minutes) to prevent accumulation of orphan runs.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            # Cancel any stuck running runs older than 30 minutes
            from datetime import timedelta
            stuck = await session.execute(
                select(PipelineRun)
                .where(PipelineRun.status == "running")
                .where(PipelineRun.started_at < datetime.now(UTC) - timedelta(minutes=30))
            )
            for old_run in stuck.scalars().all():
                old_run.status = "cancelled"
                old_run.completed_at = datetime.now(UTC)
                logger.warning(
                    "Cancelled stuck pipeline run {} (started at {}, {:.1f}h old)",
                    old_run.id, old_run.started_at,
                    (datetime.now(UTC) - old_run.started_at).total_seconds() / 3600,
                )
            run = await create_run(
                session,
                run_type=run_type,
                selected_stages=selected_stages,
                selected_sources=selected_sources,
            )
            run_id = run.id

    # Advance the DAG — dispatches first stage(s)
    await advance_pipeline(run_id)

    # Re-fetch and return
    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one()


async def retry_stage(run_id: uuid.UUID, stage_name: str) -> PipelineRun | None:
    """Reset a failed stage to PENDING and advance the pipeline."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 2026-08-12 (pipeline 修复): 必须显式 begin —— session 退出即回滚，
        # 否则 stage 重置丢失，advance_pipeline 会读到原始失败态并重新标记 failed。
        async with session.begin():
            # Reset the stage
            await update_stage_status(
                session, run_id, stage_name,
                status=StageStatus.PENDING.value,
                errors=[],
                retry_count=0,
            )
    # Re-advance
    await advance_pipeline(run_id)
    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()


async def resume_run(run_id: uuid.UUID) -> PipelineRun | None:
    """Resume a failed pipeline run by resetting all failed stages and advancing."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 2026-08-12 (pipeline 修复): 必须显式 begin —— 无 begin 时 stages 重置在
        # session 关闭时被回滚，advance_pipeline 读到原始失败态 → 续跑实际无效
        # （仅刷新了 completed_at）。加 begin 保证重置持久化。
        async with session.begin():
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

    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()


__all__ = [
    "STAGE_EXECUTORS",
    "advance_pipeline",
    "retry_stage",
    "resume_run",
    "trigger_and_start",
]
