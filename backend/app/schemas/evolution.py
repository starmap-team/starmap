"""演化域 Schema：职业路径规划 (PLAN-014 批次10 迁入集中管理)。"""

from __future__ import annotations

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
