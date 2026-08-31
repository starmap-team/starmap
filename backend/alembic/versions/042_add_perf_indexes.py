"""Add performance indexes for COUNT/filter hot columns (PERF-04, 2026-08-29).

性能优化: quality.py / admin_data_truth.py 大量按 review_status / name_cn
过滤与 COUNT, 此前无索引 → 大表全表扫 (实测 quality 27 次串行查询慢)。
补 ix_position_review_status / ix_skill_review_status / ix_position_name_cn
/ ix_skill_name_cn。纯增量, 不破坏现有数据。
"""
from __future__ import annotations

from alembic import op

revision: str = "042"
down_revision: tuple[str, ...] = ("041",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # position_records.review_status — quality.py COUNT/FILTER 热列
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_position_review_status "
        "ON position_records (review_status)"
    )
    # skill_records.review_status — quality.py COUNT/FILTER 热列
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_skill_review_status "
        "ON skill_records (review_status)"
    )
    # position_records.name_cn — match_service / graph_service 按 name_cn 查
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_position_name_cn "
        "ON position_records (name_cn)"
    )
    # skill_records.name_cn — 同上
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_skill_name_cn "
        "ON skill_records (name_cn)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_position_review_status")
    op.execute("DROP INDEX IF EXISTS ix_skill_review_status")
    op.execute("DROP INDEX IF EXISTS ix_position_name_cn")
    op.execute("DROP INDEX IF EXISTS ix_skill_name_cn")
