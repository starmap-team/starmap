"""Admin API — thin HTTP layer over admin_audit_service.

Business logic lives in app.services.admin_audit_service and app.services.review_service.
This file only handles: request parsing, dependency injection,
domain-exception → HTTP-exception mapping, and response serialization.
"""
from __future__ import annotations

import uuid as uuid_mod
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.schemas.admin import (
    AuditQueueResponse,
    AuditUpdateRequest,
    BatchAuditRequest,
    NameCnUpdateRequest,
    PipelineStatusResponse,
    PipelineTriggerResponse,
    ReconcileResult,
    ReviewActionRequest,
    ReviewBatchRequest,
    ReviewBatchResponse,
    ReviewListResponse,
)
from app.services import review_service
from app.services.admin_audit_service import (
    AdminStatsResponse,
    AuditItem,
    AuditItemNotFound,
    build_admin_stats,
    get_review_queue,
)
from app.services.admin_audit_service import (
    approve_audit as svc_approve_audit,
)
from app.services.admin_audit_service import (
    batch_audit as svc_batch_audit,
)
from app.services.admin_audit_service import (
    reject_audit as svc_reject_audit,
)
from app.services.admin_audit_service import (
    update_review_queue_item as svc_update_review_queue_item,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ── Request / Response models (HTTP-layer only) ──


# ── Helper: domain exception → HTTP ──


def _map_not_found(exc: AuditItemNotFound) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


# ── Endpoints ──


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """Admin overview stats."""
    return await build_admin_stats(session)


@router.post("/reconcile-neo4j", response_model=ReconcileResult, dependencies=[Depends(require_admin)])
async def reconcile_neo4j_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> ReconcileResult:
    """Phase 5 Step 3: 手动触发 PG → Neo4j 同步 + 孤儿节点剪枝。

    由 admin 手动调用，或由 cron job 定期调用。
    """
    import time

    from sqlalchemy import func, select, text

    from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
    from app.services.graph_projector import GraphProjector

    # 2026-08-21 (debug 修复): reconcile 后追加孤儿队列同步 —— 此前只调
    # reconcile_all（剪枝 + 补缺失节点），半孤立（Neo4j 有 + PG 有 + 缺
    # canonical_id）从不被链接，按钮「立即对账并修复」对半孤立无效果。
    from app.services.repair_engine import RepairEngine

    start = time.time()
    # 2026-08-21: 修复前 unlinked 基线（reconcile_all step5 会 SET canonical_id
    # 链接半孤立 → 修复后 unlinked 减少 = 实际链接数）
    try:
        before_scan = await RepairEngine(driver).detect_orphans(session)
        before_unlinked = (
            before_scan.unlinked_positions + before_scan.unlinked_skills
        )
    except Exception:  # noqa: BLE001
        before_unlinked = 0
    projector = GraphProjector(driver)
    result = await projector.reconcile_all(session)

    # 2026-08-21: 追加 sync_orphan_queue —— 检测新孤儿入队 + 半孤立自动
    # 链接（_reconcile_orphan_queue_status 把已链接节点标 linked）+ stale 清理。
    repair = RepairEngine(driver)
    try:
        await repair.sync_orphan_queue(session)
    except Exception as exc:  # noqa: BLE001 — 队列同步失败不阻断 reconcile 主流程
        logger.warning("reconcile: orphan queue sync failed (non-fatal): {}", exc)

    duration_ms = int((time.time() - start) * 1000)

    # 验证对齐
    async with driver.session() as s:
        r1 = await s.run("MATCH (p:Position) RETURN count(p) AS c")
        neo4j_pos = int((await r1.single())["c"])
        r2 = await s.run("MATCH (s:Skill) RETURN count(s) AS c")
        neo4j_skl = int((await r2.single())["c"])

    pg_pos = (
        await session.execute(
            select(func.count(PositionRecord.id)).where(
                PositionRecord.review_status == "approved"
            )
        )
    ).scalar() or 0
    pg_skl = (
        await session.execute(
            select(func.count(SkillRecord.id)).where(
                SkillRecord.review_status == "approved"
            )
        )
    ).scalar() or 0

    # IC-05: PG 侧只统计 approved 岗位的 PSR（Neo4j 只投影 approved）
    pg_requires = (
        await session.execute(
            select(func.count(PositionSkillRelation.id))
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .where(PositionRecord.review_status == "approved")
        )
    ).scalar() or 0
    neo4j_requires = 0
    async with driver.session() as s:
        r3 = await s.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS c")
        neo4j_requires = int((await r3.single())["c"])
    requires_diff = abs(int(neo4j_requires) - int(pg_requires))

    # 健康度（Phase 23 Task 3 扩展：边 ±0.5% 容差纳入三档）
    edge_tolerance = max(1, int(pg_requires * 0.005))
    # 修剪孤儿是成功修复：post-reconcile 计数已对齐（neo4j_pos 等读于 reconcile_all 之后），
    # orphans_pruned>0 不再使本次修复后的对齐状态标 warn。
    nodes_equal = neo4j_pos == pg_pos and neo4j_skl == pg_skl
    if nodes_equal and requires_diff <= edge_tolerance:
        health = "ok"
    elif requires_diff > edge_tolerance or (
        abs(neo4j_pos - pg_pos) <= 1 and abs(neo4j_skl - pg_skl) <= 1
    ):
        health = "warn"
    else:
        health = "critical"

    # Phase 5 Step 4: 写 audit_events 记录
    try:
        import uuid as _uuid
        from datetime import UTC
        from datetime import datetime as _dt
        await session.execute(
            text("""
                INSERT INTO audit_events (id, event, actor, action, detail, ip, created_at,
                                          entity_type, entity_id)
                VALUES (:id, :event, :actor, :action, :detail, '', :now,
                        :entity_type, :entity_id)
            """),
            {
                "id": str(_uuid.uuid4()),
                "event": "graph_reconcile",
                "actor": "admin",
                "action": "manual_reconcile",
                "detail": f"health={health},upserted={result.nodes_upserted},orphans={result.orphans_pruned}",
                "now": _dt.now(UTC),
                # BUG-18 fix: tag reconcile events with their scope so
                # admin audit log can filter by entity (graph).
                "entity_type": "graph",
                "entity_id": "all",
            },
        )
        await session.commit()
    except Exception as audit_exc:
        logger.warning("Failed to write reconcile audit: {}", audit_exc)

    logger.info(
        "Reconcile complete: health={}, positions_neo4j={} vs pg={}, skills_neo4j={} vs pg={}, orphans={}, duration={}ms",
        health, neo4j_pos, pg_pos, neo4j_skl, pg_skl, result.orphans_pruned, duration_ms,
    )

    # 2026-08-21 (debug 修复): 计算半孤立被链接数（reconcile 后 detect_orphans
    # 的 unlinked_* 减 reconcile 前的 unlinked_*）。让按钮报告「链接了 Y 个半孤立」，
    # operator 能确认三端（PG/Neo4j/队列）已一致。
    unlinked_linked = 0
    try:
        after_scan = await RepairEngine(driver).detect_orphans(session)
        after_unlinked = (
            after_scan.unlinked_positions + after_scan.unlinked_skills
        )
        unlinked_linked = max(before_unlinked - after_unlinked, 0)
    except Exception as exc:  # noqa: BLE001 — 统计失败不影响 reconcile 主流程
        logger.warning("reconcile: unlinked_linked compute failed (non-fatal): {}", exc)

    return ReconcileResult(
        positions_synced=result.nodes_upserted,
        skills_synced=result.skills_upserted,
        orphans_pruned=result.orphans_pruned,
        positions_in_neo4j=neo4j_pos,
        skills_in_neo4j=neo4j_skl,
        positions_in_pg=pg_pos,
        skills_in_pg=pg_skl,
        requires_in_neo4j=neo4j_requires,
        requires_in_pg=pg_requires,
        requires_diff=requires_diff,
        duration_ms=duration_ms,
        health=health,
        unlinked_linked=unlinked_linked,
        edges_backfilled=result.edges_upserted,
    )


@router.get("/review-queue", response_model=AuditQueueResponse, deprecated=True)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditQueueResponse:
    """Return pending review items from DB; returns empty list when table is empty.

    DEPRECATED (D8h): 旧 ReviewQueue 审核路径已废弃 —— review_queue 表 0 行且无
    写入方（历史遗留，绕过 Phase 23 review_status 状态机直接 approved）。
    前端已改用 /admin/review-items（新状态机 + 审核即入图）。仅保留兼容旧客户端。
    """
    try:
        items = await get_review_queue(session)
        return AuditQueueResponse(items=items)
    except SQLAlchemyError as exc:
        logger.error("Database error in get_review_queue: {}", exc)
        raise HTTPException(status_code=500, detail="Database query failed") from exc


@router.post("/audit/{item_id}/approve", response_model=AuditItem)
async def approve_audit_endpoint(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> AuditItem:
    """Approve a review queue item and sync to Neo4j (LOOP-07)."""
    try:
        actor = user.get("sub") or user.get("username") or "admin"
        return await svc_approve_audit(
            item_id, session, neo4j_driver=neo4j_driver, actor=f"admin:{actor}",
        )
    except AuditItemNotFound as exc:
        raise _map_not_found(exc) from exc


@router.post("/audit/{item_id}/reject", response_model=AuditItem)
async def reject_audit_endpoint(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> AuditItem:
    """Reject a review queue item and sync to Neo4j (LOOP-07)."""
    try:
        return await svc_reject_audit(item_id, session, neo4j_driver=neo4j_driver)
    except AuditItemNotFound as exc:
        raise _map_not_found(exc) from exc


@router.put("/review-queue/{item_id}", response_model=AuditItem)
@router.patch("/review-queue/{item_id}", response_model=AuditItem, include_in_schema=False)
async def update_review_queue_item_endpoint(
    item_id: int,
    body: AuditUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Update name and/or trust of a review queue item (ADMIN-02 save loop)."""
    try:
        return await svc_update_review_queue_item(
            item_id, name=body.name, trust=body.trust, session=session,
        )
    except AuditItemNotFound as exc:
        raise _map_not_found(exc) from exc


@router.post("/audit/batch", response_model=list[AuditItem])
async def batch_audit_endpoint(
    body: BatchAuditRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> list[AuditItem]:
    """Batch approve or reject multiple review queue items."""
    try:
        actor = user.get("sub") or user.get("username") or "admin"
        return await svc_batch_audit(body.item_ids, body.action, session, actor=f"admin:{actor}")
    except AuditItemNotFound as exc:
        raise _map_not_found(exc) from exc


# ══════════════════════════════════════════════════════════════
# Review workflow endpoints (Phase 23 — D-tier redesign)
# ══════════════════════════════════════════════════════════════


# entity_type → (service module, "skill"|"position")
_REVIEW_TYPE_MAP = {
    "position": "position",
    "skill": "skill",
}


@router.get("/review-items", response_model=ReviewListResponse)
async def list_review_items(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    entity_type: Annotated[Literal["position", "skill"] | None, "过滤实体类型"] = None,
    status: Annotated[Literal["draft", "pending_review", "approved", "rejected"] | None, "审核状态"] = None,
    category: Annotated[Literal["no_skill", "unclassified", "duplicate"] | None, "数据质量类别(批0): no_skill空技能/unclassified未分类/duplicate重名"] = None,
    limit: Annotated[int, "返回数量上限"] = 50,
) -> ReviewListResponse:
    """Unified review queue combining position + skill entities.

    Default: returns all `pending_review` items (the active admin queue).
    Use `?entity_type=position|skill` to narrow; use `?status=...` to view
    a different lifecycle state. Use `?category=no_skill|unclassified|duplicate`
    to filter fuzzy positions (批0 真相源).

    2026-08-21 (debug 优化): total 改为真实筛选总数（此前 = len(items) 即
    limit 截断后的条数，前端「当前筛选 200 项」误导用户以为只有 200 条，
    实际待审 1300+）。total 现在反映当前 entity_type+status 过滤下的全量计数。
    """
    items = await review_service.list_by_status(
        session,
        entity_type=entity_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        limit=limit,
    )
    # 真实总数：按过滤条件单独 count（复用 count_by_status 的模型映射）
    from sqlalchemy import func  # noqa: PLC0415
    from sqlalchemy import select as sa_select

    from app.services.review_service import _model_for  # noqa: PLC0415

    total = 0
    types: tuple[str, ...] = ("position", "skill") if entity_type is None else (entity_type,)
    for et in types:
        model = _model_for(et)  # type: ignore[arg-type]
        stmt = sa_select(func.count()).select_from(model)
        if status is not None:
            stmt = stmt.where(model.review_status == status)
        if category and et == "position":
            from app.models.extraction_models import PositionRecord, PositionSkillRelation

            if category == "no_skill":
                stmt = stmt.where(
                    ~sa_select(PositionSkillRelation.id).where(
                        PositionSkillRelation.position_id == PositionRecord.id
                    ).exists()
                )
            elif category == "unclassified":
                stmt = stmt.where(PositionRecord.industry.in_((None, "", "未分类")))
            elif category == "duplicate":
                dup = (
                    sa_select(PositionRecord.name_cn)
                    .where(PositionRecord.name_cn.is_not(None), PositionRecord.name_cn != "")
                    .group_by(PositionRecord.name_cn)
                    .having(func.count() > 1)
                    .subquery()
                )
                stmt = stmt.where(PositionRecord.name_cn.in_(sa_select(dup.c.name_cn)))
        total += int((await session.execute(stmt)).scalar() or 0)
    return ReviewListResponse(
        items=[i.to_dict() for i in items],
        total=total,
    )


@router.post("/review/batch", response_model=ReviewBatchResponse)
async def batch_review_endpoint(
    body: ReviewBatchRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> ReviewBatchResponse:
    """2026-08-21: 批量审核/一键审核（新状态机）。

    批量 approve/reject 多个 position/skill 待审项。逐条调 review_service
    （幂等：已 approved 的 no-op），单条失败不阻断其余（返回 failed_ids）。
    """
    import uuid as _uuid

    actor = user.get("sub") or user.get("username") or "admin"
    ok = 0
    fail = 0
    failed_ids: list[str] = []
    for entity_id in body.entity_ids:
        try:
            uid = _uuid.UUID(entity_id)
        except (ValueError, TypeError):
            fail += 1
            failed_ids.append(entity_id)
            continue
        try:
            if body.action == "approve":
                await review_service.approve(
                    session, entity_type=body.entity_type, entity_id=uid, actor=actor,
                )
            else:
                if not body.reason or not body.reason.strip():
                    fail += 1
                    failed_ids.append(entity_id)
                    continue
                await review_service.reject(
                    session, entity_type=body.entity_type, entity_id=uid,
                    actor=actor, reason=body.reason,
                )
            ok += 1
        except Exception as exc:  # noqa: BLE001 — 单条失败不阻断批量
            logger.warning(
                "Batch {} failed for {} {}: {}",
                body.action, body.entity_type, entity_id, exc,
            )
            fail += 1
            failed_ids.append(entity_id)
    await session.commit()
    return ReviewBatchResponse(ok=ok, fail=fail, failed_ids=failed_ids)


@router.post("/review/{entity_type}/{entity_id}/submit")
async def submit_for_review_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Submit a draft or rejected entity for admin review."""
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.submit_for_review(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return item.to_dict()


@router.post("/review/{entity_type}/{entity_id}/approve")
async def approve_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> dict[str, Any]:
    """Approve a pending_review entity. Idempotent for already-approved."""
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.approve(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # D8f 闭环: 岗位审核通过 → 立即入图 + LLM 补中文名（不等下一轮流水线）
    item_dict = item.to_dict()
    # to_dict 键是 review_status（非 status）
    if entity_type == "position" and item_dict.get("review_status") == "approved":
        position_name = item_dict.get("name", "")
        if position_name:
            from app.tasks.stage3_services import sync_approved_position_to_graph

            try:
                await sync_approved_position_to_graph(position_name)
            except Exception as exc:  # noqa: BLE001 — 入图失败不阻断审核响应
                logger.warning("approve-then-graph failed for {!r}: {}", position_name, exc)
    # P1-14 fix (functional-review 2026-08-13): 技能审核通过此前只改 PG 状态，
    # 不写 Neo4j Skill.trust_score → avg_skill_trust（数据大屏信任评分）滞后。
    # 复用 _sync_neo4j_on_audit（MERGE canonical_id + trust_score=1.0）。
    elif entity_type == "skill" and item_dict.get("review_status") == "approved":
        skill_name = item_dict.get("name", "")
        if skill_name:
            from app.services.admin_audit_service import _sync_neo4j_on_audit

            try:
                await _sync_neo4j_on_audit(neo4j_driver, "skill", skill_name, "approved")
            except Exception as exc:  # noqa: BLE001 — Neo4j 同步失败不阻断审核响应
                logger.warning("skill approve Neo4j sync failed for {!r}: {}", skill_name, exc)
    return item_dict


@router.post("/review/{entity_type}/{entity_id}/reject")
async def reject_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> dict[str, Any]:
    """Reject a pending_review entity. Reason is required."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required for reject")
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.reject(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except review_service.MissingRejectionReason as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # P1-14 fix (functional-review 2026-08-13): 技能驳回同步 Neo4j
    # （trust_score=0.0），保持图/PG 审核态一致。
    # 2026-08-21 (debug: 拒绝可见性断点)：岗位驳回同样同步 Neo4j —— 此前
    # position 分支无任何图操作，Neo4j 节点 review_status 停留 NULL/approved，
    # 被 /positions Neo4j fallback 当作 approved 公开展示（用户报告的
    # “审核拒绝没效果”根因 B）。
    item_dict = item.to_dict()
    if entity_type in ("position", "skill"):
        entity_name = item_dict.get("name", "")
        if entity_name:
            from app.services.admin_audit_service import _sync_neo4j_on_audit

            try:
                await _sync_neo4j_on_audit(neo4j_driver, entity_type, entity_name, "rejected")
            except Exception as exc:  # noqa: BLE001 — Neo4j 同步失败不阻断审核响应
                logger.warning("{} reject Neo4j sync failed for {!r}: {}", entity_type, entity_name, exc)
    return item_dict


@router.patch("/review/{entity_type}/{entity_id}/name-cn")
async def update_name_cn_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: NameCnUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """调整岗位/技能中文名（name_cn）— 复用内容审核模块（D8i/D8j 手工校准）。

    更新 PG 行 + 同步 Neo4j 节点属性，非破坏、幂等。
    """
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.update_name_cn(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            name_cn=body.name_cn,
            actor=user.get("sub", "admin"),
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        # 审计日志 action 白名单/其他约束冲突：DB 侧状态与代码不一致时
        # 返回可读错误而非 500（如 038 迁移未生效导致 ck_review_audit_log_action 缺 update_name_cn）。
        logger.error(
            "update_name_cn integrity error for {} {}: {}", entity_type, entity_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail="中文名更新失败：数据库约束冲突（审计日志白名单未同步），请联系管理员",
        ) from exc

    # 同步 Neo4j 节点 name_cn（图谱展示跟随 PG 权威）
    if neo4j_driver is not None:
        try:
            from app.services.graph_projector import GraphProjector

            projector = GraphProjector(neo4j_driver)
            await projector.apply_change(
                label="Position" if entity_type == "position" else "Skill",
                canonical_id=uid,
                properties={"name_cn": body.name_cn},
            )
        except Exception as exc:  # noqa: BLE001 — 图同步失败不阻断 PG 更新
            logger.warning("name_cn graph sync failed for {} {}: {}", entity_type, entity_id, exc)
    return item.to_dict()


@router.post("/review/{entity_type}/{entity_id}/unpublish")
async def unpublish_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Unpublish an approved entity (admin override) — moves it back to draft."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required for unpublish")
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.unpublish(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except review_service.MissingRejectionReason as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return item.to_dict()


@router.get("/review-stats")
async def get_review_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    """Aggregate count of entities by entity_type × review_status."""
    return await review_service.count_by_status(session)


# ── Pipeline management ──


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineStatusResponse:
    """Pipeline status — recent runs + data health stats."""
    import sqlalchemy as sa

    from app.models.extraction_models import (
        JDExtractionRecord,
        PositionRecord,
        ReviewQueue,
        SkillRecord,
    )
    from app.models.pipeline_models import PipelineRun as PR  # noqa: N817

    # Recent 5 runs
    runs_result = await session.execute(
        sa.select(PR).order_by(PR.started_at.desc()).limit(5)
    )
    recent_runs = [
        {
            "id": str(r.id),
            "run_type": r.run_type,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs_result.scalars().all()
    ]

    # Data stats
    jd_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(JDExtractionRecord)
    )).scalar() or 0)
    pos_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(PositionRecord)
    )).scalar() or 0)
    skill_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(SkillRecord)
    )).scalar() or 0)
    pending_review = int((await session.execute(
        sa.select(sa.func.count()).select_from(ReviewQueue)
        .where(ReviewQueue.status == "pending")
    )).scalar() or 0)

    data_stats = {
        "jd_count": jd_count,
        "position_count": pos_count,
        "skill_count": skill_count,
        "pending_review": pending_review,
    }

    return PipelineStatusResponse(recent_runs=recent_runs, data_stats=data_stats)


@router.post("/pipeline/trigger-full", response_model=PipelineTriggerResponse)
async def trigger_full_pipeline(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineTriggerResponse:
    """Trigger a full pipeline run: crawl -> dedup -> clean -> import -> graph_sync."""
    from app.services.pipeline_service import trigger_and_start

    run = await trigger_and_start(run_type="full")

    return PipelineTriggerResponse(
        run_id=str(run.id),
        status=run.status,
        message=f"Full pipeline triggered (run_id={run.id})",
    )


# ── Sub-routers (Phase 7 admin domain split) ──
from app.api.v1.admin_graph_nodes import router as graph_nodes_router  # noqa: E402
from app.api.v1.admin_prompts import router as prompts_router  # noqa: E402

router.include_router(prompts_router, prefix="")
router.include_router(graph_nodes_router, prefix="")
