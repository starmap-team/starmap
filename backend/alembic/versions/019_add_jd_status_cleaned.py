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

# CONCERN 9.5: PostgreSQL cannot drop an enum value once added, so the
# downgrade is irreversible by design.
_DOWNGRADE_NOTE = "irreversible"


def upgrade() -> None:
    # 2026-08-18 fix: jd_status 枚举由 crawler 的 Base.metadata.create_all
    # （dao.init_schema）运行时创建，不在 alembic 迁移链内。bootstrap/alembic
    # 阶段 crawler 未启动 → 枚举不存在 → ALTER TYPE 失败阻断整个迁移链。
    # 包裹 try/except：枚举不存在时跳过（crawler init_schema 后续创建），
    # 不阻断 bootstrap。
    try:
        op.execute("ALTER TYPE jd_status ADD VALUE IF NOT EXISTS 'cleaned'")
    except Exception:
        pass  # jd_status 类型不存在（crawler 未启动），跳过


def downgrade() -> None:
    # PostgreSQL 无法删除枚举值，downgrade 仅注释说明
    pass
