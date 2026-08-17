"""Extend review_audit_log action CHECK constraint to include re_extract_skills (2026-08-17 Phase 4).

Phase 4 (2026-08-17) 多模块联动：Admin 触发低数据岗位技能重新抽取端点
（POST /api/v1/admin/positions/{id}/re-extract-skills）写入
ReviewAuditLog 时使用 action='re_extract_skills'。沿用 041 同样的
模式扩展 CHECK 约束。
"""
from __future__ import annotations

from alembic import op

revision: str = "042"
down_revision: tuple[str, ...] = ("041",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        type_="check",
    )
    op.create_check_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        "action IN ('submit', 'approve', 'reject', 'unpublish', "
        "'grandfather', 'update_name_cn', 'reclassify_industry', 're_extract_skills')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        type_="check",
    )
    op.create_check_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        "action IN ('submit', 'approve', 'reject', 'unpublish', "
        "'grandfather', 'update_name_cn', 'reclassify_industry')",
    )