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
    cii: Optional[float] = Field(default=None, description="CII 评分")


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
    points: list[float] = Field(default_factory=list, description="CII 时序数据点")


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
    record_count: int = Field(default=0, description="记录计数")


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


# ============================================================================
# Auto-generated models from openapi.yaml (71 schemas, batch-imported)
# Field names/types aligned with openapi.yaml definitions.
# ============================================================================

class AdminPipelineStatusResponse(BaseModel):
    recent_runs: list[dict[str, Any]] = Field(description="")
    data_stats: dict[str, Any] = Field(description="")

class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(description="")

class AuditEventListResponse(BaseModel):
    total: int = Field(description="")
    page: int = Field(description="")
    page_size: int = Field(description="")
    items: list[AuditEventOut] = Field(description="")

class AuditEventOut(BaseModel):
    id: str = Field(description="")
    event: str = Field(description="")
    actor: str = Field(description="")
    action: str = Field(description="")
    detail: str = Field(description="")
    ip: str = Field(description="")
    created_at: str = Field(description="")

class BatchAuditRequest(BaseModel):
    item_ids: list[int] = Field(description="")
    action: str = Field(description="")

class BatchJudgeRequest(BaseModel):
    golden_file: str = Field(description="")
    system_file: str = Field(description="")
    use_llm_judge: Optional[bool] = Field(default=None, description="")
    judge_prompt_version: Optional[str] = Field(default=None, description="")
    threshold: Optional[float] = Field(default=None, description="")

class BatchJudgeResponse(BaseModel):
    total_samples: Optional[int] = Field(default=None, description="")
    evaluated_samples: Optional[int] = Field(default=None, description="")
    avg_precision: Optional[float] = Field(default=None, description="")
    avg_recall: Optional[float] = Field(default=None, description="")
    avg_f1: Optional[float] = Field(default=None, description="")
    weighted_score: Optional[float] = Field(default=None, description="")
    f1_distribution: Optional[dict[str, Any]] = Field(default=None, description="")
    quality_gate: Optional[dict[str, Any]] = Field(default=None, description="")
    per_sample: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    judge_prompt_version: Optional[str] = Field(default=None, description="")

class BatchMatchRequest(BaseModel):
    items: list[dict[str, Any]] = Field(description="")

class CancelResponse(BaseModel):
    run_id: str = Field(description="")
    status: str = Field(description="")
    cancelled_at: str = Field(description="")
    stopped_stage_names: list[str] = Field(description="")

class CareerPathResponse(BaseModel):
    origin: str = Field(description="")
    nodes: list[dict[str, Any]] = Field(description="")
    total_paths: int = Field(description="")

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(description="")
    new_password: str = Field(description="")

class ChangelogEntry(BaseModel):
    id: str = Field(description="")
    skill_name: str = Field(description="")
    change_type: str = Field(description="")
    old_proficiency: Optional[str] = Field(default=None, description="")
    new_proficiency: Optional[str] = Field(default=None, description="")
    old_requirement: Optional[str] = Field(default=None, description="")
    new_requirement: Optional[str] = Field(default=None, description="")
    trust_score: float = Field(description="")
    confidence: float = Field(description="")
    status: Optional[str] = Field(default=None, description="审核状态: pending, approved, rejected")
    created_at: str = Field(description="")

class ComprehensiveReport(BaseModel):
    jd_report: Optional[QualityReport] = Field(default=None, description="")
    resume_eval: Optional[ResumeEvalResponse] = Field(default=None, description="")
    dashboard_summary: Optional[dict[str, Any]] = Field(default=None, description="")
    overall_score: Optional[float] = Field(default=None, description="")
    overall_status: Optional[str] = Field(default=None, description="")
    recommendations: Optional[list[str]] = Field(default=None, description="")

class CreatePlanRequest(BaseModel):
    position: str = Field(description="")
    match_score: Optional[float] = Field(default=None, description="")
    skills: list[dict[str, Any]] = Field(description="")
    available_hours_per_week: Optional[float] = Field(default=None, description="")

class CreateUserRequest(BaseModel):
    username: str = Field(description="")
    password: str = Field(description="")
    role: str = Field(description="")
    email: Optional[str] = Field(default=None, description="")
    must_change_password: Optional[bool] = Field(default=None, description="")

