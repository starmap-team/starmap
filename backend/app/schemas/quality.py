"""Quality 域 Schema (PLAN-014 批次11).

从 api/v1/quality.py 内联 5 个 BaseModel 迁入集中管理.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QualityDetail(BaseModel):
    """质量维度明细."""

    dimension: str = Field(..., min_length=1, description="质量维度")
    value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    status: str = Field(..., min_length=1, description="pass/warn/fail")


class QualityReport(BaseModel):
    """契约质量报告."""

    precision: float = Field(..., ge=0, le=1, description="精确率")
    recall: float = Field(..., ge=0, le=1, description="召回率")
    f1: float = Field(..., ge=0, le=1, description="F1 分")
    warning_level: str = Field(..., min_length=1, description="green/yellow/orange/red")
    details: list[QualityDetail] = Field(default_factory=list, description="维度明细")


class QualityDashboard(BaseModel):
    """前端质量仪表盘兼容响应."""

    report: QualityReport
    total_extractions: int = Field(default=0, ge=0, description="总抽取数")
    pending_review: int = Field(default=0, ge=0, description="待审核数")
    hallucination_rate: float = Field(default=0.0, ge=0, le=1, description="幻觉率")
 # : hallucination_rate 三段式契约（沿 KPI breakdown 口径）
    hallucination_numerator: int = Field(default=0, ge=0, description="幻觉数（分子）")
    hallucination_denominator: int = Field(default=0, ge=0, description="总抽取数（分母）")
    hallucination_window_days: int = Field(default=30, ge=1, description="统计窗口天数")
    total_nodes: int = Field(default=0, ge=0, description="总节点数")
    total_edges: int = Field(default=0, ge=0, description="总边数")
    total_positions: int = Field(default=0, ge=0, description="岗位节点数")
    total_skills: int = Field(default=0, ge=0, description="技能节点数")
    avg_trust_score: float = Field(default=0.0, ge=0, le=1, description="平均信任度")
    high_trust_ratio: float = Field(default=0.0, ge=0, le=1, description="高信任度占比")
    trust_distribution: list[dict] = Field(default_factory=list, description="信任度分布")
    hallucination_trend: list[dict] = Field(default_factory=list, description="幻觉趋势")
    source_distribution: list[dict] = Field(default_factory=list, description="源分布")
    weekly_new_nodes: int = Field(default=0, ge=0, description="本周新增节点数")
    audit_pass_rate: float = Field(default=0.0, ge=0, le=1, description="审核通过率")
    audit_queue: list[dict] = Field(default_factory=list, description="待审核队列")
 # 一致性审计: 区分"未评估"与"质量差", 避免 0/0/0 被误读为红色告警
    evaluation_count: int = Field(default=0, ge=0, description="已运行 golden-set 评估记录数")
    baseline_available: bool = Field(default=False, description="是否已有 golden-set 基线")
    evaluation_explanation: str = Field(default="", description="评估状态说明")


class ResumeEvalResponse(BaseModel):
    """简历抽取 F1 评估结果."""

    success: bool = Field(default=True, description="评估是否成功")
    total_samples: int = Field(default=0, ge=0, description="总样本数")
    precision: float = Field(default=0.0, ge=0, le=1, description="精确率")
    recall: float = Field(default=0.0, ge=0, le=1, description="召回率")
    f1: float = Field(default=0.0, ge=0, le=1, description="F1 分")
    macro_f1: float = Field(default=0.0, ge=0, le=1, description="宏 F1 分")
    warning_level: str = Field(default="gray", min_length=1, description="green/yellow/orange/red/gray")
    per_sample: list[dict[str, Any]] = Field(default_factory=list, description="逐样本结果")
    summary: dict[str, Any] = Field(default_factory=dict, description="汇总")
    error: str | None = Field(default=None, description="错误信息")


class ComprehensiveReport(BaseModel):
    """综合质量报告: JD + 简历评估 + 图谱统计."""

    jd_report: QualityReport
    resume_eval: ResumeEvalResponse
    dashboard_summary: dict[str, Any] = Field(default_factory=dict, description="仪表盘摘要")
    overall_score: float = Field(default=0.0, ge=0, le=1, description="综合得分")
    overall_status: str = Field(
        default="unknown", min_length=1, description="pass/warning/fail/unknown",
    )
    recommendations: list[str] = Field(default_factory=list, description="改进建议")


class TrendPoint(BaseModel):
    """单日质量趋势数据点。"""

    date: str
    overall_score: float = 0.0
    duplicate_rate: float = 0.0
    freshness_hours: float = 0.0
    total_records: int = 0
    new_records: int = 0
    quality_score: float = 0.0
    hallucination_rate: float = 0.0
    review_count: int = 0


class QualityTrendsResponse(BaseModel):
    """质量趋势时间线响应。"""

    period: str = Field(..., description="'7d' | '30d' | '90d'")
    data_points: list[TrendPoint] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AlertItem(BaseModel):
    """单条异常告警。"""

    id: str = Field(default="", description="告警唯一标识")
    type: str = Field(default="quality", description="告警类型")
    level: str = Field(..., description="'info' | 'warning' | 'critical'")
    dimension: str
    message: str
    source: str | None = None
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = ""
    status: str = Field(default="pending", description="'pending' | 'resolved' | 'ignored'")
    created_at: str = Field(default="", description="告警创建时间")
    handled: bool = False


class QualityAlertsResponse(BaseModel):
    """异常告警列表响应。"""

    total: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    alerts: list[AlertItem] = Field(default_factory=list)


class AlertHandleRequest(BaseModel):
    """告警处理请求：action = resolve | ignore。"""

    id: str = Field(..., description="告警稳定标识（dimension:source）")
    action: str = Field(..., description="'resolve' | 'ignore'")
