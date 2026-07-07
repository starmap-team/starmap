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
from app.models.pipeline_models import PipelineSchedule

# Try to use croniter; fall back to simple interval parser if not installed
try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False
    logger.warning("croniter not installed, using fallback cron parser")


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
        except Exception as exc:
            logger.warning("Fallback cron parse failed: {}", exc)
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
    """Trigger a single schedule: run pipeline, update last_run_at + next_run_at.

    Returns True if trigger was dispatched successfully.
    """
    try:
        from app.tasks.celery_app import scheduled_pipeline_run as celery_task

        # Dispatch to Celery
        celery_task.delay(str(schedule.id))

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
    except Exception as exc:
        logger.error("Failed to trigger schedule '{}': {}", schedule.name, exc)
        return False


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
    """
    logger.info("Cron scanner loop started (interval={}s)", interval_seconds)
    engine = get_async_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    while True:
        try:
            async with session_factory() as session:
                triggered = await cron_scanner_once(session)
                if triggered:
                    logger.info("Cron scanner triggered {} schedule(s)", triggered)
        except Exception as exc:
            logger.error("Cron scanner iteration failed: {}", exc)
        await asyncio.sleep(interval_seconds)
