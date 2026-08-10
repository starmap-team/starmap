"""Cron scheduler module (Phase 2 CRON-01 ~ CRON-05).

Provides:
- compute_next_cron: Parse cron expression and compute next trigger time
- scan_due_schedules: Find and trigger due schedules
- cron_scanner_loop: Infinite loop running every 60 seconds

Uses croniter for cron expression parsing (pure Python, no new service dependencies).
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_async_engine
from app.exceptions import StarMapError
from app.models.pipeline_models import PipelineSchedule

# Try to use croniter; fall back to simple interval parser if not installed
try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False
    logger.warning("croniter not installed, using fallback cron parser")


# Module-level constants
RECONCILE_INTERVAL = timedelta(hours=24)


def compute_next_cron(cron_expression: str, base: datetime | None = None) -> datetime | None:
    """Compute the next trigger datetime from a cron expression.

    Supports standard 5-field cron expressions (min hour dom mon dow).
    Returns None if parsing fails.
    """
    if HAS_CRONITER:
        try:
            base = base or datetime.now(UTC)
            cron = croniter(cron_expression, base)
            return cron.get_next(datetime)
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to parse cron expression '{}': {}", cron_expression, exc)
            return None
    else:
        # Fallback: parse "0 */N * * *" or "*/N * * * *" style
        try:
            base = base or datetime.now(UTC)
            parts = cron_expression.strip().split()
            if len(parts) != 5:
                return None
            # Simple fallback: return base + 1 hour
            return base + timedelta(hours=1)
        except StarMapError:
            raise
        except Exception:
            logger.exception("Fallback cron parse failed")
            return None


async def scan_due_schedules(session: AsyncSession) -> list[PipelineSchedule]:
    """Find all enabled schedules whose next_run_at <= now()."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(PipelineSchedule)
        .where(PipelineSchedule.enabled == True)  # noqa: E712
        .where(PipelineSchedule.next_run_at <= now)
    )
    return list(result.scalars().all())


async def trigger_schedule(
    session: AsyncSession,
    schedule: PipelineSchedule,
) -> bool:
    """Trigger a single schedule: dispatch to Celery, update timestamps.

    BUG-16 fix: dispatch by schedule name. Previously every schedule was
    funneled through `scheduled_pipeline_run` regardless of name, which
    meant non-pipeline schedules (e.g. `daily_reconcile`) would either
    fail silently or do nothing useful. Now we route by name to the
    appropriate Celery task.
    """
    try:
        # BUG-16 fix: name-based dispatch
        if schedule.name in ("daily_reconcile", "graph_reconcile"):
            from app.tasks.celery_app import reconcile_graph_task  # type: ignore[attr-defined]
            task = reconcile_graph_task
        else:
            from app.tasks.celery_app import scheduled_pipeline_run as task

        # Dispatch to Celery
        task.delay(str(schedule.id))

        # Update timestamps
        schedule.last_run_at = datetime.now(UTC)
        next_run = compute_next_cron(schedule.cron_expression, schedule.last_run_at)
        schedule.next_run_at = next_run or schedule.last_run_at + timedelta(hours=1)

        await session.flush()
        logger.info(
            "Triggered schedule '{}' (id={}). Next run at: {}",
            schedule.name, schedule.id, schedule.next_run_at,
        )
        return True
    except StarMapError:
        raise
    except Exception:
        logger.exception("Failed to trigger schedule '{}'", schedule.name)
        return False


