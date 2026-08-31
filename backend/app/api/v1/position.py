"""岗位管理 API — 接入 PostgreSQL position_records，Neo4j fallback。"""
from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_session, get_neo4j_driver, require_admin
from app.exceptions import PositionNotFoundError, StarMapError
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.schemas.position import (
    IndustriesResponse,
    PositionListResponse,
    PositionNode,
    PositionSyncResult,
    SkillNode,
)

router = APIRouter(prefix="/positions", tags=["岗位管理"])

admin_router = APIRouter(
    prefix="/admin", tags=["岗位管理"], dependencies=[Depends(require_admin)],
)


# SQL LIKE 通配符转义，防止通配符注入
def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards (% and _) in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
    user: Annotated[dict[str, Any], Depends(get_current_user)],
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
    is_admin = user.get("role") == "admin"
    if not is_admin:
        include_all = False
        status = "approved"
 # Count total
    count_stmt = sa.select(sa.func.count()).select_from(PositionRecord)
    if industry:
        count_stmt = count_stmt.where(PositionRecord.industry.ilike(f"%{_escape_like(industry)}%", escape="\\"))
    if search:
 # 一致性审计：search 同时匹配 name、name_cn 与 industry（与前端 placeholder/客户端筛选及 Neo4j 路径一致）
        like = f"%{_escape_like(search)}%"
        count_stmt = count_stmt.where(
            sa.or_(
                PositionRecord.name.ilike(like, escape="\\"),
                PositionRecord.name_cn.ilike(like, escape="\\"),
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
                PositionRecord.name_cn.ilike(like, escape="\\"),
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
                name_cn=sk.name_cn,  # D8i: 技能中文名
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
            discovered_at=r.created_at,
            review_status=getattr(r, "review_status", None),
        ))

    return PositionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/industries",
    summary="行业列表",
    description="返回所有岗位的去重行业名称列表（按字母排序）。\n\n"
    "用于前端行业筛选下拉选项，确保用户看到全量行业而非仅当前页。",
    response_model=IndustriesResponse,
)
async def list_industries(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IndustriesResponse:
    """Distinct industry names from position_records, sorted alphabetically."""
    stmt = (
        sa.select(PositionRecord.industry)
        .where(PositionRecord.industry.isnot(None))
        .where(PositionRecord.industry != "")
        .distinct()
        .order_by(PositionRecord.industry)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return IndustriesResponse(industries=[i for i in rows if i is not None])


@router.get(
    "/{position_id}",
    summary="岗位详情",
    description="返回单个岗位详情及其技能关系。",
)
async def get_position(
    position_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    import uuid as uuid_mod

    from fastapi import HTTPException

 # 详情端点按可见性策略过滤 —— 非 admin 只能查看已发布岗位
    is_admin = user.get("role") == "admin"

    r = None

 # 尝试按 UUID 查询（仅当 ID 包含连字符的 UUID 或纯 hex 格式时）
    if len(position_id) >= 32 and (len(position_id) <= 36):
        try:
            uuid_val = uuid_mod.UUID(position_id)
            stmt = sa.select(PositionRecord).where(PositionRecord.id == uuid_val)
            if not is_admin:
                stmt = stmt.where(PositionRecord.review_status == "approved")
            r = (await session.execute(stmt)).scalar_one_or_none()
        except (ValueError, Exception):
            pass  # 非 UUID 格式，跳过

 # 尝试按名称查询
    if r is None:
        stmt = sa.select(PositionRecord).where(PositionRecord.name == position_id)
        if not is_admin:
            stmt = stmt.where(PositionRecord.review_status == "approved")
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
                "name_cn": getattr(sk, "name_cn", "") or "",
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
            # Phase 38: A3 五要素（持久化列，缺省返回 null/空列表）
            "industry_scenario": r.industry_scenario,
            "core_responsibilities": r.core_responsibilities or [],
            "bonus_skills": r.bonus_skills or [],
            "summary": r.summary,
            # 2026-08-20 (修复 C): 数据来源追溯 —— 让用户知根知底
            "provenance": {
                "source_run_id": str(r.source_run_id) if r.source_run_id else None,
                "created_by": r.created_by,
                "reviewed_by": r.reviewed_by,
                "review_status": r.review_status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            },
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
                        "name_cn": s.get("name_cn") or "",
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
                    "provenance": {
                        "source_run_id": pos.get("source_run_id"),
                        "created_by": pos.get("created_by"),
                        "reviewed_by": pos.get("reviewed_by"),
                        "review_status": pos.get("review_status"),
                        "created_at": None,
                    },
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
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    with_definitions: Annotated[
        bool,
        Query(description="A3: 为 Top-N 候选岗位 LLM 生成五要素定义（行业场景/核心职责/加分技能）。仅 admin，消耗 LLM 配额"),
    ] = False,
    definition_top_n: Annotated[
        int,
        Query(ge=1, le=50, description="生成定义的岗位数上限（按 emerging_ratio 取 Top-N）"),
    ] = 10,
) -> dict[str, Any]:
    """触发新兴岗位发现：基于技能频率 Z-score 检测。

    从 skill_timeseries 表加载历史频率数据，
    然后运行 EmergenceFinder 进行 Z-score 分析。
    若无时序数据则返回"数据不足"提示。

    with_definitions=true（A3，仅 admin）：对 emerging_ratio Top-N 候选岗位
    调 LLM 补齐行业场景/核心职责/加分技能/岗位简述，凑齐赛项要求的
    "岗位名称、核心职责、必备技能、加分技能、典型行业应用场景"五要素。
    fail-soft：单个岗位生成失败不影响其余候选。
    """
    from app.services.evolution_service import EmergenceFinder

    if with_definitions and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="with_definitions 仅 admin 可用（消耗 LLM 配额）")

    try:
 # Step 1: Load timeseries data for frequency history
        from app.services.evolution_service import load_skill_timeseries_data

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

        emerging_positions = await _discover_position_candidates(db, report)
        definitions_meta: dict[str, Any] | None = None
        if with_definitions and emerging_positions:
            from app.services.evolution_service import generate_position_definitions

            definitions_meta = await generate_position_definitions(emerging_positions, top_n=definition_top_n)
            if definitions_meta.get("warnings"):
                logger.warning("A3 definition generation warnings: {}", definitions_meta["warnings"])

        return {
            "status": "completed",
            "emerging_skills": emerging,
            "count": len(emerging),
            "skills_analyzed": len(skill_data),
            # 模块A（赛项）：岗位级发现 —— 涌现技能反查岗位画像，标记新兴演化候选
            "emerging_positions": emerging_positions,
            # A3（赛项）：五要素定义生成结果摘要（仅 with_definitions=true 时返回）
            **({"definitions": {k: definitions_meta[k] for k in ("generated", "failed", "warnings")}} if definitions_meta else {}),
        }
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in position: {}", exc)
        raise HTTPException(status_code=500, detail="岗位处理异常") from exc


async def _discover_position_candidates(
    session: AsyncSession,
    report: Any,
) -> list[dict[str, Any]]:
    """模块A 岗位级发现：涌现技能 → 岗位画像交叉 → 新兴演化候选岗位。

    赛项要求"识别萌芽/兴起的新岗位并生成岗位定义"。技能级 z-score 只回答
    "哪些技能在涌现"，本函数进一步回答"哪些岗位因涌现技能而可能是新岗位
    或正在演化"——对每个已审核岗位统计其 required 技能中属于涌现/上升
    技能的比例，占比 ≥50% 标记为候选，附带岗位定义字段。
    """
    from app.services.evolution_service import discover_emerging_positions

    result = await discover_emerging_positions(session)
    return result.get("candidates", [])


@admin_router.post(
    "/sync/all-positions-to-neo4j",
    summary="全量补齐 Neo4j Position 节点",
    description="将 PG position_records 全量幂等 MERGE 到 Neo4j Position 节点（C-1 SSOT 漂移修复）。\n\n"
    "复用 admin_audit_service 既有的 MERGE (n:Position {canonical_id}) 路径，重复执行安全。\n"
    "单条失败不阻断其余记录，失败明细在 failed 列表返回。\n\n"
    "prune_legacy=true 时额外剪枝无 canonical_id 的遗留 Position 节点（破坏性，默认关闭）。",
    response_model=PositionSyncResult,
)
async def sync_all_positions_to_neo4j_endpoint(
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    prune_legacy: Annotated[
        bool,
        Query(description="是否剪枝无 canonical_id 的遗留 Position 节点（破坏性操作，默认 false）"),
    ] = False,
) -> PositionSyncResult:
    """Admin 手动触发全量岗位同步，返回 {synced, failed, total, pruned, started_at, finished_at}。"""
    from app.db.session import get_session_factory
    from app.services.admin_audit_service import sync_all_positions_to_neo4j

    try:
        result = await sync_all_positions_to_neo4j(
            get_session_factory(), driver, prune_legacy=prune_legacy,
        )
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in sync_all_positions_to_neo4j: {}", exc)
        raise HTTPException(status_code=500, detail="岗位同步异常") from exc

    return PositionSyncResult(**result)


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

    Visibility policy (fixed 2026-08-21): only explicit `approved` is public.
    Historical nodes without `review_status` (NULL) are legacy name-MERGE junk
    and MUST NOT be surfaced as approved — that was the "rejected still visible"
    leak. NULL-review_status nodes are now excluded from public query results.
    """
    try:
        async with driver.session() as session:
 # Build dynamic WHERE clauses
            where_clauses: list[str] = []
            params: dict[str, Any] = {}

            if search:
 # 一致性审计：search 同时匹配 name / name_cn / industry，与 PG 路径及前端契约一致
                where_clauses.append(
                    "(toLower(p.name) CONTAINS toLower($search) OR "
                    "toLower(coalesce(p.name_cn, '')) CONTAINS toLower($search) OR "
                    "toLower(coalesce(p.industry, '')) CONTAINS toLower($search))"
                )
                params["search"] = search
            if industry:
                where_clauses.append("toLower(p.industry) CONTAINS toLower($industry)")
                params["industry"] = industry
 # Status filter: only explicit 'approved' is publicly visible.
 # (Historical NULL review_status nodes are legacy junk — do not default them
 #  to approved. Previously `NULL OR =` surfaced rejected/pending junk publicly.)
            if status_filter and status_filter != "all":
                where_clauses.append("(p.review_status = $status)")
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
                    review_status=props.get("review_status", None),
                ))

            return PositionListResponse(items=items, total=total, page=page, page_size=page_size)
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in position: {}", exc)
        raise HTTPException(status_code=500, detail="岗位处理异常") from exc
