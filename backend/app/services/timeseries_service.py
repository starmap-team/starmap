"""Timeseries aggregation service — refresh skill_timeseries from JDExtractionRecord.

Replaces the old seed_skill_timeseries script with a real data-driven approach:
  JDExtractionRecord → monthly window aggregation → SkillTimeseries upsert

Called by the pipeline `timeseries` stage (after graph_sync) and can also be
invoked manually via admin endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import SkillTimeseries
from app.models.extraction_models import JDExtractionRecord, SkillRecord


async def refresh_skill_timeseries(session: AsyncSession) -> dict[str, Any]:
    """Aggregate skill frequencies from JDExtractionRecord into SkillTimeseries.

    Strategy:
      1. Query all completed JDExtractionRecords, grouped by month + skill name.
      2. For each (skill, month) pair, count JDs mentioning that skill.
      3. Upsert into skill_timeseries (delete-then-insert per skill to avoid stale data).

    Returns:
        {"skills_updated": int, "windows_created": int}
    """
 # ── Step 1: Find the date range of extraction records ──
    range_stmt = sa.select(
        sa.func.min(JDExtractionRecord.created_at),
        sa.func.max(JDExtractionRecord.created_at),
    ).where(JDExtractionRecord.status == "completed")

    range_result = await session.execute(range_stmt)
    min_date, max_date = range_result.one()

    if min_date is None:
        logger.info("refresh_skill_timeseries: no completed extraction records, skipping")
        return {"skills_updated": 0, "windows_created": 0}

 # ── Step 2: Build monthly windows covering the date range ──
    windows = _build_monthly_windows(min_date, max_date)

 # ── Step 3: Load skill→category mapping from skill_records ──
    cat_result = await session.execute(sa.select(SkillRecord.name, SkillRecord.category))
 # cat_result.all() returns Sequence[Row[tuple[str, str]]], cast to Iterable[tuple[str, str]]
    skill_categories: dict[str, str] = dict(cat_result.all())  # type: ignore[arg-type]

 # ── Step 4: Aggregate per (skill, month) ──
 # Extracted_skills is JSON — can be list[dict] or dict with required/preferred keys.
 # We use PostgreSQL jsonb_array_elements to unnest skill names.
 # Fallback: Python-side aggregation for databases that don't support the function.

    skills_updated = 0
    windows_created = 0

    for window_start, window_end in windows:
 # Fetch records in this window
        stmt = (
            sa.select(JDExtractionRecord)
            .where(JDExtractionRecord.status == "completed")
            .where(JDExtractionRecord.created_at >= window_start)
            .where(JDExtractionRecord.created_at < window_end)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        if not records:
            continue

 # Python-side aggregation: count skill mentions and collect positions
        skill_counts: dict[str, int] = {}
        skill_positions: dict[str, set[str]] = {}

        for rec in records:
            skills = _extract_skill_names(rec)
            for skill_name in skills:
                skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1
                if rec.job_title:
                    skill_positions.setdefault(skill_name, set()).add(rec.job_title)

        if not skill_counts:
            continue

 # ── Step 5: Upsert into skill_timeseries ──
 # Delete existing records for this window, then insert fresh ones.
        await session.execute(
            sa.delete(SkillTimeseries).where(
                SkillTimeseries.window_start == window_start,
                SkillTimeseries.window_end == window_end,
            )
        )

        for skill_name, frequency in skill_counts.items():
            category = skill_categories.get(skill_name, "general")
            positions = sorted(skill_positions.get(skill_name, set()))[:20]  # cap at 20

            ts_record = SkillTimeseries(
                skill_name=skill_name,
                window_start=window_start,
                window_end=window_end,
                frequency=frequency,
                source_count=len(records),
                positions=positions,
                category=category,
            )
            session.add(ts_record)
            windows_created += 1

        skills_updated += len(skill_counts)

    await session.flush()

    logger.info(
        "refresh_skill_timeseries: {} skills updated, {} windows created ({} to {})",
        skills_updated,
        windows_created,
        min_date.date(),
        max_date.date(),
    )
    return {"skills_updated": skills_updated, "windows_created": windows_created}


def _build_monthly_windows(
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Generate (window_start, window_end) pairs for each month in [start, end]."""
    windows: list[tuple[datetime, datetime]] = []
    current = datetime(start.year, start.month, 1, tzinfo=UTC)
    end_boundary = datetime(end.year, end.month, 1, tzinfo=UTC) + timedelta(days=32)
    end_boundary = datetime(end_boundary.year, end_boundary.month, 1, tzinfo=UTC)

    while current < end_boundary:
        next_month = datetime(
            current.year + (1 if current.month == 12 else 0),
            1 if current.month == 12 else current.month + 1,
            1,
            tzinfo=UTC,
        )
        windows.append((current, next_month))
        current = next_month

    return windows


def _extract_skill_names(record: JDExtractionRecord) -> list[str]:
    """Extract normalized skill name list from a JDExtractionRecord.

    Handles both list[dict] and dict{required/preferred} JSON shapes.
    """
    raw = record.extracted_skills
    if not raw:
        return []

    names: list[str] = []

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    names.append(str(name))
            elif isinstance(item, str):
                names.append(item)
    elif isinstance(raw, dict):
        for key in ("required_skills", "preferred_skills", "skills"):
            val = raw.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        name = item.get("name")
                        if name:
                            names.append(str(name))
                    elif isinstance(item, str):
                        names.append(item)

    return names
