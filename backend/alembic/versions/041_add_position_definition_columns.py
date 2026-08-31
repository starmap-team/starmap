"""Add A3 five-element definition columns to position_records (Phase 38, 2026-08-31).

全岗位五要素闭环：将 A3 生成器产出的岗位定义五要素（行业场景/核心职责/
加分技能/简述）持久化到 position_records，供岗位详情/匹配/学习复用。
- industry_scenario: 典型行业应用场景（Text）
- core_responsibilities: 核心职责列表（JSONB）
- bonus_skills: 加分技能列表（JSONB）
- summary: 岗位简述（Text）

四列均可空，纯增量，不破坏现有数据。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "041"
down_revision: tuple[str, ...] = ("040",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_records",
        sa.Column("industry_scenario", sa.Text(), nullable=True, comment="典型行业应用场景（A3 五要素）"),
    )
    op.add_column(
        "position_records",
        sa.Column("core_responsibilities", JSONB(), nullable=True, comment="核心职责列表（A3 五要素）"),
    )
    op.add_column(
        "position_records",
        sa.Column("bonus_skills", JSONB(), nullable=True, comment="加分技能列表（A3 五要素）"),
    )
    op.add_column(
        "position_records",
        sa.Column("summary", sa.Text(), nullable=True, comment="岗位简述（A3 五要素）"),
    )


def downgrade() -> None:
    op.drop_column("position_records", "summary")
    op.drop_column("position_records", "bonus_skills")
    op.drop_column("position_records", "core_responsibilities")
    op.drop_column("position_records", "industry_scenario")
