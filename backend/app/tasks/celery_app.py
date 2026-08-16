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
        # ponytail: only crawl accepts run_type; others take run_id only
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
                sub_breakdown=result.get("sub_breakdown", {}),
            )
            await advance_pipeline(uuid.UUID(run_id))

        run_async(_complete_and_advance())

        return {"status": "completed", "stage": stage_name, **result}

    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Celery task error: {}", exc)
        # P0-AUDIT-FIX (2026-08-13): when `self.retry()` exhausts
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
                                scan.total, scan.orphan_positions, scan.orphan_skills,
                            )
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
    """Phase 2 CRON-04: 读取 schedule 并触发 pipeline。

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
            selected_sources=schedule.selected_sources,
        )

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
    """Phase 2 WATCHDOG: 清理超过 stage_timeout*2 仍 running 的任务。"""
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
            logger.warning("Watchdog: orphaned run {} (started={})", run.id, run.started_at)
        await session.commit()
        return {"orphans_found": len(orphans)}


# ── Helpers ──
async def _mark_stage_completed(
    run_id: str, stage_name: str,
    *, duration_ms: int = 0, records_processed: int = 0, records_seen: int = 0, errors: list[str] | None = None,
    warnings: list[str] | None = None, records_new: int | None = None, records_duplicate: int | None = None,
    current_activity: str = "", recent_samples: list[dict] | None = None,
    sub_breakdown: dict[str, int] | None = None,
) -> None:
    """Phase 3.8.7 FIX: 智能判断 status.

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
    # Phase 3.8.7: 0 记录 + 有错误 = 失败, 不是完成
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
                sub_breakdown=sub_breakdown,
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

from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "evolution-analyze": {
        "task": "app.tasks.celery_app.analyze_evolution_trends",
        "schedule": crontab(hour="*/6", minute=0),  # 每6小时
        "kwargs": {"days": 90},
    },
    # Phase 7: auto-recover orphaned pipeline runs stuck in RUNNING > 30min
    "sweep-orphan-runs": {
        "task": "app.tasks.celery_app.sweep_orphan_runs",
        "schedule": crontab(minute="*/5"),  # 每5分钟
    },
    # Phase 23 Task 1 (DC-02/DF-01): 重放 graph_write_outbox 失败行 + sweep 超龄
    # pending 行——每 30 分钟，幂等（MERGE），source_count max 语义不放大漂移
    "retry-failed-outbox-writes": {
        "task": "app.tasks.outbox_retry.retry_failed_outbox_writes",
        "schedule": crontab(minute="*/30"),  # 每30分钟
    },
    # Phase 2 (accuracy gate): 每周一 02:30 跑赛项三项 ≥90% 指标门禁，
    # 劣化自动写审计告警（prevention 之外的 detection 防线）
    "accuracy-gate-weekly": {
        "task": "app.tasks.celery_app.run_accuracy_gate_task",
        "schedule": crontab(hour=2, minute=30, day_of_week=1),  # 每周一 02:30
    },
}


# ── CONCERN 2.4 (Phase 24): Celery task_failure 信号接线 ──
# 失败任务此前不产生任何告警/审计——Celery 级失败对运营不可见（pipeline 由
# cron_scheduler 串行驱动，stage 失败仅靠 run 级 status，任务级异常静默）。
# 接线：task_failure → audit_events (celery_task_failure) + loguru 告警。

from celery import signals  # noqa: E402


def _on_task_failure(
    task_id: str,
    task_name: str,
    exception: BaseException,
    **kwargs: Any,
) -> None:
    """Celery task failure handler — surface to audit_events + logger."""
    try:
        from app.utils.audit import AuditEntry, AuditEvent, audit_log

        audit_log(
            AuditEntry(
                event=AuditEvent.CELERY_TASK_FAILURE,
                actor="celery",
                action=f"task_failure:{task_name}",
                detail=f"task_id={task_id} error={exception!r}",
                extra={"task_id": task_id, "task_name": task_name},
            )
        )
    except Exception:
        logger.opt(exception=True).warning(
            "task_failure audit write failed (non-fatal): task={} id={}",
            task_name, task_id,
        )
    logger.error(
        "Celery task FAILED: name={} id={} exc={!r}",
        task_name, task_id, exception,
    )


if getattr(celery_app, "task_failure_handler_registered", False) is False:
    signals.task_failure.connect(_on_task_failure)
    celery_app.task_failure_handler_registered = True


@celery_app.task(name="app.tasks.celery_app.run_accuracy_gate", bind=True, max_retries=1)
def run_accuracy_gate_task(self) -> dict[str, Any]:
    """赛项三项 ≥90% 指标定时评测 + 劣化告警（Phase 2）。

    每周跑一次 accuracy_gate.py（规则 baseline，无 LLM 依赖），
    任一指标 < 0.90 时写 audit 告警（CELERY_TASK_FAILURE 同级，
    让运营在审计日志里看到"指标劣化"）。结果落 loguru。

    真实 LLM 评测（run_resume_eval / run_real_eval）需凭据且慢，
    由人工/CI 按需跑；本任务用规则 baseline 做每周回归防线。
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent.parent
    gate_script = root / "evaluation" / "accuracy_gate.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(gate_script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        logger.info("accuracy_gate output:\n{}", output[-2000:])
        if proc.returncode != 0:
            # 指标劣化 → 写审计告警
            try:
                from app.utils.audit import AuditEntry, AuditEvent, audit_log

                audit_log(
                    AuditEntry(
                        event=AuditEvent.CELERY_TASK_FAILURE,
                        actor="celery",
                        action="accuracy_gate_degraded",
                        detail=f"赛项指标门禁未达标 exit={proc.returncode}",
                        extra={"output": output[-1500:]},
                    )
                )
            except Exception:
                logger.exception("accuracy_gate audit write failed (non-fatal)")
            logger.error("赛项指标门禁未达标（≥90%），需人工核查: {}", output[-800:])
            return {"passed": False, "exit_code": proc.returncode}
        return {"passed": True, "exit_code": 0}
    except subprocess.TimeoutExpired:
        logger.error("accuracy_gate 超时（1800s）")
        return {"passed": False, "error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("accuracy_gate task error: {}", exc)
        return {"passed": False, "error": str(exc)}
