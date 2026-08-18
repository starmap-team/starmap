"""ReviewAuditLog — append-only audit log for position/skill review transitions.

Every status change (submit, approve, reject, unpublish, grandfather) is
recorded here with the actor, previous status, new status, reason, and
timestamp. This table is the canonical history of who approved what and
when, supporting both operational debugging and compliance audits.

Enterprise review-workflow redesign.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ReviewAuditLog(Base):
    """Append-only audit log for review-state transitions."""

    __tablename__ = "review_audit_log"

 # Auto-incrementing bigint PK for fast inserts + monotonic ordering.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
 # 'position' | 'skill' — what kind of entity transitioned.
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
 # The UUID of the entity (FK-style reference, but polymorphic so no DB FK).
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
 # 'submit' | 'approve' | 'reject' | 'unpublish' | 'grandfather'
    action: Mapped[str] = mapped_column(String(20), nullable=False)
 # Username of the actor (admin, or 'system:grandfather', 'system:extraction', etc.)
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
 # Status before the transition (NULL for initial grandfather).
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
 # Status after the transition.
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
 # Free-form reason / comment (required for reject, optional for approve).
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
 # Server-side timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=None,
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('position', 'skill')",
            name="ck_review_audit_log_entity_type",
        ),
        CheckConstraint(
            "action IN ('submit', 'approve', 'reject', 'unpublish', 'grandfather')",
            name="ck_review_audit_log_action",
        ),
        Index("ix_review_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_review_audit_log_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewAuditLog {self.entity_type}#{self.entity_id} "
            f"{self.previous_status or '∅'}→{self.new_status} by {self.actor or 'system'}>"
        )
