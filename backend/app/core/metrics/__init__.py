"""Shared metric module — single source of truth for cross-module KPIs.

D1+D2 fix: previously `weekly_new_nodes` was computed in two places
(dashboard_service.py uses week_start=Mon, quality.py uses trailing-7d) and
`trust_score` was computed in three places (Neo4j avg, extraction-confidence
blend, source-count blend). All consumers now route through this module to
guarantee cross-page consistency.

Consumers:
- AdminOverview (4 KPIs) via dashboard.fetchOverview()
- DataDashboard via the same
- QualityDashboard via _build_quality_dashboard
- /admin/stats legacy endpoint
- Future analytics / reports
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_models import PositionRecord, SkillRecord


class WeeklyNewNodes(NamedTuple):
    """Single source of truth for "nodes added this week" KPI.

    Window: Mon 00:00 UTC of the current week → now (matches the meaning of
    "本周" in Chinese). Skill uses `first_detected_at`, position uses
    `created_at` (their respective birth timestamps).
    """

    skills: int
    positions: int
    total: int
    week_start: datetime


def compute_week_start(now: datetime | None = None) -> datetime:
    """Monday 00:00 UTC of the current week. Single definition used everywhere."""
    now = now or datetime.now(UTC)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def weekly_new_nodes(session: AsyncSession, *, now: datetime | None = None) -> WeeklyNewNodes:
    """Single canonical computation for "本周新增节点" KPI.

    Replaces duplicate SQL in:
    - dashboard_service._fetch_pipeline_stats (was: also trailing-7d form)
    - quality._build_quality_dashboard (still on trailing-7d)
    """
    week_start = compute_week_start(now)
    skills = (
        await session.execute(
            sa.select(sa.func.count())
            .select_from(SkillRecord)
            .where(SkillRecord.first_detected_at >= week_start)
        )
    ).scalar() or 0
    positions = (
        await session.execute(
            sa.select(sa.func.count())
            .select_from(PositionRecord)
            .where(PositionRecord.created_at >= week_start)
        )
    ).scalar() or 0
    return WeeklyNewNodes(
        skills=int(skills),
        positions=int(positions),
        total=int(skills) + int(positions),
        week_start=week_start,
    )


async def avg_skill_trust() -> float:
    """Single canonical computation for "平均信任度" KPI.

    Reads Neo4j `Skill.trust_score` (the entity trust property set by
    `_sync_neo4j_on_audit` on approve/reject). Returns 0.0 if Neo4j is
    unreachable. Frontend multiplies by 100 for %.
    """
    try:
        from app.services.resources import init_resources  # noqa: PLC0415
        resources = await init_resources()
        driver = resources.neo4j_driver
        if driver is None:
            logger.warning("avg_skill_trust: Neo4j driver not available")
            return 0.0
        async with driver.session() as session:
            result = await session.run(
                "MATCH (sk:Skill) WHERE sk.trust_score IS NOT NULL "
                "RETURN avg(sk.trust_score) AS avg_trust"
            )
            record = await result.single()
            val = float(record["avg_trust"]) if record and record["avg_trust"] is not None else None
        return round(val or 0.0, 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("avg_skill_trust fetch failed, fallback to 0: {}", exc)
        return 0.0


async def match_trust_score(matched_skills: list[str]) -> float | None:
    """Compute trust_score for a MatchResponse.

    Returns the MIN of `matched_skills`' Neo4j trust_score — the bottleneck
    skill's trust determines the overall trustworthiness of the match.
    Returns None if matched_skills is empty or Neo4j is unreachable.

    Used by services/match_service.py to populate the new `trust_score`
    field in MatchResponse (D6 fix).
    """
    if not matched_skills:
        return None
    try:
        from app.services.resources import init_resources  # noqa: PLC0415
        resources = await init_resources()
        driver = resources.neo4j_driver
        if driver is None:
            return None
        async with driver.session() as session:
            result = await session.run(
                "MATCH (sk:Skill) WHERE sk.name IN $names AND sk.trust_score IS NOT NULL "
                "RETURN sk.trust_score AS ts",
                names=matched_skills,
            )
            scores = [float(rec["ts"]) async for rec in result]
        return round(min(scores), 4) if scores else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("match_trust_score lookup failed: {}", exc)
        return None

