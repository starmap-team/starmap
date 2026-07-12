"""岗位管理 API — 接入 PostgreSQL position_records。"""
from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

router = APIRouter(prefix="/positions", tags=["岗位管理"])


# P2 修复 (INJ-03): 转义 SQL LIKE 通配符，防止通配符注入
def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards (% and _) in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SkillNode(BaseModel):
    """岗位所需技能骨架。"""
    skill_id: str = Field(..., description="技能唯一标识")
    name: str = Field(..., description="技能名称")
    category: str = Field(..., description="技能分类")
    confidence: float = Field(default=1.0, ge=0, le=1, description="置信度")
    source_count: int = Field(default=0, ge=0, description="来源文档计数")


class PositionNode(BaseModel):
    """契约中的 PositionNode。"""
    position_id: str = Field(..., description="岗位唯一标识")
    name: str = Field(..., description="岗位名称")
    industry: str = Field(..., description="所属行业")
    description: str = Field(..., description="岗位描述")
    skills_required: list[SkillNode] = Field(default_factory=list, description="岗位所需技能")
    discovered_at: str | None = Field(default=None, description="发现时间")


class PositionListResponse(BaseModel):
    """岗位列表响应。"""
    items: list[PositionNode] = Field(default_factory=list, description="岗位列表")
    total: int = Field(default=0, ge=0, description="岗位总数")
    page: int = Field(default=1, ge=1, description="当前页")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


@router.get(
    "",
    summary="岗位列表",
    description="返回岗位列表，支持分页、行业筛选和关键词搜索。",
    response_model=PositionListResponse,
)
async def list_positions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    industry: Annotated[str | None, Query(description="行业筛选")] = None,
    search: Annotated[str | None, Query(description="搜索关键词")] = None,
) -> PositionListResponse:
    # Count total
    count_stmt = sa.select(sa.func.count()).select_from(PositionRecord)
    if industry:
        count_stmt = count_stmt.where(PositionRecord.industry == industry)
    if search:
        count_stmt = count_stmt.where(PositionRecord.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    total = (await session.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = sa.select(PositionRecord).order_by(PositionRecord.name)
    if industry:
        stmt = stmt.where(PositionRecord.industry == industry)
    if search:
        stmt = stmt.where(PositionRecord.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()

    items: list[PositionNode] = []
    for r in rows:
        # Fetch skills for this position
        skill_stmt = (
            sa.select(SkillRecord, PositionSkillRelation)
            .join(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
            .where(PositionSkillRelation.position_id == r.id)
        )
        skill_rows = (await session.execute(skill_stmt)).all()
        skills = [
            SkillNode(
                skill_id=str(sk.id),
                name=sk.name,
                category=sk.category,
                confidence=float(rel.confidence or 1.0),
                source_count=sk.source_count or 0,
            )
            for sk, rel in skill_rows
        ]
        items.append(PositionNode(
            position_id=str(r.id),
            name=r.name or "",
            industry=r.industry or "",
            description=r.description or "",
            skills_required=skills,
            discovered_at=r.created_at.isoformat() if r.created_at else None,
        ))

    return PositionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{position_id}",
    summary="岗位详情",
    description="返回单个岗位详情及其技能关系。",
)
async def get_position(
    position_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    import uuid as uuid_mod

    from fastapi import HTTPException

    r = None

    # 尝试按 UUID 查询（仅当 ID 看起来像 UUID 时）
    if len(position_id) >= 32:
        try:
            uuid_val = uuid_mod.UUID(position_id)
            stmt = sa.select(PositionRecord).where(PositionRecord.id == uuid_val)
            r = (await session.execute(stmt)).scalar_one_or_none()
        except (ValueError, Exception):
            pass  # 非 UUID 格式，跳过

    # 尝试按名称查询
    if r is None:
        stmt = sa.select(PositionRecord).where(PositionRecord.name == position_id)
        r = (await session.execute(stmt)).scalar_one_or_none()

    if r is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")

    skill_stmt = (
        sa.select(SkillRecord, PositionSkillRelation)
        .join(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
        .where(PositionSkillRelation.position_id == r.id)
    )
    skill_rows = (await session.execute(skill_stmt)).all()
    skills = [
        {
            "skill_id": str(sk.id),
            "name": sk.name,
            "category": sk.category,
            "confidence": float(rel.confidence or 1.0),
            "source_count": sk.source_count or 0,
        }
        for sk, rel in skill_rows
    ]
    return {
        "position_id": str(r.id),
        "name": r.name,
        "industry": r.industry,
        "description": r.description,
        "skills_required": skills,
        "discovered_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.post("/discover", summary="触发岗位发现流程")
async def discover_position(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """触发新兴岗位发现：基于技能频率 Z-score 检测。

    从 skill_timeseries 表加载历史频率数据，
    然后运行 EmergenceFinder 进行 Z-score 分析。
    若无时序数据则返回"数据不足"提示。
    """
    from app.core.evolution.emergence_finder import EmergenceFinder

    try:
        # Step 1: Load timeseries data for frequency history
        from app.core.evolution.timeseries_loader import load_skill_timeseries_data

        skill_data = await load_skill_timeseries_data(db)

        if not skill_data:
            return {
                "status": "insufficient_data",
                "emerging_skills": [],
                "count": 0,
                "skills_analyzed": 0,
                "message": "时序数据不足，请先执行管线以生成技能频率统计",
            }

        # Step 2: Run emergence detection
        finder = EmergenceFinder()
        report = finder.scan(skill_data)

        emerging = []
        for signal in report.emerging + report.rising:
            emerging.append({
                "skill": signal.skill_name,
                "z_score": round(signal.z_score, 2),
                "level": signal.level.value if hasattr(signal.level, 'value') else str(signal.level),
                "sources": signal.source_count,
                "positions": signal.positions,
            })

        return {
            "status": "completed",
            "emerging_skills": emerging,
            "count": len(emerging),
            "skills_analyzed": len(skill_data),
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Discovery failed: {e}") from e
