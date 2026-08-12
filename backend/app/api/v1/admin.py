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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.schemas.admin import (
    AuditQueueResponse,
    AuditUpdateRequest,
    BatchAuditRequest,
    PipelineStatusResponse,
    PipelineTriggerResponse,
    ReconcileResult,
    ReviewActionRequest,
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

    from app.models.extraction_models import PositionRecord, SkillRecord
    from app.services.graph_projector import GraphProjector

    start = time.time()
    projector = GraphProjector(driver)
    result = await projector.reconcile_all(session)
    duration_ms = int((time.time() - start) * 1000)

    # 验证对齐
    async with driver.session() as s:
        r1 = await s.run("MATCH (p:Position) RETURN count(p) AS c")
        neo4j_pos = int((await r1.single())["c"])
        r2 = await s.run("MATCH (s:Skill) RETURN count(s) AS c")
        neo4j_skl = int((await r2.single())["c"])

    pg_pos = (await session.execute(select(func.count(PositionRecord.id)))).scalar() or 0
    pg_skl = (await session.execute(select(func.count(SkillRecord.id)))).scalar() or 0

    # 健康度
    if neo4j_pos == pg_pos and neo4j_skl == pg_skl and result.orphans_pruned == 0:
        health = "ok"
    elif abs(neo4j_pos - pg_pos) <= 1 and abs(neo4j_skl - pg_skl) <= 1:
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

    return ReconcileResult(
        positions_synced=result.nodes_upserted,
        skills_synced=result.nodes_upserted,
        orphans_pruned=result.orphans_pruned,
        positions_in_neo4j=neo4j_pos,
        skills_in_neo4j=neo4j_skl,
        positions_in_pg=pg_pos,
        skills_in_pg=pg_skl,
        duration_ms=duration_ms,
        health=health,
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
    limit: Annotated[int, "返回数量上限"] = 50,
) -> ReviewListResponse:
    """Unified review queue combining position + skill entities.

    Default: returns all `pending_review` items (the active admin queue).
    Use `?entity_type=position|skill` to narrow; use `?status=...` to view
    a different lifecycle state.
    """
    items = await review_service.list_by_status(
        session,
        entity_type=entity_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        limit=limit,
    )
    return ReviewListResponse(
        items=[i.to_dict() for i in items],
        total=len(items),
    )


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
    return item_dict


@router.post("/review/{entity_type}/{entity_id}/reject")
async def reject_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
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
