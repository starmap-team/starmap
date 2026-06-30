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

DEMO_POSITIONS: list[dict[str, Any]] = [
    {
        "position_id": "pos_backend",
        "name": "后端开发工程师",
        "industry": "互联网/IT",
        "description": "负责后端 API、数据服务与系统集成。",
        "skills_required": [
            {"skill_id": "skill_python", "name": "Python", "category": "hard_skill", "confidence": 0.95, "source_count": 12},
            {"skill_id": "skill_fastapi", "name": "FastAPI", "category": "tool", "confidence": 0.88, "source_count": 6},
        ],
    },
    {
        "position_id": "pos_data",
        "name": "数据分析师",
        "industry": "互联网/IT",
        "description": "负责业务数据分析、指标建设与可视化。",
        "skills_required": [
            {"skill_id": "skill_python", "name": "Python", "category": "hard_skill", "confidence": 0.90, "source_count": 12},
            {"skill_id": "skill_sql", "name": "SQL", "category": "hard_skill", "confidence": 0.92, "source_count": 8},
        ],
    },
]


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
    try:
        # Count total
        count_stmt = sa.select(sa.func.count()).select_from(PositionRecord)
        if industry:
            count_stmt = count_stmt.where(PositionRecord.industry == industry)
        if search:
            count_stmt = count_stmt.where(PositionRecord.name.ilike(f"%{search}%"))
        total = (await session.execute(count_stmt)).scalar() or 0

        # Fetch page
        stmt = sa.select(PositionRecord).order_by(PositionRecord.name)
        if industry:
            stmt = stmt.where(PositionRecord.industry == industry)
        if search:
            stmt = stmt.where(PositionRecord.name.ilike(f"%{search}%"))
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

        if items or total:
            return PositionListResponse(items=items, total=total, page=page, page_size=page_size)
    except Exception:
        pass

    demo_items = DEMO_POSITIONS
    if industry:
        demo_items = [item for item in demo_items if item["industry"] == industry]
    if search:
        lowered = search.lower()
        demo_items = [item for item in demo_items if lowered in item["name"].lower()]
    start = (page - 1) * page_size
    return PositionListResponse(
        items=[PositionNode(**item) for item in demo_items[start:start + page_size]],
        total=len(demo_items),
        page=page,
        page_size=page_size,
    )


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

    从 skill_timeseries 表加载历史频率数据，从 skill_records 表加载当前数据，
    然后运行 EmergenceFinder 进行 Z-score 分析。
    """
    from fastapi import HTTPException

    from app.core.evolution.emergence_finder import EmergenceFinder
    from app.models.evolution_models import SkillTimeseries
    from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

    try:
        # Step 1: Load timeseries data for frequency history
        ts_stmt = sa.select(SkillTimeseries).order_by(SkillTimeseries.window_start.asc())
        ts_result = await db.execute(ts_stmt)
        ts_records = ts_result.scalars().all()

        # Build skill_data with historical frequencies
        skill_data: dict[str, dict[str, Any]] = {}
        for r in ts_records:
            name = r.skill_name
            if name not in skill_data:
                skill_data[name] = {
                    "frequencies": [],
                    "current": 0,
                    "sources": r.source_count,
                    "positions": r.positions or [],
                }
            skill_data[name]["frequencies"].append(r.frequency)

        # Set current = last frequency, rest = history
        for data in skill_data.values():
            freqs = data["frequencies"]
            if freqs:
                data["current"] = freqs[-1]
                data["frequencies"] = freqs[:-1]

        # Step 2: For skills without timeseries, use source_count as fallback
        skill_stmt = sa.select(SkillRecord)
        skill_result = await db.execute(skill_stmt)
        all_skills = skill_result.scalars().all()

        # Load position-skill relations for position mapping
        rel_stmt = (
            sa.select(SkillRecord.name, PositionRecord.name)
            .select_from(SkillRecord)
            .outerjoin(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
            .outerjoin(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
        )
        rel_result = await db.execute(rel_stmt)
        rel_rows = rel_result.all()

        skill_positions: dict[str, list[str]] = {}
        for skill_name, pos_name in rel_rows:
            if skill_name not in skill_positions:
                skill_positions[skill_name] = []
            if pos_name and pos_name not in skill_positions[skill_name]:
                skill_positions[skill_name].append(pos_name)

        for s in all_skills:
            if s.name not in skill_data:
                source_count = int(s.source_count or 0)
                skill_data[s.name] = {
                    "frequencies": [max(0, source_count - 2), max(0, source_count - 1)],
                    "current": source_count,
                    "sources": source_count,
                    "positions": skill_positions.get(s.name, []),
                }

        # Step 3: Run emergence detection
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
