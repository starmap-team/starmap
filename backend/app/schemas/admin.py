"""管理域 Schema：图谱节点管理/数据真相对账 (PLAN-014 批次13 迁入集中管理)。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.services import auth_service  # MIN_PASSWORD_LENGTH 常量


class GraphNodeItem(BaseModel):
    """图谱节点条目（图节点管理表单/列表）。"""

    id: str = Field(default="", description="图节点 ID（优先 canonical_id，缺省回退 elementId）")
    # P1-6 fix (functional-review 2026-08-13): 透传 Neo4j elementId。此前列表只回
    # canonical_id、写操作按 elementId 匹配 → 前端拿 canonical_id 调更新/删除/审核
    # 全部 404。前端可优先用 element_id 调写操作（服务端已改为双匹配，两者皆可）。
    element_id: str = Field(default="", description="Neo4j elementId（写操作首选标识）")
    type: Literal["Position", "Skill", "Tool", "KnowledgeArea", "Domain", "Industry", "Certificate", "LearningResource"] = Field(..., description="Neo4j 节点标签")
    name: str = Field(..., min_length=1, max_length=200, description="节点名称")
    properties: dict[str, Any] = Field(default_factory=dict, description="节点属性（category/proficiency/level 等）")
    status: str = Field(default="approved", pattern="^(approved|pending|rejected)$", description="审核状态")
    created_at: str | None = Field(default=None, description="创建时间（ISO 8601，可选）")


class GraphNodeListResponse(BaseModel):
    items: list[GraphNodeItem] = Field(default_factory=list, description="图节点列表")
    total: int = Field(default=0, ge=0, description="节点总数")


class SourceCount(BaseModel):
    """单数据源的某个指标。"""
    value: int
    source: str  # e.g., "api://graph/overview", "postgres://position_records", "neo4j://Position"


class TruthRow(BaseModel):
    """一个指标的三个数据源对比。"""
    metric: str                          # "岗位总数"
    description: str                     # "用户可见的岗位记录数"
    api_value: int                       # API endpoint 返回值
    postgres_value: int                  # PostgreSQL 直查
    neo4j_value: int                      # Neo4j 直查
    diff_pct: float                      # (max - min) / max * 100
    status: str                          # "ok" | "warn" | "critical"
    explanation: str                     # 给用户看的中文说明


class HealthMetrics(BaseModel):
    """Phase 5 Step 4: 同步健康度指标。"""
    orphan_positions: int = Field(0, description="Neo4j 中 PG 找不到的 Position 节点数")
    orphan_skills: int = Field(0, description="Neo4j 中 PG 找不到的 Skill 节点数")
    last_reconcile_at: str | None = Field(None, description="最近一次 reconcile 时间（ISO）")
    reconcile_status: str = Field("unknown", description="ok | warn | critical | unknown")
    sync_health: str = Field("ok", description="ok | warn | critical")


class TruthReport(BaseModel):
    """完整数据源真理报告。"""
    rows: list[TruthRow]
    health: HealthMetrics
    generated_at: str


class OrphanQueueItem(BaseModel):
    """孤儿节点审批队列条目（P2 数据统一方案）。"""

    id: str = Field(..., description="队列条目 UUID")
    node_type: Literal["position", "skill"] = Field(..., description="'position' | 'skill'")
    name: str = Field(..., min_length=1, max_length=255, description="Neo4j 节点显示名")
    canonical_id: str | None = Field(default=None, description="canonical_id（无则为 NULL）")
    reason: Literal["no_canonical_id", "orphan_canonical_id"] = Field(..., description="孤儿判定原因")
    status: str = Field(..., pattern="^(pending|approved|rejected|cleaned|linked)$", description="审批状态")
    detail: dict[str, Any] = Field(default_factory=dict, description="引用检查结果/链接建议等附加信息")
    created_at: str | None = Field(default=None, description="入队时间（ISO）")
    reviewed_at: str | None = Field(default=None, description="审批时间（ISO）")
    reviewed_by: str | None = Field(default=None, description="审批人")


class OrphanLinkRequest(BaseModel):
    """孤儿链接请求（P3a: SET canonical_id，非破坏、可逆）。"""

    canonical_id: str | None = Field(
        default=None, max_length=64,
        description="目标 PG canonical_id（缺省用检测建议值）",
    )
    actor: str | None = Field(default=None, max_length=64, description="操作人（可选）")


class OrphanBackfillResponse(BaseModel):
    """历史技能补录结果（P3b）。"""

    backfilled: int = Field(default=0, description="回填 skill_records 的技能数")
    linked: int = Field(default=0, description="链接 canonical_id 的技能数")
    errors: list[str] = Field(default_factory=list, description="失败明细（不阻断其余）")


class OrphanQueueResponse(BaseModel):
    """孤儿审批队列响应。"""

    items: list[OrphanQueueItem] = Field(default_factory=list, description="队列条目")
    total: int = Field(default=0, ge=0, description="条目总数")


class OrphanQueueActionRequest(BaseModel):
    """孤儿队列审批动作请求。"""

    action: Literal["approve", "reject"] = Field(..., description="'approve' 删除节点 / 'reject' 拒绝")
    actor: str | None = Field(default=None, max_length=64, description="审批人（可选，默认取当前用户）")


class OrphanBatchActionRequest(BaseModel):
    """孤儿队列批量审批请求。"""

    action: Literal["approve", "reject"] = Field(..., description="'approve' 删除节点 / 'reject' 拒绝")
    only_no_reference: bool = Field(
        default=True,
        description="仅处理无引用孤儿（referenced_by=0，删除安全）；False 处理全部 pending（危险）",
    )
    actor: str | None = Field(default=None, max_length=64, description="审批人（可选）")


class OrphanBatchActionResponse(BaseModel):
    """孤儿队列批量审批结果。"""

    processed: int = Field(default=0, description="处理的条目数")
    deleted: int = Field(default=0, description="实际删除的 Neo4j 节点数")
    errors: list[str] = Field(default_factory=list, description="失败明细（不阻断其余）")


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=auth_service.MIN_PASSWORD_LENGTH, max_length=128)
    role: str = Field(..., pattern="^(admin|user)$")
    email: EmailStr | None = None
    must_change_password: bool = True


class UpdateUserRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None
    must_change_password: bool | None = None
    email: EmailStr | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(
        ..., min_length=auth_service.MIN_PASSWORD_LENGTH, max_length=128
    )


class DeleteUserRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class AuditEventOut(BaseModel):
    id: str
    event: str
    actor: str
    action: str
    detail: str
    ip: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditUpdateRequest(BaseModel):
    """Partial update for a review-queue item."""

    name: str | None = Field(default=None, min_length=1)
    trust: int | None = Field(default=None, ge=0, le=100)


class BatchAuditRequest(BaseModel):
    """Batch approve or reject multiple review queue items."""

    item_ids: list[int] = Field(..., min_length=1, max_length=100)
    action: Literal["approve", "reject"]


class AuditQueueResponse(BaseModel):
    items: list[AuditItem] = Field(default_factory=list)


class ReconcileResult(BaseModel):
    """Reconcile 操作结果。"""
    positions_synced: int = Field(default=0, description="Position 节点同步数")
    skills_synced: int = Field(default=0, description="Skill 节点同步数")
    orphans_pruned: int = Field(default=0, description="孤儿节点剪枝数")
    positions_in_neo4j: int = Field(default=0, description="Neo4j 当前 Position 数")
    skills_in_neo4j: int = Field(default=0, description="Neo4j 当前 Skill 数")
    positions_in_pg: int = Field(default=0, description="PG 当前 Position 数")
    skills_in_pg: int = Field(default=0, description="PG 当前 Skill 数")
    # Phase 23 Task 3 (IC-05): REQUIRES 边对账字段
    requires_in_neo4j: int = Field(default=0, ge=0, description="Neo4j REQUIRES 边数")
    requires_in_pg: int = Field(default=0, ge=0, description="PG approved 岗位 PSR 边数")
    requires_diff: int = Field(default=0, ge=0, description="REQUIRES 边数差值（绝对值）")
    duration_ms: int = Field(default=0, description="执行耗时（毫秒）")
    health: str = Field(default="ok", description="健康度: ok/warn/critical")


class ReviewListResponse(BaseModel):
    """Unified review queue: position + skill entities, with status filter."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ReviewActionRequest(BaseModel):
    """Body for submit/approve/reject/unpublish actions."""

    reason: str | None = Field(default=None, max_length=2000)


