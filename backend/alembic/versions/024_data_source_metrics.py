"""Add data_source_metrics table + last_successful_crawl_at column (Phase 15-04).

Revision ID: 024
Revises: 023
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision: str = "024"
down_revision: str | None = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. data_source_metrics 表 (Task 1)
    op.create_table(
        "data_source_metrics",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("records_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_duplicate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("idx_dsm_source_started", "data_source_metrics", ["source_id", "started_at"])
    op.create_index("idx_dsm_status", "data_source_metrics", ["status"])

    # 2. data_sources.last_successful_crawl_at (Task 4 - Fix M4)
    op.add_column(
        "data_sources",
        sa.Column("last_successful_crawl_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 回填: status=active 的 source 用 last_crawl_at 作为初始值
    op.execute(
        sa.text(
            "UPDATE data_sources SET last_successful_crawl_at = last_crawl_at WHERE status = 'active'"
        )
    )


def downgrade() -> None:
    op.drop_column("data_sources", "last_successful_crawl_at")
    op.drop_index("idx_dsm_status", table_name="data_source_metrics")
    op.drop_index("idx_dsm_source_started", table_name="data_source_metrics")
    op.drop_table("data_source_metrics")
