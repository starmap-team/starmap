"""Add orphan_cleanup_queue (P2 数据统一方案, 2026-08-13).

Neo4j 孤儿节点审批清理队列：RepairEngine 检测到的孤儿（canonical_id 缺失或
指向不存在的 PG 行）写入本表，管理员审批后 DETACH DELETE + audit_events 审计。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "037"
down_revision: tuple[str, ...] = ("036",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orphan_cleanup_queue",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("node_type", sa.String(20), nullable=False,
                  comment="'position' | 'skill'"),
        sa.Column("name", sa.String(255), nullable=False,
                  comment="Neo4j 节点显示名"),
        sa.Column("canonical_id", sa.String(64), nullable=True,
                  comment="Neo4j 节点 canonical_id（无则为 NULL）"),
        sa.Column("reason", sa.String(32), nullable=False,
                  comment="'no_canonical_id' | 'orphan_canonical_id'"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                  comment="'pending' | 'approved' | 'rejected' | 'cleaned'"),
        sa.Column("detail", sa.JSON(), nullable=True,
                  comment="引用检查结果等附加信息"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
    )
    # 审批队列按状态查询；node_type 区分岗位/技能孤儿
    op.create_index("ix_orphan_cleanup_status", "orphan_cleanup_queue", ["status"])
    op.create_index("ix_orphan_cleanup_node_type", "orphan_cleanup_queue", ["node_type"])


def downgrade() -> None:
    op.drop_index("ix_orphan_cleanup_node_type", table_name="orphan_cleanup_queue")
    op.drop_index("ix_orphan_cleanup_status", table_name="orphan_cleanup_queue")
    op.drop_table("orphan_cleanup_queue")