class NameCnUpdateRequest(BaseModel):
    """调整岗位/技能中文名（name_cn）。"""

    name_cn: str = Field(..., min_length=1, max_length=255, description="中文显示名（非空）")


class PipelineStatusResponse(BaseModel):
    """Pipeline status + data health summary."""

    recent_runs: list[dict[str, Any]] = Field(default_factory=list)
    data_stats: dict[str, Any] = Field(default_factory=dict)


class PipelineTriggerResponse(BaseModel):
    """Full pipeline trigger response."""

    run_id: str
    status: str
    message: str


class SeedResetResponse(BaseModel):
    """演示数据重置（seed/reset）结果 —— 设计文档 §2.3.3.2 管理角色刚需。"""

    seeded: list[str] = Field(default_factory=list, description="成功执行的种子模块名列表")
    skipped: list[str] = Field(default_factory=list, description="跳过（幂等已存在/不可用）的模块名列表")
    refused: bool = Field(default=False, description="生产环境拒绝执行时为 True（APP_ENV=production）")
    message: str = Field(default="", min_length=0, max_length=500, description="人类可读结果摘要（含子进程输出摘录）")

class AuditItem(BaseModel):
    """审核队列条目 (原 admin_audit_service 定义, 迁入集中契约)。"""

    id: int
    type: str
    name: str
    trust: int = Field(ge=0, le=100)
    status: str
