"""演化域 Schema：职业路径/预警/行业报告/演化趋势 (PLAN-014 批次10-12 迁入集中管理)。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CareerPathNode(BaseModel):
    """A node in the career path graph."""

    position: str
    similarity: float = 0.0
    skill_overlap: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    evidence_count: int = 0
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

    skill_name: str
    trend: str  # rising | stable | declining
    frequency: int = 0
    source_count: int = 0
    related_positions: list[str] = Field(default_factory=list)


class IndustryReportResponse(BaseModel):
    """Industry trend report response."""

    total_skills: int = 0
    rising_skills: list[SkillTrendItem] = Field(default_factory=list)
    declining_skills: list[SkillTrendItem] = Field(default_factory=list)


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
