"""Evolution service layer — business logic extracted from evolution.py API routes.

P1-4 fix: routes should be thin; heavy orchestration (EmergenceFinder, Cypher queries,
SQL joins, CII calculations) belongs here.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.causal_inference import (
    skill_position_associations,  # noqa: F401 — §7.6 轻量版 re-export (路由经 service 访问 core)
)
from app.core.evolution.emergence_finder import EmergenceFinder
from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.core.evolution.trust_scorer import (
    LOW_TRUST_THRESHOLD,  # noqa: F401 — 低信任度阈值 re-export (路由经 service 访问 core)
)
from app.core.evolution.write_back import (  # noqa: F401 — 审核即生效写回 re-export (路由经 service 访问 core)
    write_back_changelog_row,
)
from app.core.matching.constants import SENIOR_KEYWORDS  # noqa: F401 — 职级关键词 re-export (路由经 service 访问 core)
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

 # Build trend items — ALL skills (no [:20] silent truncation: the overview
 # table + CII chart must reflect the full trend set the user sees in KPI)
    items: list[dict[str, Any]] = []
    for name, data in skill_data.items():
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


async def build_evolution_kpi(
    session: AsyncSession,
    *,
    days: int = 90,
) -> dict[str, Any]:
    """Build the 4-KPI row for the evolution dashboard (D-11).

    - emerging_count: number of emerging+rising skills — SAME full-history
      emergence scan as /evolution/emerging-alerts, so the KPI matches the
      visible 预警表 (previously a 90 天窗口 scan → 8 vs 11 口径漂移).
    - trust_mean:     real aggregate avg(EvolutionChangelog.trust_score)
    - cii_mean:       mean of each skill's latest CII point over the days
      window (matches the 趋势概览 chart), baseline 100 口径.
    - alert_count:    non-stable signals count (emerging + rising + declining)
      from the SAME full-history scan as the 预警表.

    Empty data returns zero values, never fabricated estimates (D-12).
    """
    from app.models.evolution_models import EvolutionChangelog

 # 1/4. Emergence-derived KPIs — full-history scan (same as emerging-alerts)
    full_skill_data = await load_skill_timeseries_data(session)
    emerging_count = 0
    alert_count = 0
    if full_skill_data:
        finder = EmergenceFinder()
        report = finder.scan(full_skill_data)
        emerging_count = len(report.emerging) + len(report.rising)
        alert_count = len(report.emerging) + len(report.rising) + len(report.declining)

 # 2. Trust mean — real aggregate over the changelog table (: no placeholder)
    trust_result = await session.execute(
        sa.select(sa.func.avg(EvolutionChangelog.trust_score))
    )
    trust_value = trust_result.scalar_one()
    # 2026-08-21 (debug 修复): 空表时返回 None（前端显示"—"）而非 0.0 ——
    # 用户看到"信任均值 0%"误以为评分全为 0，实为 changelog 无记录。
    trust_mean = round(float(trust_value), 3) if trust_value is not None else None

 # 3. CII mean — days window (matches the 趋势概览 chart), avg of last points
    skill_data = await load_skill_timeseries_data(session, days=days)
    cii_last_points: list[float] = []
    for data in skill_data.values():
        points = _calculate_cii_points(data)
        if points:
            cii_last_points.append(points[-1])
    cii_mean = round(sum(cii_last_points) / len(cii_last_points), 1) if cii_last_points else 0.0

 # D-cross: 与 /quality 平均信任度对照口径（Neo4j Skill.trust_score 实时均值）
 # 复用 quality_service.avg_skill_trust 共享指标模块，避免两处口径漂移
    from app.services.quality_service import avg_skill_trust
    try:
        trust_neo4j_skill = round(float(await avg_skill_trust()), 3)
    except Exception:
        trust_neo4j_skill = 0.0

    return {
        "emerging_count": emerging_count,
        "trust_mean": trust_mean,
        "trust_mean_neo4j_skill": trust_neo4j_skill,
        "cii_mean": cii_mean,
        "alert_count": alert_count,
        "days": days,
    }


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
