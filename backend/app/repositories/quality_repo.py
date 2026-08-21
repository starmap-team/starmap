"""QualityRepository — quality dashboard data access layer.

Sinks raw SQL (sa.text) out of the API layer into a dedicated repository,
keeping the API handlers free of SQL string literals.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_models import JDExtractionRecord


async def fetch_hallucination_trend(session: AsyncSession) -> list[dict[str, Any]]:
    """Fetch hallucination trend from JDExtractionRecord.hallucination_score.

    Groups by day over the trailing 30d window, counting hallucinated records
    (hallucination_score > 0.5, same threshold as the KPI card) — unified with
    the dashboard KPI and /quality/trends instead of the old skill_timeseries
    `source_count < 3` proxy (which was a different concept and returned 0
    because all timeseries rows had source_count >= 3).

    Returns a list of {"date": str, "rate": float} dicts (rate = hallucinated / total).
    """
    cutoff = datetime.now(UTC) - timedelta(days=30)
    stmt = (
        sa.select(
            sa.func.date_trunc("day", JDExtractionRecord.created_at).label("day"),
            sa.func.count().label("total"),
            sa.func.sum(sa.case(
                (JDExtractionRecord.hallucination_score > 0.5, 1),
                else_=0,
            )).label("hallucinated"),
        )
        .select_from(JDExtractionRecord)
        .where(JDExtractionRecord.created_at >= cutoff)
        .group_by(sa.text("day"))
        .order_by(sa.text("day"))
    )
    rows = (await session.execute(stmt)).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        total = int(row[1])
        hallucinated = int(row[2])
        rate = hallucinated / total if total > 0 else 0.0
        result.append({
            "date": str(row[0])[:10],
            "rate": round(rate, 3),
        })
    return result
