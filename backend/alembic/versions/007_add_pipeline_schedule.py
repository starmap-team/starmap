"""Add pipeline_schedules table and selected_stages to pipeline_runs.

Revision ID: 007
Revises: 006
Create Date: 2026-07-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add selected_stages to pipeline_runs
    op.add_column(
        "pipeline_runs",
        sa.Column("selected_stages", postgresql.JSON(), nullable=True),
    )

    # Create pipeline_schedules table
    op.create_table(
        "pipeline_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cron_expression", sa.String(50), nullable=False),
        sa.Column("run_type", sa.String(20), nullable=False, server_default="incremental"),
        sa.Column("selected_stages", postgresql.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("pipeline_schedules")
    op.drop_column("pipeline_runs", "selected_stages")
