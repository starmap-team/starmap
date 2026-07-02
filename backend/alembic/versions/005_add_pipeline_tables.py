"""Add pipeline_runs and data_sources tables.

Revision ID: 005
Revises: 004
Create Date: 2026-06-30 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pipeline_runs ──
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_type", sa.String(20), nullable=False, server_default="full"),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stages", postgresql.JSON(), nullable=True, server_default=sa.text("'[]'::json")),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_log", sa.Text(), nullable=True),
    )
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])

    # ── data_sources ──
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="crawler"),
        sa.Column("authority_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_crawl_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_quality_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("config", postgresql.JSON(), nullable=True),
    )
    op.create_index("ix_data_sources_name", "data_sources", ["name"], unique=True)
    op.create_index("ix_data_sources_status", "data_sources", ["status"])


def downgrade() -> None:
    op.drop_table("data_sources")
    op.drop_table("pipeline_runs")
