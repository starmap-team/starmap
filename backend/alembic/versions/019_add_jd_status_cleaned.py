"""add cleaned to jd_status enum

Phase 3 Plan 02: clean 阶段完成后标记 status=cleaned，
import 阶段改读 cleaned 而非 raw，实现阶段间数据流隔离。

Revision ID: 019
Revises: 018
"""
from __future__ import annotations

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: ADD VALUE 在事务内不可见（必须先 commit 才能用），
    # 所以数据迁移放在 020。019 仅做枚举扩展。
    op.execute("ALTER TYPE jd_status ADD VALUE IF NOT EXISTS 'cleaned'")


def downgrade() -> None:
    # PostgreSQL 无法删除枚举值，downgrade 仅注释说明
    pass