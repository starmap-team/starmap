"""Add selected_sources to pipeline_runs + pipeline_schedules (D8, 2026-08-12).

背景 (deep-interview D8 裁决): 用户要求流水线爬取改为「手动可配置自选源 + 定时选源」，
而非当前固定抓取全部 active 的 crawler/api/rss 源。PipelineRun/PipelineSchedule 已有
selected_stages（阶段选择），新增 selected_sources（源选择）对称支持：
- null / [] = 全部源（默认行为，向后兼容）
- ["v2ex", "remotive"] = 仅爬取指定源

前端 TriggerDialog / ScheduleForm 提供多选；_get_crawl_configs 按 run.selected_sources
过滤 DataSourceRecord。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "035"
down_revision: tuple[str, ...] = ("034",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("selected_sources", sa.JSON(), nullable=True,
                  comment="List of source names to crawl; null/empty = all sources"),
    )
    op.add_column(
        "pipeline_schedules",
        sa.Column("selected_sources", sa.JSON(), nullable=True,
                  comment="List of source names to crawl; null/empty = all sources"),
    )


def downgrade() -> None:
    op.drop_column("pipeline_schedules", "selected_sources")
    op.drop_column("pipeline_runs", "selected_sources")
