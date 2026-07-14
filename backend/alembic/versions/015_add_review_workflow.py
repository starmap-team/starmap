"""Add review workflow to position_records + skill_records.

Phase 23 enterprise review-state redesign:
- 4-state lifecycle: draft -> pending_review -> approved | rejected
- Existing 38 positions and 269 skills are grandfathered as 'approved'
  to preserve public visibility and avoid breaking the live graph.
- New ingestion paths (POST /extract/jd, batch extract, /loop/run) now
  default to 'pending_review' so every new entity is human-curated
  before publication.
- A new review_audit_log table records every transition with actor,
  previous_status, new_status, reason, and timestamp.

Revision ID: 015
Revises: 014
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Allowed status values — used by the CHECK constraint.
ALLOWED_STATUSES = ("draft", "pending_review", "approved", "rejected")


def upgrade() -> None:
    # ── 1. Add review columns to position_records (nullable initially) ──
    op.add_column(
        "position_records",
        sa.Column("review_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "position_records",
        sa.Column("created_by", sa.String(64), nullable=True),
    )
    op.add_column(
        "position_records",
        sa.Column("reviewed_by", sa.String(64), nullable=True),
    )
    op.add_column(
        "position_records",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "position_records",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "position_records",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 2. Add review columns to skill_records ──
    op.add_column(
        "skill_records",
        sa.Column("review_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "skill_records",
        sa.Column("created_by", sa.String(64), nullable=True),
    )
    op.add_column(
        "skill_records",
        sa.Column("reviewed_by", sa.String(64), nullable=True),
    )
    op.add_column(
        "skill_records",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "skill_records",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "skill_records",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 3. Backfill: existing 38 positions + 269 skills → 'approved' (grandfathered) ──
    op.execute(
        "UPDATE position_records SET review_status = 'approved', reviewed_at = NOW(), reviewed_by = 'system:grandfather' WHERE review_status IS NULL"
    )
    op.execute(
        "UPDATE skill_records SET review_status = 'approved', reviewed_at = NOW(), reviewed_by = 'system:grandfather' WHERE review_status IS NULL"
    )

    # ── 4. Add default for new rows + enforce NOT NULL ──
    op.alter_column(
        "position_records",
        "review_status",
        existing_type=sa.String(20),
        nullable=False,
        server_default="pending_review",
    )
    op.alter_column(
        "skill_records",
        "review_status",
        existing_type=sa.String(20),
        nullable=False,
        server_default="pending_review",
    )

    # ── 5. CHECK constraints to enforce enum values ──
    op.create_check_constraint(
        "ck_position_records_review_status",
        "position_records",
        f"review_status IN {ALLOWED_STATUSES}",
    )
    op.create_check_constraint(
        "ck_skill_records_review_status",
        "skill_records",
        f"review_status IN {ALLOWED_STATUSES}",
    )

    # ── 6. Indexes for fast filtering ──
    op.create_index(
        "ix_position_records_review_status",
        "position_records",
        ["review_status"],
    )
    op.create_index(
        "ix_skill_records_review_status",
        "skill_records",
        ["review_status"],
    )

    # ── 7. Audit log table (append-only) ──
    op.create_table(
        "review_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(20), nullable=False),  # 'position' | 'skill'
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),  # 'submit'|'approve'|'reject'|'unpublish'|'grandfather'
        sa.Column("actor", sa.String(64), nullable=True),
        sa.Column("previous_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "entity_type IN ('position', 'skill')",
            name="ck_review_audit_log_entity_type",
        ),
        sa.CheckConstraint(
            "action IN ('submit', 'approve', 'reject', 'unpublish', 'grandfather')",
            name="ck_review_audit_log_action",
        ),
    )
    op.create_index(
        "ix_review_audit_log_entity",
        "review_audit_log",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_review_audit_log_created_at",
        "review_audit_log",
        ["created_at"],
    )

    # ── 8. Record grandfather events in the audit log ──
    op.execute(
        """
        INSERT INTO review_audit_log (entity_type, entity_id, action, actor, previous_status, new_status, reason)
        SELECT 'position', id, 'grandfather', 'system:grandfather', NULL, 'approved',
               'Existing data before review-workflow rollout (migration 015)'
        FROM position_records
        WHERE review_status = 'approved' AND reviewed_by = 'system:grandfather'
        """
    )
    op.execute(
        """
        INSERT INTO review_audit_log (entity_type, entity_id, action, actor, previous_status, new_status, reason)
        SELECT 'skill', id, 'grandfather', 'system:grandfather', NULL, 'approved',
               'Existing data before review-workflow rollout (migration 015)'
        FROM skill_records
        WHERE review_status = 'approved' AND reviewed_by = 'system:grandfather'
        """
    )


def downgrade() -> None:
    # Drop audit log first (it references position/skill UUIDs)
    op.drop_index("ix_review_audit_log_created_at", table_name="review_audit_log")
    op.drop_index("ix_review_audit_log_entity", table_name="review_audit_log")
    op.drop_table("review_audit_log")

    # Drop indexes
    op.drop_index("ix_skill_records_review_status", table_name="skill_records")
    op.drop_index("ix_position_records_review_status", table_name="position_records")

    # Drop CHECK constraints
    op.drop_constraint("ck_skill_records_review_status", "skill_records", type_="check")
    op.drop_constraint("ck_position_records_review_status", "position_records", type_="check")

    # Drop columns (skill)
    op.drop_column("skill_records", "submitted_at")
    op.drop_column("skill_records", "rejection_reason")
    op.drop_column("skill_records", "reviewed_at")
    op.drop_column("skill_records", "reviewed_by")
    op.drop_column("skill_records", "created_by")
    op.drop_column("skill_records", "review_status")

    # Drop columns (position)
    op.drop_column("position_records", "submitted_at")
    op.drop_column("position_records", "rejection_reason")
    op.drop_column("position_records", "reviewed_at")
    op.drop_column("position_records", "reviewed_by")
    op.drop_column("position_records", "created_by")
    op.drop_column("position_records", "review_status")