async def _run_daily_reconcile(session: AsyncSession) -> None:
    """BUG-16 fix: extract reconcile logic so both cron and the manual endpoint
    share one implementation. Runs GraphProjector.reconcile_all and writes an
    audit event so Tab 7 数据源诊断 reports an accurate "last reconcile" time.
    """
    from app.services.graph_projector import GraphProjector
    from app.services.resources import init_resources

    resources = await init_resources()
    if not resources.neo4j_driver:
        logger.warning("daily_reconcile skipped: Neo4j unavailable")
        return

    projector = GraphProjector(resources.neo4j_driver)
    result = await projector.reconcile_all(session)
    logger.info(
        "Daily reconcile: positions/skills upserted={}, orphans_pruned={}",
        result.nodes_upserted,
        result.orphans_pruned,
    )

    # Write audit event for health monitoring
    try:
        import uuid as _uuid

        from sqlalchemy import text as _text

        from app.db.session import get_session_factory

        now = datetime.now(UTC)
        sm = get_session_factory()
        async with sm() as audit_session:
            await audit_session.execute(
                _text("""
                    INSERT INTO audit_events (id, event, actor, action, detail, ip, entity_type, entity_id, created_at)
                    VALUES (:id, 'graph_reconcile', 'cron_scanner', 'daily_reconcile',
                            :detail, '', 'graph', 'all', :now)
                """),
                {
                    "id": str(_uuid.uuid4()),
                    "detail": f"upserted={result.nodes_upserted},orphans={result.orphans_pruned}",
                    "now": now,
                },
            )
            await audit_session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit event write failed: {}", exc)


async def cron_scanner_once(session: AsyncSession) -> int:
    """Single scan iteration: find and trigger due schedules.

    Returns count of triggered schedules.
    """
    due = await scan_due_schedules(session)
    triggered = 0
    for schedule in due:
        ok = await trigger_schedule(session, schedule)
        if ok:
            triggered += 1
    await session.commit()
    return triggered


async def cron_scanner_loop(interval_seconds: int = 60) -> None:
    """Infinite loop: scan and trigger due schedules every `interval_seconds`.

    Registered in app.main.py lifespan as a background task.

    Phase 5 Step 3: 每天凌晨 3 点自动 reconcile PG → Neo4j。
    """
    from datetime import UTC, datetime, timedelta

    logger.info("Cron scanner loop started (interval={}s)", interval_seconds)
    engine = get_async_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Phase 5 Step 3: 定时 reconcile 状态
    last_reconcile_at: datetime | None = None
    next_reconcile_at = datetime.now(UTC).replace(hour=3, minute=0, second=0, microsecond=0)
    if next_reconcile_at < datetime.now(UTC):
        next_reconcile_at += timedelta(days=1)

    while True:
        try:
            # Schedule trigger
            async with session_factory() as session:
                triggered = await cron_scanner_once(session)
                if triggered:
                    logger.info("Cron scanner triggered {} schedule(s)", triggered)

            # Phase 5 Step 3: 定时 reconcile
            now = datetime.now(UTC)
            if last_reconcile_at is None or now >= next_reconcile_at:
                try:

                    from app.services.graph_projector import GraphProjector
                    from app.services.resources import init_resources
                    resources = await init_resources()
                    if resources.neo4j_driver:
                        async with session_factory() as session:
                            projector = GraphProjector(resources.neo4j_driver)
                            result = await projector.reconcile_all(session)
                            logger.info(
                                "Daily reconcile: positions={}, skills={}, orphans={}",
                                result.nodes_upserted, result.nodes_upserted, result.orphans_pruned,
                            )
                            # Phase 5 Step 4: 写 audit_events 供健康度监控查询
                            try:
                                import uuid as _uuid

                                from sqlalchemy import text as _text
                                async with session_factory() as audit_session:
                                    await audit_session.execute(
                                        _text("""
                                            INSERT INTO audit_events (id, event, actor, action, detail, ip, created_at)
                                            VALUES (:id, 'graph_reconcile', 'cron_scanner', 'daily_reconcile',
                                                    :detail, '', :now)
                                        """),
                                        {
                                            "id": str(_uuid.uuid4()),
                                            "detail": f"upserted={result.nodes_upserted},orphans={result.orphans_pruned}",
                                            "now": now,
                                        },
                                    )
                                    await audit_session.commit()
                            except Exception as audit_exc:
                                logger.warning("Failed to write reconcile audit: {}", audit_exc)
                    last_reconcile_at = now
                    next_reconcile_at = now + RECONCILE_INTERVAL
                except Exception as exc:
                    logger.exception("Daily reconcile failed: {}", exc)

        except StarMapError:
            raise
        except Exception:
            logger.exception("Cron scanner iteration failed")
        await asyncio.sleep(interval_seconds)
