"""Admin API.

This file was sanitized to ASCII-only because the original Chinese
docstrings contained non-printable characters that caused runtime
SyntaxError during uvicorn reload.
"""

from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quality import _build_quality_dashboard
from app.config import settings
from app.dependencies import get_db_session
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    ReviewQueue,
    SkillRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class SourceConfig(BaseModel):
    id: int
    name: str
    authority_score: float = Field(ge=0.0, le=1.0)
    source_type: str
    record_count: int = 0


class SourceListResponse(BaseModel):
    items: list[SourceConfig] = Field(default_factory=list)


class AuditItem(BaseModel):
    id: int
    type: str
    name: str
    trust: int = Field(ge=0, le=100)
    status: str


class AuditUpdateRequest(BaseModel):
    """Partial update for a review-queue item."""

    name: str | None = Field(default=None, min_length=1)
    trust: int | None = Field(default=None, ge=0, le=100)


class AuditQueueResponse(BaseModel):
    items: list[AuditItem] = Field(default_factory=list)


class AdminStatsResponse(BaseModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    total_positions: int = Field(ge=0)
    total_skills: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    pending_review: int = Field(ge=0)


class ResetDemoResponse(BaseModel):
    ok: bool = True
    review_items: int = Field(ge=0)


_DEMO_REVIEW_SEED = [
    {"entity_type": "skill", "entity_name": "AI Agent Dev", "status": "pending", "payload": {"trust": 58}},
    {"entity_type": "position", "entity_name": "LLM Application Engineer", "status": "pending", "payload": {"trust": 64}},
    {"entity_type": "skill", "entity_name": "Spring AI", "status": "pending", "payload": {"trust": 72}},
    {"entity_type": "skill", "entity_name": "RAG", "status": "pending", "payload": {"trust": 45}},
]


async def _build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    dashboard = await _build_quality_dashboard(session)

    try:
        # Run separate queries to avoid cartesian product across 4 unrelated tables.
        total_positions = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(PositionRecord)
            )).scalar() or 0
        )
        total_skills = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(SkillRecord)
            )).scalar() or 0
        )
        total_edges = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(PositionSkillRelation)
            )).scalar() or 0
        )
        avg_value = float(
            (await session.execute(
                sa.select(
                    sa.func.coalesce(
                        sa.func.avg(JDExtractionRecord.confidence), 0.0
                    )
                )
            )).scalar() or 0.0
        )

        # Count pending review items from DB
        pending_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
                .where(ReviewQueue.status == "pending")
            )).scalar() or 0
        )
    except Exception:
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0

    return AdminStatsResponse(
        total_nodes=total_positions + total_skills,
        total_edges=total_edges,
        total_positions=total_positions,
        total_skills=total_skills,
        avg_confidence=avg_value,
        hallucination_rate=dashboard.hallucination_rate,
        pending_review=pending_count,
    )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """Admin overview stats."""
    return await _build_admin_stats(session)


@router.get("/sources", response_model=SourceListResponse)
async def get_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceListResponse:
    """Return data sources from actual crawl data."""
    try:
        result = await session.execute(
            sa.text("SELECT source_platform, COUNT(*) as cnt FROM raw_jd_records GROUP BY source_platform ORDER BY cnt DESC")
        )
        rows = result.fetchall()
        sources = []
        platform_scores = settings.authority_scores
        for idx, (platform, cnt) in enumerate(rows, 1):
            score = platform_scores.get(platform, settings.authority_default_score)
            stype = "official" if score >= 0.85 else "aggregator"
            sources.append(SourceConfig(
                id=idx, name=platform, authority_score=score,
                source_type=stype, record_count=cnt,
            ))
        return SourceListResponse(items=sources)
    except Exception as exc:
        logger.warning("Failed to query data sources: {}", exc)
        return SourceListResponse(items=[])


@router.get("/review-queue", response_model=AuditQueueResponse)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditQueueResponse:
    """Return pending review items from DB; auto-seed if table is empty."""


    try:
        # Check if there are any rows at all in the review_queue table
        total_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
            )).scalar() or 0
        )

        if total_count == 0:
            # Auto-seed from template data (only once, when table is empty)
            for seed in _DEMO_REVIEW_SEED:
                session.add(ReviewQueue(**seed))
            await session.commit()

        stmt = (
            sa.select(ReviewQueue)
            .where(ReviewQueue.status == "pending")
            .order_by(ReviewQueue.id.desc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        items = []
        for r in rows:
            trust = int((r.payload or {}).get("trust", 50))
            items.append(
                AuditItem(
                    id=r.id,
                    type=r.entity_type,
                    name=r.entity_name,
                    trust=trust,
                    status=r.status,
                )
            )
        return AuditQueueResponse(items=items)
    except Exception:
        return AuditQueueResponse(items=[])


@router.post("/audit/{item_id}/approve", response_model=AuditItem)
async def approve_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Approve a review queue item."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    row.status = "approved"
    await session.commit()
    trust = int((row.payload or {}).get("trust", 50))
    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=trust,
        status="approved",
    )


@router.post("/audit/{item_id}/reject", response_model=AuditItem)
async def reject_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Reject a review queue item."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    row.status = "rejected"
    await session.commit()
    trust = int((row.payload or {}).get("trust", 50))
    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=trust,
        status="rejected",
    )


@router.put("/review-queue/{item_id}", response_model=AuditItem)
@router.patch("/review-queue/{item_id}", response_model=AuditItem, include_in_schema=False)
async def update_review_queue_item(
    item_id: int,
    body: AuditUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Update name and/or trust of a review queue item (ADMIN-02 save loop)."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")

    if body.name is not None:
        row.entity_name = body.name
    if body.trust is not None:
        # ponytail: reassign dict so SQLAlchemy JSON dirty-tracking fires
        payload = dict(row.payload or {})
        payload["trust"] = body.trust
        row.payload = payload
    await session.commit()

    trust = int((row.payload or {}).get("trust", 50))
    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=trust,
        status=row.status,
    )


@router.post("/seed/reset", response_model=ResetDemoResponse)
@router.post("/reset-demo", response_model=ResetDemoResponse, include_in_schema=False)
async def reset_demo_seed(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResetDemoResponse:
    """Reset demo review queue state — re-seed the review_queue table."""


    # Clear existing pending review items
    await session.execute(
        sa.delete(ReviewQueue).where(ReviewQueue.status == "pending")
    )

    # Seed default demo items from shared template
    demo_items = [ReviewQueue(**seed) for seed in _DEMO_REVIEW_SEED]
    for item in demo_items:
        session.add(item)
    await session.commit()

    return ResetDemoResponse(ok=True, review_items=len(demo_items))


# ── Graph Node CRUD (for Admin panel) ──


# ── Sub-routers (Phase 7 admin domain split) ──
# ── Sub-routers (Phase 7 admin domain split) ──
from app.api.v1.admin_graph_nodes import router as graph_nodes_router  # noqa: E402
from app.api.v1.admin_prompts import router as prompts_router  # noqa: E402

router.include_router(prompts_router, prefix="")
router.include_router(graph_nodes_router, prefix="")
