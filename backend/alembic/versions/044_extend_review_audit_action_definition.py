"""Extend review_audit_log.action CHECK to allow update_definition (A3 人工优化).

管理后台新增「编辑岗位五要素」（PATCH /admin/review/position/{id}/definition）：
审核员人工优化核心职责/加分技能/行业场景/简述，审计动作 update_definition
需加入 CHECK 白名单（沿 038 先例）。
"""
from __future__ import annotations

from alembic import op

revision: str = "044"
down_revision: tuple[str, ...] = ("043",)
branch_labels = None
depends_on = None

_NEW_ACTIONS = (
    "('submit', 'approve', 'reject', 'unpublish', 'grandfather', "
    "'update_name_cn', 'update_definition')"
)


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
        "action IN ('submit', 'approve', 'reject', 'unpublish', 'grandfather', 'update_name_cn')",
    )