class DashboardDistributionResponse(BaseModel):
    source_distribution: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    domain_distribution: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    skill_category_distribution: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    timestamp: Optional[float] = Field(default=None, description="")

class DashboardOverview(BaseModel):
    total_nodes: int = Field(description="")
    total_edges: int = Field(description="")
    total_positions: int = Field(description="")
    total_skills: int = Field(description="")
    total_domains: int = Field(description="")
    trust_score: float = Field(description="")
    hallucination_rate: float = Field(description="")
    total_extractions: int = Field(description="")
    data_volume: int = Field(description="")
    today_extractions: int = Field(description="")
    pipeline_status: str = Field(description="")
    active_data_sources: int = Field(description="")
    weekly_new_nodes: int = Field(description="")
    stale: bool = Field(description="")
    stale_since: Optional[float] = Field(default=None, description="")
    timestamp: float = Field(description="")

class DashboardTrendsResponse(BaseModel):
    period: str = Field(description="")
    data_points: list[dict[str, Any]] = Field(description="")
    summary: dict[str, Any] = Field(description="")

class DataQualityResponse(BaseModel):
    metrics: Optional[dict[str, Any]] = Field(default=None, description="")
    source_scores: Optional[dict[str, Any]] = Field(default=None, description="")
    alerts: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    alert_count: Optional[int] = Field(default=None, description="")

class DataSourceResponse(BaseModel):
    id: str = Field(description="")
    name: str = Field(description="")
    source_type: str = Field(description="")
    authority_score: float = Field(description="")
    status: str = Field(description="")
    last_crawl_at: Optional[str] = Field(default=None, description="")
    total_records: Optional[int] = Field(default=None, description="")
    valid_records: Optional[int] = Field(default=None, description="")
    duplicate_rate: Optional[float] = Field(default=None, description="")
    avg_quality_score: Optional[float] = Field(default=None, description="")
    config: Optional[dict[str, Any]] = Field(default=None, description="")

class DataSourceStatsResponse(BaseModel):
    source_id: str = Field(description="")
    source_name: str = Field(description="")
    crawl_volume: list[dict[str, Any]] = Field(description="")
    quality_trend: list[dict[str, Any]] = Field(description="")
    total_runs: int = Field(description="")
    successful_runs: int = Field(description="")
    failed_runs: int = Field(description="")
    avg_records_per_run: float = Field(description="")

class DataSourceUpdateRequest(BaseModel):
    authority_score: Optional[float] = Field(default=None, description="")
    status: Optional[str] = Field(default=None, description="")
    config: Optional[dict[str, Any]] = Field(default=None, description="")

class DatasourcesHealthResponse(BaseModel):
    sources: list[SourceHealthEntry] = Field(description="")
    total_sources: int = Field(description="")
    active_sources: int = Field(description="")
    error_sources: int = Field(description="")

class DeleteUserRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="")

class EmergingAlertsResponse(BaseModel):
    alerts: list[dict[str, Any]] = Field(description="")
    total: int = Field(description="")
    summary: str = Field(description="")

class EmergingSkill(BaseModel):
    skill_name: str = Field(description="")
    level: str = Field(description="")
    z_score: float = Field(description="")
    current_frequency: int = Field(description="")
    mean_frequency: float = Field(description="")
    source_count: int = Field(description="")
    positions: Optional[list[str]] = Field(default=None, description="")

class EvolutionPathEntry(BaseModel):
    id: str = Field(description="")
    source_position: str = Field(description="")
    target_position: str = Field(description="")
    similarity: float = Field(description="")
    evidence_count: int = Field(description="")
    skill_overlap: Optional[list[str]] = Field(default=None, description="")
    key_gaps: Optional[list[str]] = Field(default=None, description="")
    trust_score: float = Field(description="")
    trend: Optional[str] = Field(default=None, description="")

class EvolutionSnapshot(BaseModel):
    id: str = Field(description="")
    position_name: str = Field(description="")
    snapshot_date: str = Field(description="")
    required_skills: list[dict[str, Any]] = Field(description="")
    preferred_skills: list[dict[str, Any]] = Field(description="")
    source_count: int = Field(description="")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(description="")

