"""Evolution service layer — business logic extracted from evolution.py API routes.

P1-4 fix: routes should be thin; heavy orchestration (EmergenceFinder, Cypher queries,
SQL joins, CII calculations) belongs here.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.causal_inference import skill_position_associations  # noqa: F401 — §7.6 轻量版 re-export (路由经 service 访问 core)
from app.core.evolution.emergence_finder import EmergenceFinder
from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord


def _build_signals_by_name(report: Any) -> dict[str, Any]:
    """Build a lookup dict from EmergenceFinder report signals."""
    signals_by_name: dict[str, Any] = {}
    for s in report.emerging + report.rising + report.declining:
        signals_by_name.setdefault(s.skill_name, s)
    for s in report.stable:
        signals_by_name.setdefault(s.skill_name, s)
    return signals_by_name


def _calculate_cii_points(data: dict[str, Any]) -> list[float]:
    """Normalize skill frequencies to CII scale (baseline = mean of first half)."""
    all_freqs = list(data["frequencies"])
    if data.get("current"):
        all_freqs.append(data["current"])

    if len(all_freqs) >= 2:
        half = max(1, len(all_freqs) // 2)
        baseline = sum(all_freqs[:half]) / half
        return [(f / baseline * 100) if baseline > 0 else 100.0 for f in all_freqs]
    return [100.0]


async def build_evolution_trends(
    session: AsyncSession,
    *,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Build evolution trend items for the /evolution/trends endpoint.

    Returns a list of dicts ready to be unpacked into EvolutionTrend models.
    """
    skill_data = await load_skill_timeseries_data(session, days=days)

    if not skill_data:
        logger.info("No timeseries data found for trends in the last {} days", days)
        return []

    # Run emergence detection
    finder = EmergenceFinder()
    report = finder.scan(skill_data)
    signals_by_name = _build_signals_by_name(report)

    # Load position relations
    rel_stmt = (
        sa.select(SkillRecord.name, PositionRecord.name)
        .select_from(SkillRecord)
        .outerjoin(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
        .outerjoin(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
    )
    rel_rows = (await session.execute(rel_stmt)).all()
    skill_positions: dict[str, list[str]] = {}
    for skill_name, pos_name in rel_rows:
        if skill_name:
            skill_positions.setdefault(skill_name, [])
            if pos_name and pos_name not in skill_positions[skill_name]:
                skill_positions[skill_name].append(pos_name)

    # Build trend items
    items: list[dict[str, Any]] = []
    for name, data in list(skill_data.items())[:20]:
        signal = signals_by_name.get(name)
        trend = signal.level.value if signal else "stable"
        # 修复 Pydantic ge=0 校验：负 z_score 会使 confidence 越界，正确 clamp 到 [0, 1]
        if signal:
            confidence = max(0.0, min(1.0, 0.5 + signal.z_score / 10))
        else:
            confidence = 0.5
        cii_points = _calculate_cii_points(data)

        items.append(
            {
                "skill_name": name,
                "trend": trend,
                "confidence": round(confidence, 3),
                "points": [round(p, 1) for p in cii_points],
                "related_positions": skill_positions.get(name, []),
            }
        )

    return items


async def build_evolution_paths(
    session: AsyncSession,
    *,
    position: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Build evolution path entries from PostgreSQL (fallback when Neo4j unavailable).

    If *position* is given, filter to paths involving that position.
    """
    from app.models.evolution_models import EvolutionPath

    stmt = sa.select(EvolutionPath)
    if position:
        stmt = stmt.where((EvolutionPath.source_position == position) | (EvolutionPath.target_position == position))
    stmt = stmt.order_by(EvolutionPath.similarity.desc()).limit(limit)

    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "source_position": r.source_position,
            "target_position": r.target_position,
            "similarity": r.similarity,
            "evidence_count": r.evidence_count,
            "skill_overlap": r.skill_overlap or [],
            "key_gaps": r.key_gaps or [],
            "trust_score": r.trust_score,
            "trend": "stable",
        }
        for r in records
    ]


async def build_emerging_skills(
    session: AsyncSession,
    *,
    level: str | None = None,
) -> list[dict[str, Any]]:
    """Build emerging skill items from timeseries data."""
    skill_data = await load_skill_timeseries_data(session)

    if not skill_data:
        return []

    finder = EmergenceFinder()
    report = finder.scan(skill_data)

    signals = report.emerging + report.rising
    if level:
        signals = [s for s in signals if s.level.value == level]

    return [
        {
            "skill_name": s.skill_name,
            "level": s.level.value,
            "z_score": s.z_score,
            "current_frequency": s.current_frequency,
            "mean_frequency": s.mean_frequency,
            "source_count": s.source_count,
            "positions": s.positions,
        }
        for s in signals
    ]
