"""Evolution industry-report endpoint — extracted from evolution.py (Phase 7 evolution domain split).

业务说明：行业趋势报告 API，聚合技能需求数据、时序趋势和岗位要求，提供行业总览。
注册到 evolution.py 的主 router（prefix="/evolution"），最终路径 /evolution/industry-report。
"""
from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.extraction_models import PositionRecord, PositionSkillRelation
from app.schemas.evolution import IndustryReportResponse, SkillTrendItem
from app.services.evolution_service import EmergenceFinder, load_skill_timeseries_data

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
 # EmergenceFinder 经 services 层 re-export（api → services → core）
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
 # No timeseries data — return empty trends rather than fabricating from source_count.
 # The pipeline's timeseries stage must run first to generate real frequency data.
        pass

 # Top positions by skill count
    top_pos_stmt = (
        sa.select(PositionRecord.name, sa.func.count(PositionSkillRelation.skill_id).label("skill_count"))
        .select_from(PositionRecord)
        .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
        .group_by(PositionRecord.name)
        .order_by(sa.func.count(PositionSkillRelation.skill_id).desc())
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
