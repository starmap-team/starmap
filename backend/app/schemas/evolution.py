"""演化域 Schema：职业路径/预警/行业报告/演化趋势 (PLAN-014 批次10-12 迁入集中管理)。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CareerPathNode(BaseModel):
    """A node in the career path graph."""

    position: str = Field(..., description="岗位名称")
    similarity: float = Field(default=0.0, ge=0, le=1, description="与起点岗位的相似度 0~1")
    skill_overlap: list[str] = Field(default_factory=list, description="技能重叠列表")
    key_gaps: list[str] = Field(default_factory=list, description="关键技能缺口")
    evidence_count: int = Field(default=0, ge=0, description="路径证据条数")
    direction: str = Field(default="forward", description="forward | lateral | up")


class CareerPathResponse(BaseModel):
    """Career path planning response."""

    origin: str
    nodes: list[CareerPathNode] = Field(default_factory=list)
    total_paths: int = 0


class EmergingAlert(BaseModel):
    """An emerging skill alert with full context."""

    skill_name: str = Field(..., description="技能名称")
    category: str = Field(default="", description="分类")
    level: str = Field(..., description="分类: emerging/rising/declining/stable")
    z_score: float = Field(default=0.0, description="Z-score 值")
    current_frequency: int = Field(default=0, description="当前频次")
    mean_frequency: float = Field(default=0.0, description="历史均值频次")
    source_count: int = Field(default=0, description="来源数")
    domains: list[str] = Field(default_factory=list, description="所属领域")
    positions: list[str] = Field(default_factory=list, description="关联岗位")
    trend: str = Field(default="stable", description="趋势方向")
    portability_score: float = Field(default=0.0, ge=0, le=1, description="可迁移性得分")
    alert_message: str = Field(default="", description="预警描述")


class EmergingAlertsResponse(BaseModel):
    """Emerging skill alerts response."""

    alerts: list[EmergingAlert] = Field(default_factory=list, description="预警列表")
    total: int = 0
    summary: str = ""


class SkillTrendItem(BaseModel):
    """Skill trend in industry report."""

    skill_name: str = Field(..., description="技能名称")
    trend: str = Field(..., description="rising | stable | declining")
    frequency: int = Field(default=0, ge=0, description="出现频次")
    source_count: int = Field(default=0, ge=0, description="数据源数")
    related_positions: list[str] = Field(default_factory=list, description="相关岗位")


class IndustryReportResponse(BaseModel):
    """Industry trend report response."""

    total_skills: int = Field(default=0, ge=0, description="技能总数")
    rising_skills: list[SkillTrendItem] = Field(default_factory=list, description="上升技能")
    declining_skills: list[SkillTrendItem] = Field(default_factory=list, description="下降技能")
    stable_skills: list[SkillTrendItem] = Field(default_factory=list, description="平稳技能")
    top_positions: list[dict] = Field(default_factory=list, description="热门岗位 TOP")
    summary: str = Field(default="", description="报告摘要")


class EvolutionTrend(BaseModel):
    """技能趋势条目。"""

    skill_name: str = Field(..., description="技能名称")
    trend: str = Field(..., description="趋势方向：rising/stable/declining")
    confidence: float = Field(..., ge=0, le=1, description="趋势置信度")
    points: list[float] = Field(default_factory=list, description="CII 时序数据点")
    related_positions: list[str] = Field(default_factory=list, description="相关岗位")


class EvolutionTrendsResponse(BaseModel):
    """演化趋势响应。"""

    items: list[EvolutionTrend] = Field(default_factory=list, description="趋势列表")


class ChangelogEntry(BaseModel):
    """变更日志条目。"""

    id: str
    skill_name: str
    change_type: str
    old_proficiency: str | None = None
    new_proficiency: str | None = None
    old_requirement: str | None = None
    new_requirement: str | None = None
    trust_score: float
    confidence: float
    created_at: datetime
    position_name: str = Field(default="", description="发生技能变更的职位名称")
    status: str = Field(default="pending", description="审核状态：pending/approved/rejected")
    written_back: bool = Field(default=False, description="该变更是否已回写 position_skill_relations")
    evidence_json: dict[str, Any] = Field(
        default_factory=dict,
        description="证据链：mention_count_old/new、source_count、factors（源计数/提及新旧/变更类型/稳定性因子）",
    )


class EvolutionKpiResponse(BaseModel):
    """演化看板 KPI 行响应。"""

    emerging_count: int = Field(..., ge=0, description="涌现技能数（emerging + rising）")
    # 2026-08-21 (debug 修复): Optional —— changelog 空表时返回 None（前端显示"—"），
    # 而非 0.0（用户误读为"信任度全 0"）
    trust_mean: float | None = Field(default=None, ge=0, le=1, description="变更日志信任度均值（0-1，真实聚合；空表为 None）")
    trust_mean_neo4j_skill: float = Field(
        default=0.0, ge=0, le=1, description="Neo4j Skill.trust_score 实时均值（与 /quality 共享 avg_skill_trust 指标）"
    )
    cii_mean: float = Field(..., ge=0, description="技能 CII 均值（基准 100，A4 基线口径）")
    alert_count: int = Field(..., ge=0, description="预警数（emerging/rising/declining 非平稳信号）")
    days: int = Field(..., ge=7, le=730, description="分析时间窗口（天）")


class EvolutionPathEntry(BaseModel):
    """演化路径条目。"""

    id: str
    source_position: str
    target_position: str
    similarity: float
    evidence_count: int
    skill_overlap: list[str]
    key_gaps: list[str]
    trust_score: float
    trend: str = "stable"


class EmergingSkill(BaseModel):
    """涌现技能条目。"""

    skill_name: str
    level: str  # emerging/rising/stable/declining
    z_score: float
    current_frequency: int
    mean_frequency: float
    source_count: int
    positions: list[str]


class SnapshotEntry(BaseModel):
    """快照条目。"""

    id: str
    position_name: str
    snapshot_date: datetime
    required_skills: list[dict[str, Any]]
    preferred_skills: list[dict[str, Any]]
    source_count: int


class ReviewQueueItem(BaseModel):
    """审核队列条目。"""

 # E22 fix: include id so the frontend can dispatch per-row approve/reject
 # via /evolution/review-queue/{id}/action.
    id: str = Field(..., description="EvolutionChangelog id (UUID)")
    skill_name: str
    position_name: str
    change_type: str
    trust_score: float
    status: str  # pending/approved/rejected
    created_at: datetime


# ─── Endpoints ───


class PortabilityDetail(BaseModel):
    """Skill portability analysis response."""

    skill_name: str = Field(..., description="技能名称")
    portability_score: float = Field(default=0.0, ge=0, le=1, description="可迁移性得分")
    domains: list[str] = Field(default_factory=list, description="所属领域")
    domain_count: int = 0
    positions_by_domain: dict[str, list[str]] = Field(
        default_factory=dict,
        description="各领域关联岗位",
    )
    total_positions: int = 0
    transferability_tier: str = Field(default="low", description="可迁移性等级")
    related_skills: list[str] = Field(default_factory=list, description="相关跨领域技能")
    recommendation: str = Field(default="", description="建议")

class CausalAssociation(BaseModel):
    """技能-岗位关联显著性 (§7.6 因果推理轻量版)。"""

    position: str = Field(..., min_length=1, max_length=200, description="岗位名称")
    a: int = Field(..., ge=0, description="技能记录中含该岗位的记录数")
    b: int = Field(..., ge=0, description="技能记录中不含该岗位的记录数")
    c: int = Field(..., ge=0, description="对照记录中含该岗位的记录数")
    d: int = Field(..., ge=0, description="对照记录中不含该岗位的记录数")
    p_value: float = Field(..., ge=0, le=1, description="Fisher 精确检验 p 值")
    significant: bool = Field(..., description="p < 0.05 且 |phi| >= 0.1")
    phi: float = Field(..., ge=-1, le=1, description="phi 系数 (效应量)")
    method: str = Field(default="fisher_exact", description="检验方法")


class CausalAnalysisResponse(BaseModel):
    """技能因果关联分析响应 (§7.6)。"""

    skill: str = Field(..., min_length=1, description="被分析技能")
    associations: list[CausalAssociation] = Field(default_factory=list, description="显著关联岗位列表")
    total_records: int = Field(0, ge=0, description="技能记录数")
    control_records: int = Field(0, ge=0, description="对照记录数")
    alpha: float = Field(0.05, ge=0, le=1, description="显著性水平")
