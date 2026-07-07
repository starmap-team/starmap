"""Shared SkillTimeseries data loader.

Single canonical implementation replacing 7+ copy-pasted blocks
across evolution.py, orchestrator.py, and position.py.

ponytail: one function with keyword filters, all call sites pass their
specific filter params. Returns the standard dict shape every consumer expects.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import SkillTimeseries


async def load_skill_timeseries_data(
    session: AsyncSession,
    *,
    category: str | None = None,
    days: int | None = None,
    position_name: str | None = None,
    include_category: bool = False,
) -> dict[str, dict[str, Any]]:
    """Load SkillTimeseries grouped by skill_name, returning dict for EmergenceFinder.

    Returns dict mapping skill_name -> {
        "frequencies": list[int],   # all windows except last
        "current": int,            # last window's frequency
        "sources": int,            # source_count from first record
        "positions": list[str],    # positions from first record
        "category": str,           # included only if include_category=True
    }
    Returns empty dict if no records found.
    """
    stmt = sa.select(SkillTimeseries).order_by(SkillTimeseries.window_start.asc())

    if days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = stmt.where(SkillTimeseries.window_start >= cutoff)

    if category is not None:
        stmt = stmt.where(SkillTimeseries.category == category)

    if position_name is not None:
        stmt = stmt.where(SkillTimeseries.positions.contains([position_name]))

    result = await session.execute(stmt)
    records = result.scalars().all()

    skill_data: dict[str, dict[str, Any]] = {}
    for r in records:
        name = r.skill_name
        if name not in skill_data:
            entry: dict[str, Any] = {
                "frequencies": [],
                "current": 0,
                "sources": r.source_count,
                "positions": r.positions or [],
            }
            if include_category:
                entry["category"] = r.category
            skill_data[name] = entry
        skill_data[name]["frequencies"].append(r.frequency)

    for data in skill_data.values():
        freqs = data["frequencies"]
        if freqs:
            data["current"] = freqs[-1]
            data["frequencies"] = freqs[:-1]

    return skill_data
