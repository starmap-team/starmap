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
from app.exceptions import StarMapError
from app.tasks.stage3_services import (
    run_analyze_evolution_trends,
    run_batch_extract_jd,
    run_build_graph_from_extractions,
)
from app.utils.async_helpers import run_async

celery_app = Celery(
    "starmap",
    broker=settings.redis_uri,
    backend=settings.redis_uri)
celery_app.conf.update(
    task_default_queue="starmap",
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_time_limit=settings.pipeline_stage_timeout,
    task_soft_time_limit=settings.pipeline_stage_timeout - 30)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def batch_extract_jd(self, jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Batch-extract skills from a JD via Celery."""
    try:
        logger.info("batch_extract_jd started chars={}", len(jd_text))
        return run_async(run_batch_extract_jd(jd_text, options=options))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        raise self.retry(exc=exc) from exc

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, Any]:
    """Build Neo4j graph triples from persisted extraction records."""
    try:
        logger.info("build_graph_from_extractions started limit={}", limit)
        return run_async(run_build_graph_from_extractions(limit))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        raise self.retry(exc=exc) from exc

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, Any]:
    """Analyze skill and position evolution from recent extraction records."""
    try:
        logger.info("analyze_evolution_trends started days={}", days)
        return run_async(run_analyze_evolution_trends(days))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        raise self.retry(exc=exc) from exc

@celery_app.task(
    bind=True,
    max_retries=settings.pipeline_retry_max,
    default_retry_delay=settings.pipeline_retry_backoff,
    acks_late=True,
    reject_on_worker_lost=True)
def execute_pipeline_stage(self, run_id: str, stage_name: str) -> dict[str, Any]:
    """Execute a single pipeline stage and advance the DAG.

    On success: marks stage completed, then calls advance_pipeline to dispatch next stages.
    On failure: retries with backoff; after max retries, marks stage failed and advances.: STOP flag 检查 — if Redis flag `pipeline:stop:{run_id}` is set,
    raise PipelineCancelled to gracefully skip this stage (no retry).
    """
    from app.core.pipeline.executor import STAGE_EXECUTORS, advance_pipeline

 #: Check STOP flag at the START of each stage execution
    try:
        from app.core.pipeline.orchestrator import is_run_cancelled
        from app.services.resources import resources as app_resources
        redis_client = app_resources.redis_client
        if run_async(is_run_cancelled(redis_client, uuid.UUID(run_id))):
            logger.info(
                "execute_pipeline_stage run_id={} stage={}: STOP flag detected, marking cancelled",
                run_id, stage_name)
            run_async(_mark_stage_cancelled(run_id, stage_name))
            return {"status": "cancelled", "stage": stage_name, "reason": "STOP flag set"}
    except StarMapError:
        raise
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
        # only crawl accepts run_type; others take run_id only
        if stage_name == StageName.CRAWL.value:
            result = executor(run_id, run_type="full")  # type: ignore[operator]
        else:
            result = executor(run_id)  # type: ignore[operator]
        duration_ms = int((time.monotonic() - start) * 1000)

 # Update stage status AND advance DAG in ONE async call
 # (avoids "different loop" error when running two separate run_async calls)
        async def _complete_and_advance():
            await _mark_stage_completed(
                run_id, stage_name,
                duration_ms=duration_ms,
                records_processed=result.get("records_processed", 0),
                records_seen=result.get("records_seen", 0),
                records_new=result.get("records_new"),
                records_duplicate=result.get("records_duplicate"),
                errors=result.get("errors", []),
                warnings=result.get("warnings", []),
                current_activity=result.get("current_activity", ""),
                recent_samples=result.get("recent_samples", []),
                sub_breakdown=result.get("sub_breakdown", {}))
            await advance_pipeline(uuid.UUID(run_id))

        run_async(_complete_and_advance())

        return {"status": "completed", "stage": stage_name, **result}

    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
 # P0-AUDIT-FIX (2026-08-13): when `self.retry` exhausts
 # `max_retries`, Celery raises `MaxRetriesExceededError` and the task
 # fails — but `_mark_stage_failed` was never called, so the stage
 # record stays at status='running' until the watchdog sweep runs
 # `pipeline_stage_timeout * 2` later (≥30 min). The DAG also stops
 # advancing because advance_pipeline is only called on success.
 # Detect exhaustion via `self.request.retries` and explicitly mark
 # the stage failed BEFORE raising — so admins see the root cause
 # immediately and DAG downstream can cascade-fail.
        if self.request.retries >= settings.pipeline_retry_max:
            try:
                run_async(_mark_stage_failed(run_id, stage_name, [str(exc)]))
            except Exception as mark_exc:
                logger.exception("Failed to mark stage {} failed: {}", stage_name, mark_exc)
 # Do NOT re-raise after marking failed — let the task end normally
 # so Celery records the failure correctly and the watchdog sweep
 # isn't triggered prematurely. Returning a failure dict is enough.
            return {"status": "failed", "stage": stage_name, "error": str(exc), "exhausted": True}
        retry_delay = settings.pipeline_retry_backoff * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay) from exc

async def _mark_stage_cancelled(run_id: str, stage_name: str) -> None:
    """Mark a stage as cancelled in the pipeline_runs.stages JSONB )."""
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
                StageStatus.PENDING.value):
                stage["status"] = "cancelled"
                stage["completed_at"] = datetime.now(UTC).isoformat
                flag_modified(run, "stages")
                break
        await session.commit()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def advance_pipeline_task(self, run_id: str) -> None:
    """Async advance_pipeline wrapper for Celery dispatch.

    Retries with exponential backoff if worker crashes mid-execution.
    Stale advances are idempotent: advance_pipeline only dispatches PENDING stages.
    """
    import uuid

    from app.core.pipeline.executor import advance_pipeline
    try:
        run_async(advance_pipeline(uuid.UUID(run_id)))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries)) from exc

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def reconcile_graph_task(self, schedule_id: str) -> None:
    """BUG-16 fix: Celery task for daily PG↔Neo4j reconcile.

    Triggered by the cron_scanner when a `daily_reconcile` schedule comes due.
    Runs the same reconciliation logic the manual `/admin/reconcile-neo4j`
    endpoint triggers, and writes an audit event so Tab 7 数据源诊断 can
    show "last reconcile" correctly.

    BUG-16 root cause: the schedule existed in code paths but `pipeline_schedules`
    had no row registered for it, AND `trigger_schedule` always called
    `scheduled_pipeline_run` regardless of schedule name. Both are now fixed.
    """
    try:
        async def _run() -> None:
            from app.core.pipeline.cron_scheduler import _run_daily_reconcile
            from app.db.session import get_session_factory

            sm = get_session_factory()
            async with sm() as session:
                async with session.begin():
                    await _run_daily_reconcile(session)
 # P4b 漂移告警: reconcile 后检测残留孤儿（被引用无标识节点/缺 PG 记录），
 # 非零即告警——让每日 cron 把漂移暴露为可观测信号，而非静默。
                try:
                    from app.services.repair_engine import RepairEngine
                    from app.services.resources import resources as app_resources

                    if app_resources.neo4j_driver is not None:
                        repair = RepairEngine(app_resources.neo4j_driver)
                        scan = await repair.detect_orphans(session)
                        if scan.total > 0:
                            logger.warning(
                                "reconcile drift alert: {} orphan nodes remain "
                                "(positions={}, skills={}) — 需链接 canonical_id 或补录 PG",
                                scan.total, scan.orphan_positions, scan.orphan_skills)
                        else:
                            logger.info("reconcile drift check: clean (0 orphans)")
                except Exception as drift_exc:  # noqa: BLE001 — 告警失败不阻断
                    logger.warning("reconcile drift check failed (non-fatal): {}", drift_exc)

        run_async(_run())
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("reconcile_graph_task error: {}", exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries)) from exc

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def scheduled_pipeline_run(self, schedule_id: str) -> None:
    """CRON-04: 读取 schedule 并触发 pipeline。

    Retries once at 60s delay. If the schedule fetch fails (transient DB issue),
    the retry gives PostgreSQL time to recover.
    """
    try:
        run_async(_execute_scheduled_run(schedule_id))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        raise self.retry(exc=exc) from exc

async def _execute_scheduled_run(schedule_id: str) -> None:
    """读取 schedule → trigger → 更新 last/next_run_at。"""
    from datetime import timedelta

    from sqlalchemy import select

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
        await trigger_and_start(
            run_type=schedule.run_type,
            selected_stages=schedule.selected_stages,
            selected_sources=schedule.selected_sources)

        schedule.last_run_at = datetime.now(UTC)
        try:
            from app.core.pipeline.cron_scheduler import compute_next_cron
            schedule.next_run_at = compute_next_cron(schedule.cron_expression, schedule.last_run_at)
        except StarMapError:
            raise
        except Exception:
            schedule.next_run_at = schedule.last_run_at + timedelta(hours=1)
        await session.commit()

@celery_app.task(bind=True, max_retries=0)
def sweep_orphan_runs(self) -> dict[str, Any]:
    """WATCHDOG: 清理超过 stage_timeout*2 仍 running 的任务。"""
    run_async(_sweep_orphan_runs_async())
    return {"status": "completed"}

async def _sweep_orphan_runs_async() -> dict[str, Any]:
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.pipeline.orchestrator import RunStatus
    from app.db.session import get_session_factory
    from app.models.pipeline_models import PipelineRun

    sm = get_session_factory()
    async with sm() as session:
        threshold = datetime.now(UTC) - timedelta(seconds=settings.pipeline_stage_timeout * 2)
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.status == RunStatus.RUNNING.value)
        )
        orphans = []
        for run in result.scalars().all():
 # P0-AUDIT-FIX (2026-08-13): started_at 可能为 naive（timezone=True 规范化
 # 前的历史行，或 SQLite 测试库）——naive 与 aware 比较会抛 TypeError。
 # 假定 naive = UTC，统一后做 Python 侧过滤（RUNNING 记录数少，可接受）。
            started_at = run.started_at
            if started_at is not None and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            if started_at < threshold:
                orphans.append(run)
        for run in orphans:
            run.status = RunStatus.FAILED.value
            run.completed_at = datetime.now(UTC)
            run.error_log = "orphaned by watchdog"
            # 2026-08-21: 同步把卡在 running 的 stage 标 failed —— 此前只标 run，
            # pipeline_runs.stages 快照里 import 永远 running，/pipeline/stages
            # 与运行历史长期矛盾（DAG「运行中 0%」vs 历史「失败」）。
            stages = list(run.stages or [])
            changed = False
            for stage in stages:
                if isinstance(stage, dict) and stage.get("status") == "running":
                    stage["status"] = "failed"
                    stage["completed_at"] = datetime.now(UTC).isoformat()
                    stage.setdefault("errors", []).append("stage orphaned by watchdog")
                    changed = True
            if changed:
                run.stages = stages
            logger.warning("Watchdog: orphaned run {} (started={})", run.id, run.started_at)
        await session.commit()
        return {"orphans_found": len(orphans)}

# ── Helpers ──
async def _mark_stage_completed(
    run_id: str, stage_name: str,
    *, duration_ms: int = 0, records_processed: int = 0, records_seen: int = 0, errors: list[str] | None = None,
    warnings: list[str] | None = None, records_new: int | None = None, records_duplicate: int | None = None,
    current_activity: str = "", recent_samples: list[dict] | None = None,
    sub_breakdown: dict[str, int] | None = None) -> None:
    """FIX: 智能判断 status.

    规则:
    - 0 记录 + 0 错误 → completed
    - 有记录 → completed (即使有错误, 错误是 warning)
    - 0 记录 + 有错误 → failed (关键修复: 之前所有 0 记录都被误标为 completed)

    2026-08-12 (pipeline 修复): 非致命提示（如 crawl 0 条采集）已移入 warnings，
    不再进入 errors —— 因此 "0 记录 + 有错误" 里的 errors 现在只代表真实异常，
    避免部分源返回 0 条导致定时任务每小时刷 failed。
    """
    from app.core.pipeline.orchestrator import update_stage_status
    from app.db.session import get_session_factory
    error_list = errors or []
 #0 记录 + 有错误 = 失败, 不是完成
    if records_processed == 0 and error_list:
        actual_status = "failed"
    else:
        actual_status = "completed"
    sm = get_session_factory()
    async with sm() as session:
        async with session.begin():
            await update_stage_status(
                session, uuid.UUID(run_id), stage_name,
                status=actual_status,
                duration_ms=duration_ms,
                records_processed=records_processed,
                records_seen=records_seen,
                errors=error_list,
                warnings=warnings,
                records_new=records_new,
                records_duplicate=records_duplicate,
                current_activity=current_activity,
                recent_samples=recent_samples,
                sub_breakdown=sub_breakdown)

async def _mark_stage_failed(
    run_id: str, stage_name: str, errors: list[str]) -> None:
    from app.core.pipeline.orchestrator import update_stage_status
    from app.db.session import get_session_factory
    sm = get_session_factory()
    async with sm() as session:
        async with session.begin():
            await update_stage_status(
                session, uuid.UUID(run_id), stage_name,
                status="failed",
                errors=errors)

# ── Beat schedule (: 定时演化分析) ──

from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "evolution-analyze": {
        "task": "app.tasks.celery_app.analyze_evolution_trends",
        "schedule": crontab(hour="*/6", minute=0),  # 每6小时
        "kwargs": {"days": 90},
    },
 #auto-recover orphaned pipeline runs stuck in RUNNING > 30min
    "sweep-orphan-runs": {
        "task": "app.tasks.celery_app.sweep_orphan_runs",
        "schedule": crontab(minute="*/5"),  # 每5分钟
    },
 #/): 重放 graph_write_outbox 失败行 + sweep 超龄
 # pending 行——每 30 分钟，幂等（MERGE），source_count max 语义不放大漂移
    "retry-failed-outbox-writes": {
        "task": "app.tasks.outbox_retry.retry_failed_outbox_writes",
        "schedule": crontab(minute="*/30"),  # 每30分钟
    },
 # 2026-08-28 (批2 可持续): 每日重试空技能岗位抽取（last_retry_at 幂等 + Redis 锁防并发）
    "retry-no-skill-positions": {
        "task": "app.tasks.celery_app.retry_no_skill_positions",
        "schedule": crontab(hour=3, minute=30),  # 每日 03:30 UTC
    },
}

# ──: Celery task_failure 信号接线 ──
# 失败任务此前不产生任何告警/审计——Celery 级失败对运营不可见（pipeline 由
# cron_scheduler 串行驱动，stage 失败仅靠 run 级 status，任务级异常静默）。
# 接线：task_failure → audit_events (celery_task_failure) + loguru 告警。

from celery import signals  # noqa: E402


def _on_task_failure(
    task_id: str | None = None,
    exception: BaseException | None = None,
    **kwargs: Any) -> None:
    """Celery task failure handler — surface to audit_events + logger.

    2026-08-21 修复: celery 5.6 的 task_failure 信号发送的命名参数是
    (task_id, exception, args, kwargs, traceback, einfo) —— 没有 task_name。
    此前签名 (task_id, task_name, exception) 导致每次任务失败 handler 自身
    抛 TypeError（日志可见 "missing 1 required positional argument"），
    审计与告警从未真正写入。sender 是 task 实例，可取其 name。
    """
    sender = kwargs.get("sender")
    task_name = getattr(sender, "name", "unknown") if sender is not None else "unknown"
    exc = exception if exception is not None else kwargs.get("einfo")
    detail = f"task_id={task_id} error={exc!r}" if exc is not None else f"task_id={task_id}"
    try:
        from app.utils.audit import AuditEntry, AuditEvent, audit_log

        audit_log(
            AuditEntry(
                event=AuditEvent.CELERY_TASK_FAILURE,
                actor="celery",
                action=f"task_failure:{task_name}",
                detail=detail,
                extra={"task_id": task_id, "task_name": task_name})
        )
    except Exception:
        logger.opt(exception=True).warning(
            "task_failure audit write failed (non-fatal): task={} id={}",
            task_name, task_id)
    logger.error(
        "Celery task FAILED: name={} id={} exc={!r}",
        task_name, task_id, exc)

if getattr(celery_app, "task_failure_handler_registered", False) is False:
    signals.task_failure.connect(_on_task_failure)
    celery_app.task_failure_handler_registered = True


# 2026-08-20 (debug 修复): worker 进程初始化 resources —— 此前 worker 从未调用
# init_resources()，进程内 redis_client=None → publish_event 静默 no-op →
# 所有 SSE 进度事件未发出 → 前端 import 阶段永远 0%（实时进度全靠 SSE）。
# 注意: 不能用 asyncio.run() —— 它会创建并关闭临时事件循环，redis 异步客户端
# 绑定该 loop，后续 celery task 的 loop 不同 → "Event loop is closed"。
# 改用 worker 进程级 loop（保持存活）run_until_complete。
def _on_worker_process_init(**kwargs: Any) -> None:
    try:
        import asyncio

        from app.services.resources import init_resources

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_resources())
        logger.info("[celery] resources initialized (redis/neo4j/pg) in worker process")
    except Exception:
        logger.opt(exception=True).warning(
            "[celery] init_resources failed in worker process (SSE publish will no-op)"
        )


if getattr(celery_app, "worker_init_registered", False) is False:
    signals.worker_process_init.connect(_on_worker_process_init)
    celery_app.worker_init_registered = True


@celery_app.task(bind=True, max_retries=0)
def retry_no_skill_positions(self: Any, limit: int = 50) -> dict[str, int]:
    """每日重试空技能岗位抽取（批2 可持续, 2026-08-28）。

    从 JDExtractionRecord.jd_content 重抽取 quality_hint='no_skills' 的岗位；
    成功（persist_extraction_result 建出 PSR）→ 清 quality_hint + 更新 last_retry_at；
    失败/无 JD 记录 → 仅更新 last_retry_at（幂等，明日再试）。
    Redis 锁防多 worker 并发；每日限次 limit（默认 50）。
    """
    import asyncio

    from redis import Redis

    from app.config import settings

    lock_key = "starmap:lock:retry_no_skill"
    try:
        redis_client = Redis.from_url(settings.redis_uri, socket_connect_timeout=3)
        if not redis_client.set(lock_key, "1", nx=True, ex=3600):
            logger.info("retry_no_skill_positions: lock held, skip")
            return {"skipped": "lock_held"}
    except Exception:  # noqa: BLE001 — Redis 不可用不阻断（单 worker 场景无并发）
        redis_client = None

    try:
        return asyncio.run(_run_no_skill_retry(limit))
    finally:
        if redis_client is not None:
            try:
                redis_client.delete(lock_key)
            except Exception:  # noqa: BLE001
                pass


async def _run_no_skill_retry(limit: int) -> dict[str, int]:
    """实际重试逻辑（可单测）。"""
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_async_engine
    from app.models.extraction_models import (
        JDExtractionRecord,
        PositionRecord,
        PositionSkillRelation,
    )
    from app.tasks.stage3_services import run_batch_extract_jd

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    stats = {"retried": 0, "success": 0, "failed": 0, "no_jd": 0}
    now = datetime.now(UTC)

    async with sessionmaker() as session:
        # 找 no_skills 且今天未重试过的岗位（last_retry_at IS NULL 或 < 今天 00:00）
        rows = (
            await session.execute(
                select(PositionRecord)
                .where(
                    PositionRecord.quality_hint == "no_skills",
                    (PositionRecord.last_retry_at.is_(None))
                    | (PositionRecord.last_retry_at < now.replace(hour=0, minute=0, second=0, microsecond=0)),
                )
                .limit(limit)
            )
        ).scalars().all()

        for pos in rows:
            stats["retried"] += 1
            # 取该岗位最近一条 completed JD 抽取记录原文
            jd = (
                await session.execute(
                    select(JDExtractionRecord)
                    .where(
                        JDExtractionRecord.status == "completed",
                        JDExtractionRecord.job_title == pos.name,
                    )
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
            if jd is None or not (jd.jd_content or "").strip():
                stats["no_jd"] += 1
                pos.last_retry_at = now
                await session.flush()
                continue
            try:
                await run_batch_extract_jd(
                    jd.jd_content,
                    job_title=pos.name,
                    source_run_id=pos.source_run_id,
                )
                # 成功判定：persist 后岗位有 PSR 关联
                has_psr = (
                    await session.execute(
                        select(PositionSkillRelation.id).where(
                            PositionSkillRelation.position_id == pos.id
                        ).limit(1)
                    )
                ).first()
                if has_psr is not None:
                    pos.quality_hint = None  # 清标记 → 下次 reconcile 可入图
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            except Exception as exc:  # noqa: BLE001 — 单条失败不阻断批量
                logger.warning("retry_no_skill extract failed for '{}': {}", pos.name[:50], exc)
                stats["failed"] += 1
            pos.last_retry_at = now
            await session.flush()
        await session.commit()
    await engine.dispose()
    logger.info("retry_no_skill_positions done: {}", stats)
    return stats
