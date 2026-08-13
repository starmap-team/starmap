"""Extend review_audit_log.action CHECK to allow update_name_cn (2026-08-13).

内容审核 tab 新增「改中文名」：管理员在审核队列中直接修正岗位/技能 name_cn
（D8i/D8j 中文化手工校准），审计动作 update_name_cn 需加入 CHECK 白名单。
"""
from __future__ import annotations

from alembic import op

revision: str = "038"
down_revision: tuple[str, ...] = ("037",)
branch_labels = None
depends_on = None

_NEW_ACTIONS = "('submit', 'approve', 'reject', 'unpublish', 'grandfather', 'update_name_cn')"


def upgrade() -> None:
    op.drop_constraint("ck_review_audit_log_action", "review_audit_log", type_="check")
    op.create_check_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        f"action IN {_NEW_ACTIONS}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_review_audit_log_action", "review_audit_log", type_="check")
    op.create_check_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        "action IN ('submit', 'approve', 'reject', 'unpublish', 'grandfather')",
    )
