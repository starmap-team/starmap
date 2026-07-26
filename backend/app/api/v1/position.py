"""岗位管理 API — 接入 PostgreSQL position_records，Neo4j fallback。"""
from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver
from app.exceptions import PositionNotFoundError, StarMapError
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
    name_cn: str = Field(default="", description="岗位中文名称")
    industry: str = Field(..., description="所属行业")
    description: str = Field(..., description="岗位描述")
    skills_required: list[SkillNode] = Field(default_factory=list, description="岗位所需技能")
    discovered_at: str | None = Field(default=None, description="发现时间")
    review_status: str | None = Field(default=None, description="审核状态")


class PositionListResponse(BaseModel):
    """岗位列表响应。"""
    items: list[PositionNode] = Field(default_factory=list, description="岗位列表")
    total: int = Field(default=0, ge=0, description="岗位总数")
    page: int = Field(default=1, ge=1, description="当前页")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


@router.get(
    "",
    summary="岗位列表",
    description="返回岗位列表，支持分页、行业筛选、关键词搜索和审核状态过滤。\n\n"
    "审核状态（默认 approved）：draft / pending_review / approved / rejected。\n"
    "admin 用户可传 include_all=true 查看所有状态；其他用户始终只看 approved。",
    response_model=PositionListResponse,
)
async def list_positions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    industry: Annotated[str | None, Query(description="行业筛选")] = None,
    search: Annotated[str | None, Query(description="搜索关键词")] = None,
    status: Annotated[
        str | None,
        Query(description="审核状态（默认 approved；admin + include_all=true 可查全部）"),
    ] = None,
    include_all: Annotated[
        bool,
        Query(description="admin 用：true 时不强制 status=approved"),
    ] = False,
) -> PositionListResponse:
    # Count total
    count_stmt = sa.select(sa.func.count()).select_from(PositionRecord)
    if industry:
        count_stmt = count_stmt.where(PositionRecord.industry.ilike(f"%{_escape_like(industry)}%", escape="\\"))
    if search:
        # Phase 13 一致性审计：search 同时匹配 name 与 industry（与前端 placeholder/客户端筛选及 Neo4j 路径一致）
        like = f"%{_escape_like(search)}%"
        count_stmt = count_stmt.where(
            sa.or_(
                PositionRecord.name.ilike(like, escape="\\"),
                PositionRecord.industry.ilike(like, escape="\\"),
            )
        )
    # Default visibility policy: only approved is public. Admin can override.
    effective_status = status
    if not include_all and effective_status is None:
        effective_status = "approved"
    if effective_status is not None:
        count_stmt = count_stmt.where(PositionRecord.review_status == effective_status)
    total = (await session.execute(count_stmt)).scalar() or 0

    # ── Neo4j fallback: when filtered PG count is 0, try Neo4j ──
    # This handles the case where PG has records but none match the status filter
    # (e.g., all PG positions are "pending_review" but user wants "approved").
    # Neo4j positions without explicit review_status default to "approved".
    if total == 0 and driver is not None:
        return await _list_positions_neo4j(driver, page, page_size, industry, search, effective_status)

    # Fetch page
    stmt = sa.select(PositionRecord).order_by(PositionRecord.name)
    if industry:
        stmt = stmt.where(PositionRecord.industry.ilike(f"%{_escape_like(industry)}%", escape="\\"))
    if search:
        like = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            sa.or_(
                PositionRecord.name.ilike(like, escape="\\"),
                PositionRecord.industry.ilike(like, escape="\\"),
            )
        )
    if effective_status is not None:
        stmt = stmt.where(PositionRecord.review_status == effective_status)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()

    # Batch-fetch skills for all positions on this page (avoids N+1)
    position_ids = [r.id for r in rows]
    skill_map: dict[Any, list[SkillNode]] = {}
    if position_ids:
        skill_stmt = (
            sa.select(SkillRecord, PositionSkillRelation)
            .join(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
            .where(PositionSkillRelation.position_id.in_(position_ids))
        )
        skill_rows = (await session.execute(skill_stmt)).all()
        for sk, rel in skill_rows:
            skill_map.setdefault(rel.position_id, []).append(SkillNode(
                skill_id=str(sk.id),
                name=sk.name,
                category=sk.category,
                confidence=float(rel.confidence or 1.0),
                source_count=sk.source_count or 0,
            ))

    items: list[PositionNode] = []
    for r in rows:
        items.append(PositionNode(
            position_id=str(r.id),
            name=r.name or "",
            name_cn=getattr(r, "name_cn", "") or "",
            industry=r.industry or "",
            description=r.description or "",
            skills_required=skill_map.get(r.id, []),
            discovered_at=r.created_at.isoformat() if r.created_at else None,
            review_status=getattr(r, "review_status", None),
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
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> dict[str, Any]:
    import uuid as uuid_mod

    from fastapi import HTTPException

    r = None

    # 尝试按 UUID 查询（仅当 ID 包含连字符的 UUID 或纯 hex 格式时）
    if len(position_id) >= 32 and (len(position_id) <= 36):
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

    # PostgreSQL hit — return with skills
    if r is not None:
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
                "proficiency": "精通" if rel.requirement_type == "required" else "了解" if rel.requirement_type == "preferred" else "熟悉",
                "confidence": float(rel.confidence or 1.0),
                "source_count": sk.source_count or 0,
            }
            for sk, rel in skill_rows
        ]
        return {
            "position_id": str(r.id),
            "name": r.name,
            "name_cn": getattr(r, "name_cn", "") or "",
            "industry": r.industry,
            "description": r.description,
            "skills_required": skills,
            "discovered_at": r.created_at.isoformat() if r.created_at else None,
        }

    # ── Neo4j fallback: query Position node by name ──
    if driver is not None:
        try:
            from app.services.graph_service import fetch_position_graph

            graph = await fetch_position_graph(driver, position_id, depth=1)
            if graph.get("position") is not None:
                pos = graph["position"]
                skills = [
                    {
                        "skill_id": s.get("skill_id", ""),
                        "name": s.get("name", ""),
                        "category": s.get("category", "hard_skill"),
                        "confidence": float(s.get("confidence", 1.0)),
                        "source_count": int(s.get("source_count", 0) or 0),
                    }
                    for s in graph.get("skills", [])
                ]
                return {
                    "position_id": pos.get("position_id", ""),
                    "name": pos.get("name", ""),
                    "name_cn": pos.get("name_cn", pos.get("name", "")),
                    "industry": pos.get("industry", ""),
                    "description": pos.get("description", ""),
                    "skills_required": skills,
                    "discovered_at": None,
                }
        except PositionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in position: {}", exc)
            raise HTTPException(status_code=500, detail="岗位处理异常") from exc

    raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")


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
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in position: {}", exc)
        raise HTTPException(status_code=500, detail="岗位处理异常") from exc


# ── Neo4j fallback for position list ──

async def _list_positions_neo4j(
    driver: Any,
    page: int,
    page_size: int,
    industry: str | None,
    search: str | None,
    status_filter: str | None = None,
) -> PositionListResponse:
    """Fallback: query Position nodes from Neo4j when PostgreSQL has no matching records.

    Positions without explicit review_status default to 'approved' for public view.
    Supports status filtering (default: only show approved for public).
    """
    try:
        async with driver.session() as session:
            # Build dynamic WHERE clauses
            where_clauses: list[str] = []
            params: dict[str, Any] = {}

            if search:
                # Phase 13 一致性审计：search 同时匹配 name 与 industry，与 PG 路径及前端契约一致
                where_clauses.append(
                    "(toLower(p.name) CONTAINS toLower($search) OR "
                    "toLower(coalesce(p.industry, '')) CONTAINS toLower($search))"
                )
                params["search"] = search
            if industry:
                where_clauses.append("toLower(p.industry) CONTAINS toLower($industry)")
                params["industry"] = industry
            # Status filter: Neo4j positions without review_status default to 'approved'
            if status_filter and status_filter != "all":
                if status_filter == "approved":
                    where_clauses.append("(p.review_status IS NULL OR p.review_status = $status)")
                else:
                    where_clauses.append("p.review_status = $status")
                params["status"] = status_filter

            where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Count total
            count_query = f"MATCH (p:Position){where_str} RETURN count(p) AS cnt"
            count_result = await session.run(count_query, params)
            count_record = await count_result.single()
            total = count_record["cnt"] if count_record else 0

            if total == 0:
                return PositionListResponse(items=[], total=0, page=page, page_size=page_size)

            # Fetch page with skills
            page_query = f"""
                MATCH (p:Position){where_str}
                WITH p ORDER BY p.name
                SKIP $skip LIMIT $limit
                OPTIONAL MATCH (p)-[r:REQUIRES]->(s:Skill)
                RETURN p, collect(s) AS skills
            """
            page_params = {**params, "skip": (page - 1) * page_size, "limit": page_size}
            page_result = await session.run(page_query, page_params)

            items: list[PositionNode] = []
            async for record in page_result:
                p_node = record["p"]
                if p_node is None:
                    continue
                props = dict(p_node)
                skills_raw = record["skills"] or []

                skill_nodes: list[SkillNode] = []
                for s in skills_raw:
                    if s is None:
                        continue
                    s_props = dict(s)
                    skill_nodes.append(SkillNode(
                        skill_id=str(s.element_id),
                        name=s_props.get("name", ""),
                        category=s_props.get("category", "hard_skill"),
                        confidence=float(s_props.get("confidence", 1.0)),
                        source_count=int(s_props.get("source_count", 0) or 0),
                    ))

                items.append(PositionNode(
                    position_id=str(p_node.element_id),
                    name=props.get("name", ""),
                    name_cn=props.get("name_cn", ""),
                    industry=props.get("industry", ""),
                    description=props.get("description", ""),
                    skills_required=skill_nodes,
                    discovered_at=None,
                ))

            return PositionListResponse(items=items, total=total, page=page, page_size=page_size)
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in position: {}", exc)
        raise HTTPException(status_code=500, detail="岗位处理异常") from exc
