"""Evolution industry-report endpoint — extracted from evolution.py (Phase 7 evolution domain split).

业务说明：行业趋势报告 API，聚合技能需求数据、时序趋势和岗位要求，提供行业总览。
注册到 evolution.py 的主 router（prefix="/evolution"），最终路径 /evolution/industry-report。
"""
from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.dependencies import get_db_session
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord


class SkillTrendItem(BaseModel):
    """Skill trend in industry report."""

    skill_name: str
    trend: str  # rising | stable | declining
    frequency: int = 0
    source_count: int = 0
    related_positions: list[str] = Field(default_factory=list)


class IndustryReportResponse(BaseModel):
    """Industry trend report response."""

    total_skills: int = 0
    rising_skills: list[SkillTrendItem] = Field(default_factory=list)
    declining_skills: list[SkillTrendItem] = Field(default_factory=list)
    stable_skills: list[SkillTrendItem] = Field(default_factory=list)
    top_positions: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


router = APIRouter(tags=["行业报告"])


@router.get("/industry-report", response_model=IndustryReportResponse)
async def get_industry_report(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    category: Annotated[str | None, Query(description="技能分类筛选")] = None,
) -> IndustryReportResponse:
    """Get industry trend report with skill demand changes.

    Aggregates skill frequency data, timeseries trends, and position
    requirements to provide a comprehensive industry overview.
    """
    # Get skill trends from timeseries data
    skill_data = await load_skill_timeseries_data(session, category=category)

    # If we have timeseries data, use emergence detection
    rising: list[SkillTrendItem] = []
    declining: list[SkillTrendItem] = []
    stable: list[SkillTrendItem] = []

    if skill_data:
        from app.core.evolution.emergence_finder import EmergenceFinder

        # skill_data already has the right shape for EmergenceFinder
        finder = EmergenceFinder()
        report = finder.scan(skill_data)

        for signal in report.rising:
            rising.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="rising",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))

        for signal in report.declining:
            declining.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="declining",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))

        for signal in report.stable[:20]:
            stable.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="stable",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))
    else:
        # Fallback: use SkillRecord for basic stats
        fallback_stmt = (
            sa.select(SkillRecord.name, SkillRecord.source_count, SkillRecord.category)
            .order_by(SkillRecord.source_count.desc())
            .limit(50)
        )
        if category:
            fallback_stmt = fallback_stmt.where(SkillRecord.category == category)

        fallback_result = await session.execute(fallback_stmt)
        fallback_records = fallback_result.all()

        for name, source_count, _cat in fallback_records:
            # Get positions for this skill
            pos_stmt = (
                sa.select(PositionRecord.name)
                .select_from(PositionSkillRelation)
                .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(SkillRecord.name == name)
                .limit(10)
            )
            pos_result = await session.execute(pos_stmt)
            positions = [row[0] for row in pos_result.all()]

            trend = "rising" if source_count > 5 else "declining" if source_count < 2 else "stable"
            item = SkillTrendItem(
                skill_name=name,
                trend=trend,
                frequency=source_count,
                source_count=source_count,
                related_positions=positions,
            )
            if trend == "rising":
                rising.append(item)
            elif trend == "declining":
                declining.append(item)
            else:
                stable.append(item)

    # Top positions by skill count
    top_pos_stmt = (
        sa.select(PositionRecord.name, sa.func.count(PositionSkillRelation.skill_id).label("skill_count"))
        .select_from(PositionRecord)
        .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
        .group_by(PositionRecord.name)
        .order_by(sa.text("skill_count DESC"))
        .limit(10)
    )
    top_pos_result = await session.execute(top_pos_stmt)
    top_positions = [
        {"position": name, "skill_count": count}
        for name, count in top_pos_result.all()
    ]

    # Generate summary
    total = len(rising) + len(declining) + len(stable)
    summary_parts = []
    if rising:
        summary_parts.append(f"{len(rising)} 个技能呈上升趋势")
    if declining:
        summary_parts.append(f"{len(declining)} 个技能呈下降趋势")
    summary_parts.append(f"共跟踪 {total} 个技能")
    summary = "，".join(summary_parts) + "。"

    return IndustryReportResponse(
        total_skills=total,
        rising_skills=rising[:20],
        declining_skills=declining[:20],
        stable_skills=stable[:20],
        top_positions=top_positions,
        summary=summary,
    )
