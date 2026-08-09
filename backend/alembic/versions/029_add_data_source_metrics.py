"""Add data_source_metrics table (Phase 15-04 Task 1, 2026-08-07 补建).

health_monitor.record_metric 依赖此表记录每次爬取指标 (24h success_rate/
错误加权熔断/自动恢复), 但基线迁移遗漏 → 表从未建 → data_sources 的
valid_records/avg_quality_score 从不更新 → 数据质量评估恒 0。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "029"
down_revision: tuple[str, str] = ("020", "028")  # merge 预存分叉 (020 与 021-028 并行)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_source_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("records_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_duplicate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_data_source_metrics_source_id", "data_source_metrics", ["source_id"])
    op.create_index("ix_data_source_metrics_run_id", "data_source_metrics", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_data_source_metrics_run_id", table_name="data_source_metrics")
    op.drop_index("ix_data_source_metrics_source_id", table_name="data_source_metrics")
    op.drop_table("data_source_metrics")
