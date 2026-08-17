"""Extend review_audit_log action CHECK constraint to include reclassify_industry (2026-08-17 Phase 3).

背景：Phase 3 IndustryClassifier 第三层（Admin 重新分类 industry 端点）
写入 ReviewAuditLog 时使用 action='reclassify_industry'，但 DB 层
ck_review_audit_log_action CHECK 约束只接受 6 个固定值（submit / approve /
reject / unpublish / grandfather / update_name_cn），导致 IntegrityError。

约束扩展：新增 'reclassify_industry' 与值 — 业务语义 = admin 手动
覆盖岗位 industry 字段（属于 update 类别，但单独标记便于审计追溯）。

下游：管理后台「审计日志」Tab 可以按 action='reclassify_industry' 过滤，
看 admin 修正了哪些岗位的行业分类。
"""
from __future__ import annotations

from alembic import op

revision: str = "041"
down_revision: tuple[str, ...] = ("040",)
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
        "'grandfather', 'update_name_cn', 'reclassify_industry')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        type_="check",
    )
    # 不重建原约束（'reclassify_industry' 数据会阻塞 downgrade）
    # 留给运维决定是 truncate 还是手动迁移。
    op.create_check_constraint(
        "ck_review_audit_log_action",
        "review_audit_log",
        "action IN ('submit', 'approve', 'reject', 'unpublish', "
        "'grandfather', 'update_name_cn')",
    )
