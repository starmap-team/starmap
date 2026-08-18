"""Extend review_audit_log action CHECK constraint to include alert actions (2026-08-17 Phase 5).

Phase 5 多模块联动 — Celery 周期任务（daily_skill_backfill_task /
weekly_low_data_re_extract_task / daily_data_quality_check_task）写
ReviewAuditLog 时的特殊 action 值：
- industry_alert: 行业质量告警（unclassified_ratio 越界）
- low_data_support_alert: 数据支撑度告警（avg_score < 0.4）

沿用 041 / 042 模式扩展 CHECK 约束。
"""
from __future__ import annotations

from alembic import op

revision: str = "043"
down_revision: tuple[str, ...] = ("042",)
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
        "'grandfather', 'update_name_cn', 'reclassify_industry', 're_extract_skills', "
        "'industry_alert', 'low_data_support_alert')",
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
        "'grandfather', 'update_name_cn', 'reclassify_industry', 're_extract_skills')",
    )