class GraphNodeItem(BaseModel):
    id: Optional[str] = Field(default=None, description="")
    type: str = Field(description="Node label: Position, Skill, Tool, KnowledgeArea")
    name: str = Field(description="")
    properties: Optional[dict[str, Any]] = Field(default=None, description="")
    status: Optional[str] = Field(default=None, description="")
    created_at: Optional[str] = Field(default=None, description="")

class IndustryReportResponse(BaseModel):
    total_skills: Optional[int] = Field(default=None, description="")
    rising_skills: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    declining_skills: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    stable_skills: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    top_positions: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    summary: Optional[str] = Field(default=None, description="")

class JudgeRequest(BaseModel):
    golden: dict[str, Any] = Field(description="")
    system_output: dict[str, Any] = Field(description="")
    use_llm_judge: Optional[bool] = Field(default=None, description="")
    judge_prompt_version: Optional[str] = Field(default=None, description="")

class JudgeSampleResponse(BaseModel):
    sample_id: Optional[str] = Field(default=None, description="")
    precision: Optional[float] = Field(default=None, description="")
    recall: Optional[float] = Field(default=None, description="")
    f1: Optional[float] = Field(default=None, description="")
    llm_score: Optional[float] = Field(default=None, description="")
    llm_reasoning: Optional[str] = Field(default=None, description="")
    errors: Optional[list[str]] = Field(default=None, description="")
    evaluated_at: Optional[str] = Field(default=None, description="")

class LearningPlanResponse(BaseModel):
    plan_id: str = Field(description="")
    position: str = Field(description="")
    status: str = Field(description="")
    match_score_at_creation: Optional[float] = Field(default=None, description="")
    overall_pct: Optional[float] = Field(default=None, description="")
    total_hours: Optional[float] = Field(default=None, description="")
    total_weeks: Optional[float] = Field(default=None, description="")
    phase_count: Optional[int] = Field(default=None, description="")
    phases: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    skills: Optional[list[SkillProgressItem]] = Field(default=None, description="")
    stats: Optional[dict[str, Any]] = Field(default=None, description="")

class LoginRequest(BaseModel):
    username: str = Field(description="")
    password: str = Field(description="")

class LoginResponse(BaseModel):
    access_token: str = Field(description="")
    refresh_token: str = Field(description="")
    expires_in: int = Field(description="")
    user: dict[str, Any] = Field(description="")

class LogoutRequest(BaseModel):
    refresh_token: str = Field(description="")

class LoopRunRequest(BaseModel):
    jd_text: str = Field(description="")
    target_position: str = Field(description="")

class LoopRunResponse(BaseModel):
    run_id: str = Field(description="")
    jd_text: str = Field(description="")
    target_position: str = Field(description="")
    status: str = Field(description="")
    steps: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    extracted_skills: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    graph_update: Optional[dict[str, Any]] = Field(default=None, description="")
    match_result: Optional[dict[str, Any]] = Field(default=None, description="")
    learning_path: Optional[dict[str, Any]] = Field(default=None, description="")
    total_duration_seconds: Optional[float] = Field(default=None, description="")

class PairwiseRequest(BaseModel):
    output_a: dict[str, Any] = Field(description="")
    output_b: dict[str, Any] = Field(description="")

class PairwiseResponse(BaseModel):
    sample_id: Optional[str] = Field(default=None, description="")
    precision_b_vs_a: Optional[float] = Field(default=None, description="")
    recall_b_vs_a: Optional[float] = Field(default=None, description="")
    f1_b_vs_a: Optional[float] = Field(default=None, description="")
    errors: Optional[list[str]] = Field(default=None, description="")
    evaluated_at: Optional[str] = Field(default=None, description="")

class PipelineConfigResponse(BaseModel):
    stage_timeout: int = Field(description="")
    worker_concurrency: int = Field(description="")
    crawl_concurrency: int = Field(description="")
    retry_max: int = Field(description="")
    retry_backoff: int = Field(description="")

class PipelineConfigUpdateRequest(BaseModel):
    stage_timeout: Optional[int] = Field(default=None, description="")
    worker_concurrency: Optional[int] = Field(default=None, description="")
    crawl_concurrency: Optional[int] = Field(default=None, description="")
    retry_max: Optional[int] = Field(default=None, description="")
    retry_backoff: Optional[int] = Field(default=None, description="")

