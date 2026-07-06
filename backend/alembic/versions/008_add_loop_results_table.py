"""Add loop_results table.

Revision ID: 008
Revises: 007
Create Date: 2026-07-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loop_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(100), unique=True, nullable=False),
        sa.Column(
            "steps_json",
            postgresql.JSONB(),
            nullable=True,
            server_default="{}",
            comment="Serialized list of step results",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="running",
            comment="'running' | 'completed' | 'failed'",
        ),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_loop_results_run_id", "loop_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_loop_results_run_id", table_name="loop_results")
    op.drop_table("loop_results")
