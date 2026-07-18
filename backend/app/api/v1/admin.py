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
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
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


class AuditUpdateRequest(BaseModel):
    """Partial update for a review-queue item."""

    name: str | None = Field(default=None, min_length=1)
    trust: int | None = Field(default=None, ge=0, le=100)


class BatchAuditRequest(BaseModel):
    """Batch approve or reject multiple review queue items."""

    item_ids: list[int] = Field(..., min_length=1, max_length=100)
    action: Literal["approve", "reject"]


class AuditQueueResponse(BaseModel):
    items: list[AuditItem] = Field(default_factory=list)


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


@router.get("/review-queue", response_model=AuditQueueResponse)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditQueueResponse:
    """Return pending review items from DB; returns empty list when table is empty."""
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


class ReviewListResponse(BaseModel):
    """Unified review queue: position + skill entities, with status filter."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ReviewActionRequest(BaseModel):
    """Body for submit/approve/reject/unpublish actions."""

    reason: str | None = Field(default=None, max_length=2000)


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
    return item.to_dict()


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


class PipelineStatusResponse(BaseModel):
    """Pipeline status + data health summary."""

    recent_runs: list[dict[str, Any]] = Field(default_factory=list)
    data_stats: dict[str, Any] = Field(default_factory=dict)


class PipelineTriggerResponse(BaseModel):
    """Full pipeline trigger response."""

    run_id: str
    status: str
    message: str


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
    from app.core.pipeline.executor import trigger_and_start

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
