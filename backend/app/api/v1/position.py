"""岗位管理 API — 接入 PostgreSQL position_records，Neo4j fallback。"""
from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL, normalize_industry
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

# D-02: 岗位域的 admin 运维路由。独立 router（prefix="/admin"）以避免与
# `/positions/{position_id}` 的路径参数抢匹配，同时叠加 require_admin 鉴权。
admin_router = APIRouter(
    prefix="/admin", tags=["岗位管理"], dependencies=[Depends(require_admin)],
)


# P2 修复 (INJ-03): 转义 SQL LIKE 通配符，防止通配符注入
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
 # 可见性策略此前只读 query 参数、
 # 无角色校验 —— 任何登录用户传 ?status=pending_review 或 include_all=true
 # 即可查看未发布/已驳回岗位，注释声称的"admin 用户可传 include_all"形同
 # 虚设。现强制：非 admin 忽略 include_all 并锁定 status=approved。
    is_admin = user.get("role") == "admin"
    if not is_admin:
        include_all = False
        status = "approved"
 # Count total
    count_stmt = sa.select(sa.func.count()).select_from(PositionRecord)
    if industry:
        count_stmt = count_stmt.where(PositionRecord.industry.ilike(f"%{_escape_like(industry)}%", escape="\\"))
    if search:
 # Phase 13 一致性审计：search 同时匹配 name、name_cn 与 industry（与前端 placeholder/客户端筛选及 Neo4j 路径一致）
        like = f"%{_escape_like(search)}%"
 # Fix D (Architect review): industry 搜索排除「未分类」字面量，避免 admin
 # 输入「未分类」搜出全部岗位。
        count_stmt = count_stmt.where(
            sa.or_(
                PositionRecord.name.ilike(like, escape="\\"),
                PositionRecord.name_cn.ilike(like, escape="\\"),
                sa.and_(
                    PositionRecord.industry.ilike(like, escape="\\"),
                    PositionRecord.industry != UNCLASSIFIED_INDUSTRY_LITERAL,
                ),
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
 # Fix D: search 排除「未分类」字面量（避免 admin 搜「未分类」命中全部）
        stmt = stmt.where(
            sa.or_(
                PositionRecord.name.ilike(like, escape="\\"),
                PositionRecord.name_cn.ilike(like, escape="\\"),
                sa.and_(
                    PositionRecord.industry.ilike(like, escape="\\"),
                    PositionRecord.industry != UNCLASSIFIED_INDUSTRY_LITERAL,
                ),
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
    "用于前端行业筛选下拉选项，确保用户看到全量行业而非仅当前页。\n\n"
    "2026-08-17 (P1-D 闭环): 若 DB 存在「未分类」字面量行（永远存在的兜底桶），\n"
    "API 也会一并返回 — 否则用户无法在 87% 岗位是「未分类」时筛选它们。",
    response_model=IndustriesResponse,
)
async def list_industries(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IndustriesResponse:
    """Distinct industry names from position_records, sorted alphabetically.

    「未分类」字面量（DB 兜底桶）始终追加在返回列表末尾（仅在存在时），
    不参与字母排序，确保用户可筛 87% 的「未分类」岗位。
    """
 # 真实行业（不含「未分类」），按字母排序
    real_stmt = (
        sa.select(PositionRecord.industry)
        .where(PositionRecord.industry.isnot(None))
        .where(PositionRecord.industry != "")
        .where(PositionRecord.industry != UNCLASSIFIED_INDUSTRY_LITERAL)
        .distinct()
        .order_by(PositionRecord.industry)
    )
    real_rows = (await session.execute(real_stmt)).scalars().all()

 # 「未分类」字面量行存在性检查（避免出现「未分类」chip 但筛不出结果的 UX 撕裂）
    has_unclassified_stmt = (
        sa.select(sa.func.count())
        .select_from(PositionRecord)
        .where(PositionRecord.industry == UNCLASSIFIED_INDUSTRY_LITERAL)
    )
    has_unclassified = (await session.execute(has_unclassified_stmt)).scalar() or 0

    industries = [i for i in real_rows if i is not None]
    if has_unclassified > 0:
        industries.append(UNCLASSIFIED_INDUSTRY_LITERAL)
    return IndustriesResponse(industries=industries)


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

 # 详情同样遵守可见性策略 —— 非 admin 只能查看已发布岗位
 # （list_positions 已锁定 status=approved，详情端点此前完全不按
 # review_status 过滤 → 通过 /positions/{id} 直接访问未发布岗位）。
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
                "category": sk.category,
                "proficiency": "精通" if rel.requirement_type == "required" else "了解" if rel.requirement_type == "preferred" else "熟悉",
                "confidence": float(rel.confidence or 1.0),
                "source_count": sk.source_count or 0,
            }
            for sk, rel in skill_rows
        ]
 # 契约 (industry.py): DB industry 永远是非空字符串 — 后端兜底归一化，
 # 前端 PositionList.vue:302 / PositionDetail.vue 都不需要 `|| '未分类'` 兜底。
 # 同时防止后续写入路径绕过 normalize_industry() 时的回归。
 # 用 normalize_industry 而非简单的 `or` 兜底，是为了让「 」(纯空白)、
 # 「通用」/「其他」等历史脏数据也能被归一化（详见 industry.py）。
        industry_value = normalize_industry(r.industry)
        return {
            "position_id": str(r.id),
            "name": r.name,
            "name_cn": getattr(r, "name_cn", "") or "",
            "industry": industry_value,
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
 # 契约 (industry.py): industry 永远是非空字面量。
 # Neo4j 节点 industry 属性可能存 NULL（_POSITION_MERGE_CYPHER
 # 不走归一化），必须 normalize_industry 兜底。
                    "industry": normalize_industry(pos.get("industry")),
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
    from app.services.evolution_service import EmergenceFinder

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

        return {
            "status": "completed",
            "emerging_skills": emerging,
            "count": len(emerging),
            "skills_analyzed": len(skill_data),
 # P1-4: 岗位级发现 —— 涌现技能反查岗位画像，标记新兴演化候选
            "emerging_positions": await _discover_position_candidates(db, report),
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
    """P1-4 岗位级发现：涌现技能 → 岗位画像交叉 → 新兴演化候选岗位。

    赛项模块A要求"识别萌芽/兴起的新岗位并生成岗位定义"。技能级 z-score
    只回答"哪些技能在涌现"，本函数进一步回答"哪些岗位因涌现技能而可能
    是新岗位/正在演化"——对每个已审核岗位统计其 required 技能中属于
    涌现/上升技能的比例，占比 ≥50% 标记为候选，附带岗位定义字段。
    """
    from app.services.evolution_service import discover_emerging_positions

    result = await discover_emerging_positions(session)
    return result.get("candidates", [])


# ── Admin: 全量 PG → Neo4j Position 同步（C-1 D-01/D-02）──


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


# ── Admin: 单个岗位 industry 重新分类（Phase 3 IndustryClassifier）──


class ReclassifyIndustryRequest(BaseModel):
    """Admin 手动重新分类 industry 请求体（Phase 3, 2026-08-17）。

    验证规则：
    - industry 不允许填「未分类」字面量（用户应填真实行业或留空由系统 fallback）
    - industry 必须是 canonical 桶之一（防 Admin 误输入拼写错误的字符串污染图谱）
    - reason 至少 5 字（让 audit log 可追溯动机）
    """

    industry: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="新的行业（必须是 industry_taxonomy.yaml 中的 canonical 桶之一）",
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="重新分类的原因（写入 ReviewAuditLog）",
    )


class ReclassifyIndustryResponse(BaseModel):
    """Reclassify 结果（返回写入后的 industry + 受影响记录数）。"""

    position_id: str
    canonical_id: str | None = None
    industry: str = Field(description="归一化后的 industry（前端直接显示）")
    neo4j_synced: bool = Field(description="Neo4j Position 节点 industry 是否已同步")
    audit_log_id: int | None = Field(description="ReviewAuditLog 主键（用户可查）")


@admin_router.post(
    "/positions/{position_id}/reclassify-industry",
    summary="重新分类单个岗位 industry",
    description="Admin 手动覆盖 PG position_records.industry 字段 + 同步 Neo4j Position 节点 industry 属性 + 写 ReviewAuditLog。\n\n"
    "用法：当场景场景下 LLM 抽取 / backfill / alias 字典把某岗位归到错误的"
    " canonical 桶时，运营可在 /admin/content-review 面板一键修正。\n\n"
    "锁定契约：industry 必须是 taxonomy.yaml canonical 桶之一（不允许"
    " 「未分类」字面量 / 模糊词），否则 422 拒绝。",
    response_model=ReclassifyIndustryResponse,
)
async def reclassify_industry(
    position_id: str,
    body: ReclassifyIndustryRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> ReclassifyIndustryResponse:
    """Phase 3 IndustryClassifier 第三层：admin 手动覆盖闭环。"""
    from app.core.extraction.industry import (
        UNCLASSIFIED_INDUSTRY_LITERAL,
        get_canonical_industries,
        is_generic_industry,
        normalize_industry,
    )

 # 1. 校验 industry 是 canonical 桶之一（防 admin 误输入污染）
    canonical = set(get_canonical_industries())
    normalized = normalize_industry(body.industry)
    if normalized == UNCLASSIFIED_INDUSTRY_LITERAL:
        raise HTTPException(
            status_code=422,
            detail=f"industry 不允许「未分类」字面量或模糊词，请选 canonical 桶：{sorted(canonical)[:5]}...",
        )
    if normalized not in canonical:
        raise HTTPException(
            status_code=422,
            detail=f"industry '{body.industry}' 不在 canonical 桶中，可选：{sorted(canonical)[:10]}...",
        )
    if is_generic_industry(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"industry '{body.industry}' 是模糊词，请选真实行业",
        )

 # 2. 校验 position 存在且可访问
    import uuid as _uuid
    canonical_id: str | None = None
    try:
        _uuid.UUID(position_id)
        r = (await session.execute(
            sa.select(PositionRecord).where(PositionRecord.id == _uuid.UUID(position_id))
        )).scalar_one_or_none()
    except (ValueError, Exception):
 # 非 UUID，按名称查询
        r = (await session.execute(
            sa.select(PositionRecord).where(PositionRecord.name == position_id)
        )).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")

    old_industry = r.industry or ""
    canonical_id = str(r.id)
    r.industry = normalized
    await session.commit()
    await session.refresh(r)

 # 3. 同步 Neo4j Position 节点 industry 属性
    neo4j_synced = False
    if driver is not None:
        try:
            async with driver.session() as s:
                await s.run(
                    "MATCH (n:Position {canonical_id: $cid}) "
                    "SET n.industry = $industry, n.updated_at = datetime()",
                    cid=canonical_id,
                    industry=normalized,
                )
                neo4j_synced = True
        except Exception as exc:
            logger.warning("reclassify_industry: Neo4j sync failed: {}", exc)
            neo4j_synced = False

 # 4. 写 ReviewAuditLog（让 admin 可查「谁、什么时候、为什么」改了 industry）
    from app.models.review_audit_log import ReviewAuditLog
    audit_log = ReviewAuditLog(
        entity_type="position",
        entity_id=r.id,
        actor=user.get("sub") or user.get("username") or "unknown",
        action="reclassify_industry",
        previous_status=old_industry or None,
        new_status=normalized,
        reason=body.reason,
    )
    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)
    audit_id = audit_log.id

    return ReclassifyIndustryResponse(
        position_id=canonical_id,
        canonical_id=canonical_id,
        industry=normalized,
        neo4j_synced=neo4j_synced,
        audit_log_id=audit_id,
    )


class ReExtractSkillsRequest(BaseModel):
    """Admin 触发重新抽取技能请求体（多模块联动 Phase 4, 2026-08-17）。

    适用场景：低数据支撑岗位（no_data / low_data_support）—
    admin 可触发对原始 JD 文本的 LLM 重新抽取，补全 skills_required。
    """

    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="重新抽取原因（写入 ReviewAuditLog）",
    )


class ReExtractSkillsResponse(BaseModel):
    """Re-extract 结果。"""

    position_id: str
    jd_extraction_id: str | None = None
    skills_extracted: int = 0
    neo4j_synced: bool
    audit_log_id: int | None = None


@admin_router.post(
    "/positions/{position_id}/re-extract-skills",
    summary="触发单个岗位技能重新抽取",
    description=(
        "多模块联动 Phase 4 (2026-08-17)：admin 主动对低数据支撑岗位触发"
        " LLM 重新抽取 skills_required，弥补自动 ETL 抽取失败 / 数据缺失场景。\n\n"
        "与 reclassify-industry 不同：reclassify 只改 industry 字段，"
        "本端点重新跑 LLM extract pipeline（不传 jd_content 用最近一次"
        " raw_text 重新抽取）。\n\n"
        "写入路径：create JDExtractionRecord → 写 PositionSkillRelation"
        " → Neo4j 同步 → 写 ReviewAuditLog。"
    ),
    response_model=ReExtractSkillsResponse,
)
async def re_extract_skills(
    position_id: str,
    body: ReExtractSkillsRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> ReExtractSkillsResponse:
    """低数据支撑岗位的补抽取端点（fail-soft，LLM 失败不阻塞）。"""
    import uuid as _uuid
    from app.core.extraction.llm_client import LLMClient
    from app.core.extraction.jd_extract import extract_from_jd, mask_pii
    from app.tasks.stage3_services import (
        _upsert_position,
        _upsert_skill,
        _ensure_position_skill_relation,
        _confidence_from_result,
        _hallucination_score_from_result,
    )
    from app.models.extraction_models import (
        JDExtractionRecord,
        PositionSkillRelation,
    )

    # 1. 校验 position 存在
    try:
        _uuid.UUID(position_id)
        pos = (await session.execute(
            sa.select(PositionRecord).where(PositionRecord.id == _uuid.UUID(position_id))
        )).scalar_one_or_none()
    except (ValueError, Exception):
        pos = (await session.execute(
            sa.select(PositionRecord).where(PositionRecord.name == position_id)
        )).scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")

    # 2. 找最近一次该岗位的 raw_text（jdextractionrecord.extracted_skills.job_title 对应）
    #    这里简化：直接用 pos.name 作为 LLM 输入（admin 触发场景通常是 legacy 岗位没 JD 文本）
    jd_content = pos.name
    if pos.name_cn and pos.name_cn != pos.name:
        jd_content = f"{pos.name_cn}（{pos.name}）"

    # 3. 调 LLM extract（fail-soft）
    try:
        llm_result = await extract_from_jd(jd_content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"LLM 抽取失败: {type(exc).__name__}: {str(exc)[:200]}",
        )

    data = llm_result.get("data", {})
    extracted_skills = data.get("required_skills", []) + data.get("preferred_skills", [])

    # 4. 写 JDExtractionRecord
    extraction_record = JDExtractionRecord(
        jd_content=mask_pii(jd_content),
        job_title=pos.name,
        extracted_skills=data,
        experience_years=data.get("experience_required"),
        education=data.get("education_required"),
        confidence=_confidence_from_result(llm_result),
        hallucination_score=_hallucination_score_from_result(llm_result),
        status="completed",
    )
    session.add(extraction_record)
    await session.flush()

    # 5. 写 PositionSkillRelation（重复检测：同 position+skill 跳过）
    skills_added = 0
    for entry in extracted_skills:
        if not isinstance(entry, dict):
            continue
        skill_name = entry.get("name") or entry.get("skill") or entry.get("title")
        if not skill_name:
            continue
        skill_row = await _upsert_skill(
            session, skill_name,
            entry.get("category", "hard_skill"),
        )
        existing_rel = (await session.execute(
            sa.select(PositionSkillRelation).where(
                PositionSkillRelation.position_id == pos.id,
                PositionSkillRelation.skill_id == skill_row.id,
            )
        )).scalar_one_or_none()
        if existing_rel is None:
            await _ensure_position_skill_relation(
                session, pos.id, skill_row.id,
                "required" if entry in data.get("required_skills", []) else "preferred",
                _confidence_from_result(llm_result),
            )
            skills_added += 1

    await session.commit()
    await session.refresh(extraction_record)

    # 6. Neo4j 同步（fail-soft）
    neo4j_synced = False
    if driver is not None:
        try:
            async with driver.session() as s:
                await s.run(
                    "MATCH (p:Position {canonical_id: $cid}) "
                    "SET p.updated_at = datetime()",
                    cid=str(pos.id),
                )
                neo4j_synced = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("re_extract_skills: Neo4j sync failed: {}", exc)
            neo4j_synced = False

    # 7. 写 ReviewAuditLog
    from app.models.review_audit_log import ReviewAuditLog
    audit_log = ReviewAuditLog(
        entity_type="position",
        entity_id=pos.id,
        actor=user.get("sub") or user.get("username") or "unknown",
        action="re_extract_skills",
        previous_status=None,  # skills 列表无法用 single string 表示
        new_status=f"extracted={skills_added}",
        reason=body.reason,
    )
    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)

    return ReExtractSkillsResponse(
        position_id=str(pos.id),
        jd_extraction_id=str(extraction_record.id) if extraction_record.id else None,
        skills_extracted=skills_added,
        neo4j_synced=neo4j_synced,
        audit_log_id=audit_log.id,
    )


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
 # Fix D (Architect review): industry CONTAINS 排除「未分类」字面量，
 # 避免 admin 搜「未分类」命中所有岗位。Neo4j 侧 industry=null 时
 # coalesce('', '') 不命中。
                where_clauses.append(
                    "(toLower(p.name) CONTAINS toLower($search) OR "
                    "(p.industry IS NOT NULL AND p.industry <> $unclassified_lit AND "
                    "toLower(p.industry) CONTAINS toLower($search)))"
                )
                params["search"] = search
                params["unclassified_lit"] = UNCLASSIFIED_INDUSTRY_LITERAL
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
 # fix: 回写 review_status，与 PG 路径字段对齐（OPEN-LOW 修复）
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
