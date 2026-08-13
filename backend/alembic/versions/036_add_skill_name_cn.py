"""Add skill_records.name_cn (D8i, 2026-08-12).

技能中文化: 752 个技能中 638 个为英文（Computer Vision、Written Communication
等），岗位已有 name_cn 字段但技能表没有。新增 name_cn 用于英文技能翻译后
展示（岗位详情/匹配诊断/图谱等多处）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "036"
down_revision: tuple[str, ...] = ("035",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_records",
        sa.Column("name_cn", sa.String(255), nullable=True,
                  comment="技能中文名（英文技能翻译后展示）"),
    )


def downgrade() -> None:
    op.drop_column("skill_records", "name_cn")
