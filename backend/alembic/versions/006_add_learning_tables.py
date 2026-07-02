"""Add learning center tables.

Revision ID: 006
Revises: 005
Create Date: 2026-06-30 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── learning_plans ──
    op.create_table(
        "learning_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, server_default="anonymous"),
        sa.Column("position", sa.String(255), nullable=False),
        sa.Column("skills", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("match_score_at_creation", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("estimated_hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_learning_plans_user_id", "learning_plans", ["user_id"])
    op.create_index("ix_learning_plans_position", "learning_plans", ["position"])
    op.create_index("ix_learning_plans_status", "learning_plans", ["status"])

    # ── learning_progress ──
    op.create_table(
        "learning_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("importance", sa.String(20), nullable=False, server_default="required"),
        sa.Column("estimated_hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_learning_progress_plan_id", "learning_progress", ["plan_id"])
    op.create_index("ix_learning_progress_skill_name", "learning_progress", ["skill_name"])
    op.create_index(
        "ix_learning_progress_plan_skill",
        "learning_progress",
        ["plan_id", "skill_name"],
        unique=True,
    )

    # ── skill_prerequisites ──
    op.create_table(
        "skill_prerequisites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill", sa.String(255), nullable=False),
        sa.Column("prerequisite", sa.String(255), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_skill_prerequisites_skill", "skill_prerequisites", ["skill"])
    op.create_index("ix_skill_prerequisites_prerequisite", "skill_prerequisites", ["prerequisite"])
    op.create_index(
        "ix_skill_prerequisites_unique_edge",
        "skill_prerequisites",
        ["skill", "prerequisite"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("skill_prerequisites")
    op.drop_table("learning_progress")
    op.drop_table("learning_plans")
