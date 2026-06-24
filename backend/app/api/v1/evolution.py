"""演化分析 API。对应§5.2 能力更新 + §7.3 岗位演进。"""
from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.tasks.celery_app import analyze_evolution_trends

router = APIRouter(prefix="/evolution", tags=["演化分析"])


class EvolutionTrend(BaseModel):
    """技能趋势条目。"""

    skill_name: str = Field(..., description="技能名称")
    trend: str = Field(..., description="趋势方向：rising/stable/declining")
    confidence: float = Field(..., ge=0, le=1, description="趋势置信度")
    related_positions: list[str] = Field(default_factory=list, description="相关岗位")


class EvolutionTrendsResponse(BaseModel):
    """演化趋势响应。"""

    items: list[EvolutionTrend] = Field(default_factory=list, description="趋势列表")


@router.get("/trends", response_model=EvolutionTrendsResponse)
async def get_trends(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    category: Annotated[str | None, Query(description="技能分类筛选")] = None,
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
) -> EvolutionTrendsResponse:
    """技能热度趋势、岗位变迁时间线、新兴岗位预警（§8.3 演化看板）。"""
    _ = days

    stmt = (
        sa.select(SkillRecord.name, SkillRecord.source_count, PositionRecord.name)
        .select_from(SkillRecord)
        .outerjoin(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
        .outerjoin(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
        .order_by(SkillRecord.source_count.desc(), SkillRecord.name.asc())
        .limit(200)
    )
    if category:
        stmt = stmt.where(SkillRecord.category == category)

    rows = (await session.execute(stmt)).all()
    grouped: dict[str, tuple[int, list[str]]] = {}
    for skill_name, source_count, position_name in rows:
        count, positions = grouped.setdefault(skill_name, (int(source_count or 0), []))
        if position_name and position_name not in positions:
            positions.append(position_name)
        grouped[skill_name] = (count, positions)

    items: list[EvolutionTrend] = []
    for name, (count, related_positions) in list(grouped.items())[:20]:
        trend = "rising" if count >= 5 else "stable"
        confidence = min(1.0, 0.5 + count / 20)
        items.append(
            EvolutionTrend(
                skill_name=name,
                trend=trend,
                confidence=confidence,
                related_positions=related_positions,
            )
        )

    return EvolutionTrendsResponse(items=items)


@router.post("/analyze")
async def analyze_evolution(
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
):
    """触发演化分析流程。"""
    task = analyze_evolution_trends.delay(days)
    return {"message": "queued", "task_id": task.id, "days": days}