class PipelineRunResponse(BaseModel):
    id: str = Field(description="")
    run_type: str = Field(description="")
    status: str = Field(description="")
    started_at: Optional[str] = Field(default=None, description="")
    completed_at: Optional[str] = Field(default=None, description="")
    stages: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    total_records: Optional[int] = Field(default=None, description="")
    new_records: Optional[int] = Field(default=None, description="")
    updated_records: Optional[int] = Field(default=None, description="")
    quality_score: Optional[float] = Field(default=None, description="")
    error_log: Optional[str] = Field(default=None, description="")
    selected_stages: Optional[list[str]] = Field(default=None, description="")

class PipelineStatusResponse(BaseModel):
    is_running: bool = Field(description="")
    current_run: Optional[PipelineRunResponse] = Field(default=None, description="")
    last_run: Optional[PipelineRunResponse] = Field(default=None, description="")
    run_counts: dict[str, Any] = Field(description="")
    active_data_sources: int = Field(description="")
    today_crawl_volume: int = Field(description="")
    success_rate: float = Field(description="")
    avg_quality_score: float = Field(description="")
    quality_alerts: Optional[list[dict[str, Any]]] = Field(default=None, description="")

class PipelineTriggerResponse(BaseModel):
    run_id: str = Field(description="")
    status: str = Field(description="")
    message: str = Field(description="")

class PortabilityDetail(BaseModel):
    skill_name: str = Field(description="")
    portability_score: float = Field(description="")
    domains: list[str] = Field(description="")
    domain_count: int = Field(description="")
    positions_by_domain: Optional[dict[str, Any]] = Field(default=None, description="")
    total_positions: int = Field(description="")
    transferability_tier: str = Field(description="")
    related_skills: Optional[list[str]] = Field(default=None, description="")
    recommendation: Optional[str] = Field(default=None, description="")

class QualityAlertsResponse(BaseModel):
    total: int = Field(description="")
    critical: int = Field(description="")
    warning: int = Field(description="")
    info: int = Field(description="")
    alerts: list[dict[str, Any]] = Field(description="")

class QualityDashboard(BaseModel):
    report: QualityReport = Field(description="")
    total_extractions: int = Field(description="")
    pending_review: int = Field(description="")
    hallucination_rate: float = Field(description="")
    total_nodes: int = Field(description="")
    total_edges: int = Field(description="")
    total_positions: int = Field(description="")
    total_skills: int = Field(description="")
    avg_trust_score: float = Field(description="")
    high_trust_ratio: float = Field(description="")
    trust_distribution: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    hallucination_trend: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    source_distribution: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    weekly_new_nodes: Optional[int] = Field(default=None, description="")
    audit_pass_rate: Optional[float] = Field(default=None, description="")
    audit_queue: Optional[int] = Field(default=None, description="")

class QualityTrendsResponse(BaseModel):
    period: str = Field(description="")
    data_points: list[dict[str, Any]] = Field(description="")
    summary: dict[str, Any] = Field(description="")

class RecommendationItem(BaseModel):
    skill: str = Field(description="")
    importance: str = Field(description="")
    gap_level: str = Field(description="")
    estimated_hours: float = Field(description="")
    prerequisites: Optional[list[str]] = Field(default=None, description="")
    reason: str = Field(description="")

class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="")

class RefreshResponse(BaseModel):
    access_token: str = Field(description="")
    expires_in: int = Field(description="")

class ResetPasswordRequest(BaseModel):
    token: str = Field(description="")
    new_password: str = Field(description="")

class ResumeEvalResponse(BaseModel):
    success: Optional[bool] = Field(default=None, description="")
    total_samples: Optional[int] = Field(default=None, description="")
    precision: Optional[float] = Field(default=None, description="")
    recall: Optional[float] = Field(default=None, description="")
    f1: Optional[float] = Field(default=None, description="")
    macro_f1: Optional[float] = Field(default=None, description="")
    warning_level: Optional[str] = Field(default=None, description="")
    per_sample: Optional[list[dict[str, Any]]] = Field(default=None, description="")
    summary: Optional[dict[str, Any]] = Field(default=None, description="")
    error: Optional[str] = Field(default=None, description="")

class ReverseMatchRequest(BaseModel):
    person_skills: list[dict[str, Any]] = Field(description="")
    top_k: Optional[int] = Field(default=None, description="")
    min_score: Optional[float] = Field(default=None, description="")

