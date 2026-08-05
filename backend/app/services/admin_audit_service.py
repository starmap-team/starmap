"""Admin audit service — business logic for review queue operations.

Extracted from admin.py so that the API layer remains a thin HTTP wrapper.
All functions accept an AsyncSession and return domain objects or raise
domain exceptions (AuditItemNotFound, etc.) — no HTTPException here.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from neo4j.exceptions import Neo4jError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quality import _build_quality_dashboard
from app.exceptions import StarMapError
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    ReviewQueue,
    SkillRecord,
)

# ── Domain exceptions ──


class AuditItemNotFound(Exception):  # noqa: N818
    """Raised when a review-queue item does not exist."""


# ── Pydantic-like result types (shared with API layer) ──
# Kept here so service functions return typed objects instead of raw dicts.

from pydantic import BaseModel, Field  # noqa: E402

from app.schemas.admin import AuditItem  # noqa: E402


class AdminStatsResponse(BaseModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    total_positions: int = Field(ge=0)
    total_skills: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    pending_review: int = Field(ge=0)


# ── Helpers ──

_SKILL_ENTITY_TYPES = frozenset({"skill", "skill_alias", "new_skill"})
_POSITION_ENTITY_TYPES = frozenset({"position", "new_position"})


def _trust_from_payload(payload: dict | None) -> int:
    """Extract trust score from ReviewQueue payload, default 50."""
    return int((payload or {}).get("trust", 50))


# LOOP-07: Neo4j sync on approve/reject
async def _sync_neo4j_on_audit(neo4j_driver: Any, item_type: str, item_name: str, status: str) -> None:
    """Sync audit result to Neo4j graph (non-blocking).

    Phase 5 Step 2 修复: 用 MERGE 而非 MATCH+SET，确保节点不存在时自动创建。
    canonical_id 是 Neo4j 与 PG 同步的桥梁。
    """
    if not neo4j_driver:
        return
    label_map = {"position": "Position", "new_position": "Position", "skill": "Skill", "skill_alias": "Skill", "new_skill": "Skill"}
    label = label_map.get(item_type)
    if not label:
        return
    if not label.isalnum():
        return
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.db.session import get_async_engine
        from app.models.extraction_models import PositionRecord, SkillRecord

        # 查 PG 拿到 canonical_id（用 PG 实际字段名）
        engine = get_async_engine()
        async with engine.begin() as conn:
            session = AsyncSession(bind=conn)
            if label == "Position":
                result = await session.execute(
                    select(PositionRecord.id, PositionRecord.name, PositionRecord.industry, PositionRecord.review_status)
                    .where(PositionRecord.name == item_name)
                )
                row = result.first()
                if not row:
                    logger.warning("Neo4j sync: PG PositionRecord not found for '{}'", item_name)
                    return
                canonical_id = str(row[0])
                name = row[1]
                industry = row[2] or ""
                review_status = row[3] or status
            else:  # Skill
                result = await session.execute(
                    select(SkillRecord.id, SkillRecord.name, SkillRecord.review_status)
                    .where(SkillRecord.name == item_name)
                )
                row = result.first()
                if not row:
                    logger.warning("Neo4j sync: PG SkillRecord not found for '{}'", item_name)
                    return
                canonical_id = str(row[0])
                name = row[1]
                review_status = row[2] or status
                industry = ""

        trust = 1.0 if status == "approved" else 0.0

        # 用 canonical_id MERGE，确保幂等
        async with neo4j_driver.session() as s:
            if label == "Position":
                await s.run(
                    """
                    MERGE (n:Position {canonical_id: $cid})
                    SET n.name = $name,
                        n.industry = $industry,
                        n.review_status = $review_status,
                        n.trust_score = $trust,
                        n.status = $status,
                        n.synced_at = datetime()
                    """,
                    cid=canonical_id,
                    name=name,
                    industry=industry,
                    review_status=review_status,
                    trust=trust,
                    status=status,
                )
            else:
                await s.run(
                    """
                    MERGE (n:Skill {canonical_id: $cid})
                    SET n.name = $name,
                        n.review_status = $review_status,
                        n.trust_score = $trust,
                        n.status = $status,
                        n.synced_at = datetime()
                    """,
                    cid=canonical_id,
                    name=name,
                    review_status=review_status,
                    trust=trust,
                    status=status,
                )
        logger.info("Neo4j sync: {} '{}' (canonical={}) → status={}", label, name, canonical_id, status)
    except (Neo4jError, SQLAlchemyError) as e:
        logger.warning("Neo4j sync failed (non-blocking): {}", e)
    except Exception as e:
        logger.exception("Unexpected error in Neo4j sync (non-blocking): {}", e)


def _audit_item_from_row(row: ReviewQueue, *, status_override: str | None = None) -> AuditItem:
    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=_trust_from_payload(row.payload),
        status=status_override or row.status,
    )


# ── Service functions ──


async def build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    """Aggregate DB counts + quality dashboard into admin stats."""
    dashboard = await _build_quality_dashboard(session)

    try:
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
        pending_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
                .where(ReviewQueue.status == "pending")
            )).scalar() or 0
        )
    except (SQLAlchemyError, StarMapError):
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0
        logger.warning("Admin stats DB query failed, using fallback")
    except Exception:
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0
        logger.exception("Unexpected error in admin stats DB query")

    return AdminStatsResponse(
        total_nodes=total_positions + total_skills,
        total_edges=total_edges,
        total_positions=total_positions,
        total_skills=total_skills,
        avg_confidence=avg_value,
        hallucination_rate=dashboard.hallucination_rate,
        pending_review=pending_count,
    )


async def get_review_queue(session: AsyncSession) -> list[AuditItem]:
    """Return all pending review-queue items."""
    stmt = (
        sa.select(ReviewQueue)
        .where(ReviewQueue.status == "pending")
        .order_by(ReviewQueue.id.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_audit_item_from_row(r) for r in rows]


async def approve_audit(
    item_id: int,
    session: AsyncSession,
    neo4j_driver: Any | None = None,
    actor: str = "admin:review_queue",
) -> AuditItem:
    """Approve a review-queue item and sync to skill/position tables + Neo4j (LOOP-07).

    Phase 24 fix: when a new SkillRecord / PositionRecord is created
    from an approved ReviewQueue row, set review_status='approved' so
    the new Phase 23 review-workflow column stays consistent. Previously
    the row was created with the column default 'pending_review' —
    meaning the entity was effectively invisible to /positions and the
    admin would have to re-approve it through the content-review tab.
    """
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    row.status = "approved"

    now = datetime.now(UTC)

    # Sync approved data to actual tables
    if row.entity_type in _SKILL_ENTITY_TYPES:
        existing = await session.execute(
            sa.select(SkillRecord).where(SkillRecord.name == row.entity_name)
        )
        if existing.scalar_one_or_none() is None:
            # Preserve category from payload if the operator set one
            # (Phase 24 evolution orchestrator stores it under
            # payload["category"]; legacy path leaves it None).
            payload = row.payload or {}
            category = payload.get("category") or "general"
            session.add(SkillRecord(
                name=row.entity_name,
                category=category,
                source_count=1,
                review_status="approved",
                reviewed_by=actor,
                reviewed_at=now,
            ))
    elif row.entity_type in _POSITION_ENTITY_TYPES:
        existing = await session.execute(
            sa.select(PositionRecord).where(PositionRecord.name == row.entity_name)
        )
        if existing.scalar_one_or_none() is None:
            session.add(PositionRecord(
                name=row.entity_name,
                review_status="approved",
                reviewed_by=actor,
                reviewed_at=now,
            ))

    await session.commit()

    # Sync to Neo4j (non-blocking)
    await _sync_neo4j_on_audit(neo4j_driver, row.entity_type, row.entity_name, "approved")

    return _audit_item_from_row(row, status_override="approved")


async def reject_audit(item_id: int, session: AsyncSession, neo4j_driver: Any | None = None) -> AuditItem:
    """Reject a review-queue item and sync to Neo4j (LOOP-07)."""
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    row.status = "rejected"
    await session.commit()

    # Sync to Neo4j (non-blocking)
    await _sync_neo4j_on_audit(neo4j_driver, row.entity_type, row.entity_name, "rejected")

    return _audit_item_from_row(row, status_override="rejected")


async def update_review_queue_item(
    item_id: int, *, name: str | None = None, trust: int | None = None,
    session: AsyncSession | None = None,
) -> AuditItem:
    """Partial update of a review-queue item's name and/or trust."""
    if session is None:
        raise AuditItemNotFound("Session is required for update_review_queue_item")
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    if name is not None:
        row.entity_name = name
    if trust is not None:
        # Reassign dict so SQLAlchemy JSON dirty-tracking fires
        payload = dict(row.payload or {})
        payload["trust"] = trust
        row.payload = payload

    await session.commit()
    return _audit_item_from_row(row)


