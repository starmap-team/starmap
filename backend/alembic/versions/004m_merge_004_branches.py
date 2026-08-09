"""Merge 004a/004b branches (2026-08-07).

历史: 004a 与 004b 均定义 revision="004" (003 分支点, 重复 id),
005 的 down_revision="004" 悬空 → 新环境 alembic upgrade head 失败。
修复: 004a/004b 唯一化 + 本 merge 收拢分支 + 005 down 指向本迁移。
"""
from __future__ import annotations

revision: str = "004m"
down_revision: tuple[str, str] = ("004a", "004b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op merge (两个分支的表已在各自迁移中创建)。"""
    pass


def downgrade() -> None:
    pass
