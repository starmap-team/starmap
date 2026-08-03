"""Add match_results table for persisted match outcomes.

Revision ID: 004
Revises: 003
Create Date: 2026-06-28 01:00:00.000000

NOTE (2026-07-24): This file was renamed from 004_add_match_results_table.py to
004b_add_match_results_table.py to disambiguate from 004a_add_changelog_status.py.
Both share revision ID "004" (branch point from 003). This is a known Alembic
branch — use `alembic upgrade 017` to specify the target explicitly.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_results",
        sa.Column("match_id", sa.String(64), primary_key=True),
        sa.Column("target_position", sa.String(255), nullable=False),
        sa.Column("person_skills", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("matched_skills", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("missing_required", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("missing_bonus", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("gap_report", postgresql.JSON(), nullable=True),
        sa.Column("learning_path", postgresql.JSON(), nullable=True),
        sa.Column("cii", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_match_results_target_position", "match_results", ["target_position"])
    op.create_index("ix_match_results_created_at", "match_results", ["created_at"])


def downgrade() -> None:
    op.drop_table("match_results")
