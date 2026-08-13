"""孤儿节点清理队列 (P2 数据统一方案).

当 Neo4j 节点在 PostgreSQL 中找不到对应记录时（canonical_id 缺失或指向
不存在的 PG 行），RepairEngine 将其写入本队列，管理员审批后执行 DETACH DELETE。
删除是破坏性操作，必须经审批门控 + audit_events 审计（见
docs/design/多端数据统一与防漂移架构方案.md §3 目标架构）。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class OrphanCleanupQueue(Base):
    """一条待审批的 Neo4j 孤儿节点清理请求。"""

    __tablename__ = "orphan_cleanup_queue"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 节点类型: 'position' | 'skill'（与 GraphProjector.NODE_LABELS 对齐）
    node_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="'position' | 'skill'",
    )
    # 节点显示名（用于审批 UI 预览）
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Neo4j 节点显示名",
    )
    # 有 canonical_id 但指向不存在 PG 行的节点记录之；无 canonical_id 的为 NULL
    canonical_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="Neo4j 节点 canonical_id（无则为 NULL）",
    )
    # 孤儿判定原因
    reason: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="'no_canonical_id' | 'orphan_canonical_id'",
    )
    # 审批状态机: pending -> approved/rejected -> cleaned
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="'pending' | 'approved' | 'rejected' | 'cleaned'",
    )
    # 引用检查备注（被非孤儿节点引用时记录）
    detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="引用检查结果等附加信息",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
        comment="入队时间",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """供 API 序列化（与 admin 其他 to_dict 模式一致）。"""
        return {
            "id": str(self.id),
            "node_type": self.node_type,
            "name": self.name,
            "canonical_id": self.canonical_id,
            "reason": self.reason,
            "status": self.status,
            "detail": self.detail or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
        }


__all__ = ["OrphanCleanupQueue"]
