"""StarMap 数据模型 —— 与 openapi.yaml 契约保持同步。

所有模型继承 pydantic.BaseModel 使用 v2 校验。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SkillCategory(str, Enum):
    hard_skill = "hard_skill"
    soft_skill = "soft_skill"
    tool = "tool"
    certificate = "certificate"


class Proficiency(str, Enum):
    level_1 = "了解"
    level_2 = "熟悉"
    level_3 = "精通"


class TrendDirection(str, Enum):
    rising = "rising"
    stable = "stable"
    declining = "declining"


class WarningLevel(str, Enum):
    green = "green"
    yellow = "yellow"
    orange = "orange"
    red = "red"


class StatusLevel(str, Enum):
    pass_ = "pass"
    warn = "warn"
    fail = "fail"


class ExtractionRequest(BaseModel):
    jd_content: str = Field(
        min_length=1,
        description="职位描述文本",
    )
    options: Optional[dict[str, Any]] = Field(
        default=None,
        description="抽取选项（model, temperature 等）",
    )


class SkillItem(BaseModel):
    skill: str = Field(description="技能名称")
    category: str = Field(description="技能分类")
    proficiency: str = Field(description="熟练度")


class NormalizedSkill(BaseModel):
    original: str = Field(description="原始技能名称")
    normalized: str = Field(description="归一化后的技能名称")
    method: str = Field(description="归一化方法")
    confidence: float = Field(description="归一化置信度")


class ExtractionResult(BaseModel):
    position_name: str = Field(default="", description="抽取的岗位名称")
    required_skills: list[SkillItem] = Field(default_factory=list, description="必需技能列表")
    preferred_skills: list[SkillItem] = Field(default_factory=list, description="加分技能列表")
    experience_required: Optional[int] = Field(default=None, description="要求经验年数")
    education_required: Optional[str] = Field(default=None, description="学历要求")
    responsibilities: list[str] = Field(default_factory=list, description="岗位职责描述")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度")
    hallucination_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="幻觉风险评分")
    normalized_skills: list[NormalizedSkill] = Field(default_factory=list, description="归一化后的技能列表")


class SkillNode(BaseModel):
    skill_id: str = Field(description="技能唯一标识（归一化后的 ID）")
    name: str = Field(description="技能展示名称")
    category: SkillCategory = Field(description="技能分类")
    proficiency: Proficiency = Field(description="熟练度等级")
    confidence: float = Field(ge=0.0, le=1.0, description="该技能节点置信度")
    source_count: int = Field(ge=0, description="来源文档计数")


class PositionNode(BaseModel):
    position_id: str = Field(description="岗位唯一标识")
    name: str = Field(description="岗位名称")
    industry: str = Field(description="所属行业")
    description: str = Field(description="岗位描述")
    skills_required: list[SkillNode] = Field(description="技能要求列表")
    discovered_at: Optional[datetime] = Field(
        default=None, description="发现时间",
    )


class GraphNode(BaseModel):
    id: str = Field(description="节点 ID")
    labels: list[str] = Field(description="节点标签列表")
    properties: dict[str, Any] = Field(
        description="节点属性键值对",
    )


class GraphEdge(BaseModel):
    source_id: str = Field(description="源节点 ID")
    target_id: str = Field(description="目标节点 ID")
    type: str = Field(description="边类型")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="边属性",
    )


class MatchOptions(BaseModel):
    threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="匹配阈值",
    )


class MatchRequest(BaseModel):
    person_skills: list[SkillNode] = Field(description="个人技能列表")
    target_position: str = Field(description="目标岗位 ID 或名称")
    options: MatchOptions = Field(
        default_factory=MatchOptions,
        description="匹配选项",
    )


class MatchResult(BaseModel):
    match_id: str = Field(description="匹配结果 ID")
    target_position: str = Field(description="目标岗位")
    match_score: float = Field(
        ge=0.0, le=1.0, description="总体匹配度",
    )
    matched_skills: list[str] = Field(description="已匹配技能")
    gap_skills: list[str] = Field(description="差距技能")
    recommendations: list[str] = Field(description="学习路径建议")
    missing_required: list[str] = Field(default_factory=list, description="缺失的必备技能")
    missing_bonus: list[str] = Field(default_factory=list, description="缺失的加分技能")
    skill_gap_detail: list["SkillGapDetail"] = Field(default_factory=list, description="技能差距明细")
    overall_assessment: str = Field(default="", description="总体评估")
    estimated_learning_time: str = Field(default="", description="预计学习时长")


class SkillGapDetail(BaseModel):
    skill: str = Field(description="技能名称")
    importance: str = Field(description="required 或 bonus")
    gap_level: str = Field(description="完全缺失、部分掌握或已掌握")
    learning_path: list[str] = Field(description="学习路径")


class QualityDetail(BaseModel):
    dimension: str = Field(description="评估维度")
    value: float = Field(description="当前值")
    threshold: float = Field(description="阈值")
    status: StatusLevel = Field(description="状态")


class QualityReport(BaseModel):
    precision: float = Field(ge=0.0, le=1.0, description="精度")
    recall: float = Field(ge=0.0, le=1.0, description="召回率")
    f1: float = Field(ge=0.0, le=1.0, description="F1 值")
    warning_level: WarningLevel = Field(description="警戒等级")
    details: list[QualityDetail] = Field(description="详细评估条目")


class EvolutionTrend(BaseModel):
    skill_name: str = Field(description="技能名称")
    trend: TrendDirection = Field(description="趋势方向")
    confidence: float = Field(
        ge=0.0, le=1.0, description="趋势置信度",
    )
    related_positions: list[str] = Field(description="关联岗位")


class Error(BaseModel):
    detail: str = Field(description="错误描述")
    code: str = Field(description="错误码")
    timestamp: Optional[datetime] = Field(
        default=None, description="错误发生时间",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def set_timestamp(cls, v: Any) -> datetime:
        return v or datetime.utcnow()


class AdminStats(BaseModel):
    total_nodes: int = Field(description="总节点数")
    total_edges: int = Field(description="总边数")
    total_positions: int = Field(description="岗位总数")
    total_skills: int = Field(description="技能总数")
    avg_confidence: float = Field(
        ge=0.0, le=1.0, description="平均置信度",
    )
    hallucination_rate: float = Field(
        ge=0.0, le=1.0, description="幻觉率",
    )
    pending_review: int = Field(description="待审核数")


class SourceConfig(BaseModel):
    id: int = Field(description="数据源 ID")
    name: str = Field(description="数据源名称")
    authority_score: float = Field(ge=0.0, le=1.0, description="权威性分数")
    source_type: str = Field(description="数据源类型")


class SourceList(BaseModel):
    items: list[SourceConfig] = Field(description="数据源列表")


class AuditItem(BaseModel):
    id: int = Field(description="审核项 ID")
    type: str = Field(description="position 或 skill")
    name: str = Field(description="审核对象名称")
    trust: int = Field(ge=0, le=100, description="信任度百分比")
    status: str = Field(description="pending、approved 或 rejected")


class AuditQueue(BaseModel):
    items: list[AuditItem] = Field(description="审核队列")


class ResetDemoResult(BaseModel):
    ok: bool = Field(description="是否重置成功")
    review_items: int = Field(ge=0, description="重置后的审核项数量")


class PaginatedPositions(BaseModel):
    items: list[PositionNode] = Field(description="岗位列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class DiscoverRequest(BaseModel):
    source: Optional[str] = Field(
        default=None, description="数据源标识",
    )
    force: bool = Field(
        default=False, description="是否强制重新发现",
    )


class TaskResponse(BaseModel):
    message: str = Field(description="响应消息")
    task_id: UUID = Field(description="任务 ID")


class EvolutionAnalyzeRequest(BaseModel):
    mode: str = Field(
        default="incremental",
        description="分析模式",
    )
    category: Optional[str] = Field(
        default=None, description="限定分析领域",
    )


class EvaluateRequest(BaseModel):
    scope: str = Field(
        default="full",
        description="评估范围",
    )
    sample_ratio: float = Field(
        default=1.0, ge=0.01, le=1.0,
        description="采样比例",
    )
