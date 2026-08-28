"""Add quality_hint + last_retry_at to position_records (Batch 0 truth source, 2026-08-28).

共识计划批0 真相源：统一过滤函数 `position_filter.is_graph_eligible()` 需要
PG 侧标记列支撑——
- quality_hint: 岗位质量标记（no_skills / unclassified / non_it / NULL=ok），
  reconcile_all 快照查询据此排除隐藏岗位（防「剪枝→回填」振荡）
- last_retry_at: 定时重试幂等（每日只重试一次空技能/未分类岗位）

两列均可空，纯增量，不破坏现有数据。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "040"
down_revision: tuple[str, ...] = ("039",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_records",
        sa.Column("quality_hint", sa.String(32), nullable=True, comment="岗位质量标记: no_skills/unclassified/non_it"),
    )
    op.add_column(
        "position_records",
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True, comment="定时重试时间戳(幂等)"),
    )
    # 存量扫描辅助索引（审核队列 category 筛选用）
    op.create_index(
        "ix_position_records_quality_hint",
        "position_records",
        ["quality_hint"],
    )


def downgrade() -> None:
    op.drop_index("ix_position_records_quality_hint", table_name="position_records")
    op.drop_column("position_records", "last_retry_at")
    op.drop_column("position_records", "quality_hint")
