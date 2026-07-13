"""QualityRepository — quality dashboard data access layer.

Sinks raw SQL (sa.text) out of the API layer into a dedicated repository,
keeping the API handlers free of SQL string literals.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import SkillTimeseries


async def fetch_hallucination_trend(session: AsyncSession) -> list[dict[str, Any]]:
    """Fetch monthly hallucination trend from skill_timeseries data.

    Groups by month, counting low-source (<3) entries as hallucination proxies.
    Returns a list of {"date": str, "rate": float} dicts.
    """
    ts_stmt = (
        sa.select(
            sa.func.date_trunc("month", SkillTimeseries.window_start).label("month"),
            sa.func.count().label("total"),
            sa.func.sum(sa.case((SkillTimeseries.source_count < 3, 1), else_=0)).label("low_source"),
        )
        .select_from(SkillTimeseries)
        .group_by(sa.text("month"))
        .order_by(sa.text("month"))
    )
    ts_rows = (await session.execute(ts_stmt)).all()
    result: list[dict[str, Any]] = []
    for row in ts_rows:
        total = int(row.total)
        low_source = int(row.low_source)
        rate = low_source / total if total > 0 else 0.0
        result.append({
            "date": str(row.month)[:7],
            "rate": round(rate, 3),
        })
    return result
