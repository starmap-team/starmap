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

import sqlalchemy as sa

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_learning_progress_plan_skill",
        "learning_progress",
        ["plan_id", "skill_name"],
    )
    op.create_index(
        "ix_skill_timeseries_skill_window",
        "skill_timeseries",
        ["skill_name", "window_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_skill_timeseries_skill_window", table_name="skill_timeseries")
    op.drop_index("ix_learning_progress_plan_skill", table_name="learning_progress")
