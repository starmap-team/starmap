"""Review service — state machine for position/skill review workflow.

Phase 23 enterprise review-workflow redesign.

State transitions (all in single PG transaction, with audit log):

    draft ──submit──> pending_review ──approve──> approved
                          │                  └──unpublish──> draft
                          └──reject──> rejected
                              │
                              └──revise──> draft

Key invariants:
- Only `approved` entities are visible to the public API.
- Every transition appends a row to `review_audit_log`.
- Approval does not require Neo4j success — Neo4j sync is best-effort
  and a failure is recorded but does not roll back the PG state.
- Re-approval is idempotent: calling approve() on an already-approved
  entity with no status change does NOT create a duplicate audit log.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_models import PositionRecord, SkillRecord
from app.models.review_audit_log import ReviewAuditLog

# ── Status enum ──

Status = Literal["draft", "pending_review", "approved", "rejected"]
Action = Literal["submit", "approve", "reject", "unpublish", "grandfather"]
EntityType = Literal["position", "skill"]

ALLOWED_STATUSES: tuple[Status, ...] = ("draft", "pending_review", "approved", "rejected")


# ── Domain exceptions ──


class ReviewNotFound(Exception):
    """Entity not found for review operation."""


class InvalidStateTransition(Exception):
    """Attempted transition is not allowed from the current state."""


class MissingRejectionReason(Exception):
    """Reject requires a non-empty reason."""


# ── Public result types ──


@dataclass
class ReviewItem:
    """Unified view of an item pending review (or recently actioned)."""

    entity_type: EntityType
    entity_id: uuid.UUID
    name: str
    industry: str | None
    review_status: Status
    created_by: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    submitted_at: datetime | None
    rejection_reason: str | None
    created_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "name": self.name,
            "industry": self.industry,
            "review_status": self.review_status,
            "created_by": self.created_by,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Helpers ──


def _now() -> datetime:
    return datetime.now(UTC)


def _model_for(entity_type: EntityType) -> type[PositionRecord] | type[SkillRecord]:
    if entity_type == "position":
        return PositionRecord
    if entity_type == "skill":
        return SkillRecord
    raise ValueError(f"Unknown entity_type: {entity_type}")


async def _get_entity(session: AsyncSession, entity_type: EntityType, entity_id: uuid.UUID) -> PositionRecord | SkillRecord:
    model = _model_for(entity_type)
    result: sa.Result[tuple[PositionRecord | SkillRecord]] = await session.execute(sa.select(model).where(model.id == entity_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ReviewNotFound(f"{entity_type} {entity_id} not found")
    return row


async def _record_transition(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    action: Action,
    actor: str | None,
    previous_status: Status | None,
    new_status: Status,
    reason: str | None,
) -> None:
    """Append a row to review_audit_log."""
    log = ReviewAuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        created_at=_now(),
    )
    session.add(log)


# ── State machine operations ──


async def submit_for_review(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    actor: str,
) -> ReviewItem:
    """Move draft → pending_review.

    Idempotent: if the entity is already `pending_review`, this is a no-op
    (no duplicate audit log row).
    """
    row = await _get_entity(session, entity_type, entity_id)
    if row.review_status == "pending_review":
        return _to_item(entity_type, row)
    if row.review_status not in ("draft", "rejected"):
        raise InvalidStateTransition(
            f"Cannot submit {row.review_status} entity for review; must be draft or rejected"
        )

    previous = cast(Status, row.review_status)
    row.review_status = "pending_review"
    row.submitted_at = _now()
    # Clear any previous rejection reason — it's a fresh submission.
    if row.review_status == "pending_review" and previous == "rejected":
        row.rejection_reason = None
    await _record_transition(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action="submit",
        actor=actor,
        previous_status=previous,
        new_status="pending_review",
        reason=None,
    )
    await session.commit()
    await session.refresh(row)
    return _to_item(entity_type, row)


async def approve(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    actor: str,
    reason: str | None = None,
) -> ReviewItem:
    """Move pending_review → approved.

    Idempotent: re-approving an already-approved entity is a no-op.
    Raises InvalidStateTransition for `draft`/`rejected` (use submit/revise first).
    """
    row = await _get_entity(session, entity_type, entity_id)
    if row.review_status == "approved":
        return _to_item(entity_type, row)
    if row.review_status != "pending_review":
        raise InvalidStateTransition(
            f"Cannot approve {row.review_status} entity; must be pending_review"
        )

    previous = cast(Status, row.review_status)
    row.review_status = "approved"
    row.reviewed_by = actor
    row.reviewed_at = _now()
    row.rejection_reason = None
    await _record_transition(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action="approve",
        actor=actor,
        previous_status=previous,
        new_status="approved",
        reason=reason,
    )
    await session.commit()
    await session.refresh(row)
    return _to_item(entity_type, row)


async def reject(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    actor: str,
    reason: str,
) -> ReviewItem:
    """Move pending_review → rejected. Reason is required."""
    if not reason or not reason.strip():
        raise MissingRejectionReason("Reject requires a non-empty reason")
    row = await _get_entity(session, entity_type, entity_id)
    if row.review_status == "rejected":
        # Already rejected — return existing state without writing another log.
        return _to_item(entity_type, row)
    if row.review_status != "pending_review":
        raise InvalidStateTransition(
            f"Cannot reject {row.review_status} entity; must be pending_review"
        )

    previous = cast(Status, row.review_status)
    row.review_status = "rejected"
    row.reviewed_by = actor
    row.reviewed_at = _now()
    row.rejection_reason = reason.strip()
    await _record_transition(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action="reject",
        actor=actor,
        previous_status=previous,
        new_status="rejected",
        reason=reason.strip(),
    )
    await session.commit()
    await session.refresh(row)
    return _to_item(entity_type, row)


async def unpublish(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    actor: str,
    reason: str,
) -> ReviewItem:
    """Move approved → draft (admin override). Reason is required for audit."""
    if not reason or not reason.strip():
        raise MissingRejectionReason("Unpublish requires a reason for audit")
    row = await _get_entity(session, entity_type, entity_id)
    if row.review_status != "approved":
        raise InvalidStateTransition(
            f"Cannot unpublish {row.review_status} entity; must be approved"
        )

    previous = cast(Status, row.review_status)
    row.review_status = "draft"
    row.reviewed_by = actor
    row.reviewed_at = _now()
    row.rejection_reason = reason.strip()
    await _record_transition(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action="unpublish",
        actor=actor,
        previous_status=previous,
        new_status="draft",
        reason=reason.strip(),
    )
    await session.commit()
    await session.refresh(row)
    return _to_item(entity_type, row)


# ── Query operations ──


def _to_item(entity_type: EntityType, row: PositionRecord | SkillRecord) -> ReviewItem:
    # SkillRecord has no created_at — fall back to first_detected_at.
    created_at = getattr(row, "created_at", None) or getattr(row, "first_detected_at", None)
    return ReviewItem(
        entity_type=entity_type,
        entity_id=row.id,
        name=getattr(row, "name", ""),
        industry=getattr(row, "industry", None),
        review_status=cast(Status, row.review_status),
        created_by=row.created_by,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        submitted_at=row.submitted_at,
        rejection_reason=row.rejection_reason,
        created_at=created_at,
    )


async def list_by_status(
    session: AsyncSession,
    *,
    entity_type: EntityType | None = None,
    status: Status | None = None,
    limit: int = 50,
) -> list[ReviewItem]:
    """List entities by review status, optionally filtered by type.

    Returns most-recently-created first. SkillRecord has no created_at,
    so we fall back to first_detected_at for skills.
    """
    out: list[ReviewItem] = []
    types: tuple[EntityType, ...] = ("position", "skill") if entity_type is None else (entity_type,)
    for et in types:
        model = _model_for(et)
        sort_col = getattr(model, "created_at", None) or getattr(model, "first_detected_at", None)
        stmt: sa.Select[tuple[PositionRecord | SkillRecord]] = sa.select(model)
        if sort_col is not None:
            stmt = stmt.order_by(sort_col.desc())
        stmt = stmt.limit(limit)
        if status is not None:
            stmt = stmt.where(model.review_status == status)
        result = await session.execute(stmt)
        for row in result.scalars().all():
            out.append(_to_item(et, row))
    # Re-sort merged result by created_at desc (None values go last).
    out.sort(key=lambda r: r.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return out[:limit]


async def get_history(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    limit: int = 50,
) -> list[ReviewAuditLog]:
    """Return audit log entries for one entity, newest first."""
    result = await session.execute(
        sa.select(ReviewAuditLog)
        .where(
            ReviewAuditLog.entity_type == entity_type,
            ReviewAuditLog.entity_id == entity_id,
        )
        .order_by(ReviewAuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_status(session: AsyncSession) -> dict[str, int]:
    """Aggregate counts for admin stats."""
    out: dict[str, int] = {"position": 0, "skill": 0}
    for et in ("position", "skill"):
        model = _model_for(et)  # type: ignore[arg-type]
        result = await session.execute(
            sa.select(model.review_status, sa.func.count()).group_by(model.review_status)
        )
        for status, count in result.all():
            out[f"{et}_{status}"] = int(count)
            out[et] += int(count)
    return out