class ReverseMatchResponse(BaseModel):
    recommendations: list[dict[str, Any]] = Field(description="")
    total_positions_scanned: int = Field(description="")
    skills_provided: int = Field(description="")

class ReviewActionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="")

class ReviewListResponse(BaseModel):
    items: list[dict[str, Any]] = Field(description="")
    total: int = Field(description="")

class ReviewQueueItem(BaseModel):
    id: Optional[str] = Field(default=None, description="变更项 ID")
    skill_name: str = Field(description="")
    position_name: str = Field(description="")
    change_type: str = Field(description="")
    trust_score: float = Field(description="")
    status: str = Field(description="")
    created_at: str = Field(description="")

class DomainKeywordEntry(BaseModel):
    name: str = Field(description="领域名称")
    keywords: list[str] = Field(description="领域关键词列表")

class ScheduleCreateRequest(BaseModel):
    name: str = Field(description="")
    cron_expression: str = Field(description="")
    run_type: Optional[str] = Field(default=None, description="")
    selected_stages: Optional[list[str]] = Field(default=None, description="")
    enabled: Optional[bool] = Field(default=None, description="")

class ScheduleResponse(BaseModel):
    id: str = Field(description="")
    name: str = Field(description="")
    cron_expression: str = Field(description="")
    run_type: str = Field(description="")
    selected_stages: Optional[list[str]] = Field(default=None, description="")
    enabled: Optional[bool] = Field(default=None, description="")
    last_run_at: Optional[str] = Field(default=None, description="")
    next_run_at: Optional[str] = Field(default=None, description="")
    created_at: Optional[str] = Field(default=None, description="")

class SkillProgressItem(BaseModel):
    skill_name: str = Field(description="")
    status: str = Field(description="")
    progress_pct: float = Field(description="")
    importance: Optional[str] = Field(default=None, description="")
    estimated_hours: Optional[float] = Field(default=None, description="")
    started_at: Optional[str] = Field(default=None, description="")
    completed_at: Optional[str] = Field(default=None, description="")
    notes: Optional[str] = Field(default=None, description="")

class SourceHealthEntry(BaseModel):
    id: str = Field(description="")
    name: str = Field(description="")
    status: str = Field(description="")
    last_crawl_at: Optional[str] = Field(default=None, description="")
    total_records: Optional[int] = Field(default=None, description="")
    recent_run_status: Optional[str] = Field(default=None, description="")

class SyncTriggerResponse(BaseModel):
    run_id: str = Field(description="")
    source_name: str = Field(description="")
    status: str = Field(description="")
    message: str = Field(description="")

class TriggerRequest(BaseModel):
    run_type: Optional[str] = Field(default=None, description="")
    selected_stages: Optional[list[str]] = Field(default=None, description="")

class TriggerResponse(BaseModel):
    run_id: str = Field(description="")
    run_type: str = Field(description="")
    status: str = Field(description="")
    message: str = Field(description="")

class UpdateProgressRequest(BaseModel):
    skill_name: str = Field(description="")
    status: Optional[str] = Field(default=None, description="")
    progress_pct: Optional[float] = Field(default=None, description="")
    notes: Optional[str] = Field(default=None, description="")

class UpdateUserRequest(BaseModel):
    role: Optional[str] = Field(default=None, description="")
    is_active: Optional[bool] = Field(default=None, description="")
    must_change_password: Optional[bool] = Field(default=None, description="")
    email: Optional[str] = Field(default=None, description="")

class UserInfo(BaseModel):
    id: Optional[str] = Field(default=None, description="")
    username: Optional[str] = Field(default=None, description="")
    role: Optional[str] = Field(default=None, description="")
    email: Optional[str] = Field(default=None, description="")
    is_active: Optional[bool] = Field(default=None, description="")
    must_change_password: Optional[bool] = Field(default=None, description="")
    failed_login_attempts: Optional[int] = Field(default=None, description="")
    locked_until: Optional[str] = Field(default=None, description="")
    created_at: Optional[str] = Field(default=None, description="")
    updated_at: Optional[str] = Field(default=None, description="")

class UserListResponse(BaseModel):
    total: int = Field(description="")
    page: int = Field(description="")
    page_size: int = Field(description="")
    items: list[UserInfo] = Field(description="")

