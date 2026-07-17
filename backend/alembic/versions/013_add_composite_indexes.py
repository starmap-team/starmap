"""Add composite indexes for learning_progress and skill_timeseries.

learning_progress(plan_id, skill_name): supports looking up a specific skill's
progress within a plan — the most common query pattern from the learning center
dashboard and progress tracker.

skill_timeseries(skill_name, window_start): supports querying a skill's frequency
history across time windows — the core access pattern for trend analysis and
Z-score emerging-skill detection.

Revision ID: 013
Revises: 012
Create Date: 2026-07-12
"""
from collections.abc import Sequence

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # UAT 2026-07-16: 索引已在 006_add_learning_tables.py (ix_learning_progress_plan_skill)
    # 和 003_add_evolution_tables.py (skill_timeseries 单字段索引) 阶段创建过；
    # 直接 create_index 在全新库上会被首次运行命中 DuplicateTableError。
    # 这里用 IF NOT EXISTS 兼容已建库与新库两种场景。
    op.create_index(
        "ix_learning_progress_plan_skill",
        "learning_progress",
        ["plan_id", "skill_name"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_skill_timeseries_skill_window",
        "skill_timeseries",
        ["skill_name", "window_start"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_timeseries_skill_window", table_name="skill_timeseries", if_exists=True)
    op.drop_index("ix_learning_progress_plan_skill", table_name="learning_progress", if_exists=True)
