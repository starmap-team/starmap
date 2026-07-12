"""Admin API — thin HTTP layer over admin_audit_service.

Business logic lives in app.services.admin_audit_service.
This file only handles: request parsing, dependency injection,
domain-exception → HTTP-exception mapping, and response serialization.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.services.admin_audit_service import (
    AdminStatsResponse,
    AuditItem,
    AuditItemNotFound,
    approve_audit as svc_approve_audit,
    batch_audit as svc_batch_audit,
    build_admin_stats,
    get_review_queue,
    reject_audit as svc_reject_audit,
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
) -> AuditItem:
    """Approve a review queue item and sync to Neo4j (LOOP-07)."""
    try:
        return await svc_approve_audit(item_id, session, neo4j_driver=neo4j_driver)
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
) -> list[AuditItem]:
    """Batch approve or reject multiple review queue items."""
    try:
        return await svc_batch_audit(body.item_ids, body.action, session)
    except AuditItemNotFound as exc:
        raise _map_not_found(exc) from exc


# ── Pipeline management ──


class PipelineStatusResponse(BaseModel):
    """Pipeline status + data health summary."""

    recent_runs: list[dict[str, object]] = Field(default_factory=list)
    data_stats: dict[str, object] = Field(default_factory=dict)


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
    from app.models.pipeline_models import PipelineRun as PR

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