async def batch_audit(
    item_ids: list[int], action: str, session: AsyncSession,
    actor: str = "admin:batch",
) -> list[AuditItem]:
    """Batch approve or reject multiple review-queue items.

    Phase 24 fix: same as approve_audit — newly-created SkillRecord /
    PositionRecord get review_status='approved' so the Phase 23 column
    stays consistent.
    """
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id.in_(item_ids))
    )
    rows = result.scalars().all()
    if not rows:
        raise AuditItemNotFound("No audit items found for the given IDs")

    now = datetime.now(UTC)
    results: list[AuditItem] = []
    for row in rows:
        if action == "approve":
            row.status = "approved"
            if row.entity_type in _SKILL_ENTITY_TYPES:
                existing = await session.execute(
                    sa.select(SkillRecord).where(SkillRecord.name == row.entity_name)
                )
                if existing.scalar_one_or_none() is None:
                    payload = row.payload or {}
                    category = payload.get("category") or "general"
                    session.add(SkillRecord(
                        name=row.entity_name,
                        category=category,
                        source_count=1,
                        review_status="approved",
                        reviewed_by=actor,
                        reviewed_at=now,
                    ))
            elif row.entity_type in _POSITION_ENTITY_TYPES:
                existing = await session.execute(
                    sa.select(PositionRecord).where(PositionRecord.name == row.entity_name)
                )
                if existing.scalar_one_or_none() is None:
                    session.add(PositionRecord(
                        name=row.entity_name,
                        review_status="approved",
                        reviewed_by=actor,
                        reviewed_at=now,
                    ))
        else:
            row.status = "rejected"

        results.append(_audit_item_from_row(row))

    await session.commit()
    return results
