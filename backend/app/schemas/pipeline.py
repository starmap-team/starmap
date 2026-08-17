"""Pydantic schemas for the pipeline API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StageInfo(BaseModel):
    """Single pipeline stage details."""
    name: str = Field(..., description="Stage name")
    status: str = Field(..., description="pending/running/completed/failed/skipped/cancelled")
    started_at: str | None = Field(None, description="ISO timestamp")
    completed_at: str | None = Field(None, description="ISO timestamp")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Stage progress 0.0-1.0")
    duration_ms: int = Field(0, ge=0, description="阶段耗时（毫秒）")
    records_processed: int = Field(0, ge=0, description="已处理记录数")
    records_new: int | None = Field(None, ge=0, description="crawl 真正新增行数")
    records_duplicate: int | None = Field(None, ge=0, description="crawl 重复行数")
    errors: list[str] = Field(default_factory=list, description="阶段错误信息列表")
    errors_count: int = Field(0, ge=0, description="Count of errors (alias for len(errors))")
    warnings: list[str] = Field(default_factory=list, description="阶段非致命警告（如 crawl 0 条采集），不判 failed")
    retry_count: int = Field(0, ge=0, description="阶段重试次数")
    depends_on: list[str] = Field(default_factory=list, description="前置阶段名列表")
 # 实时活动上下文（来自 executor 的 _publish_stage_progress）
    current_activity: str = Field("", description="当前活动描述 (e.g. '正在爬取 BOSS直聘: ...')")
    recent_samples: list[dict] = Field(default_factory=list, description="最近处理的样本 (URL/技能/图节点)")
    sub_breakdown: dict[str, int] = Field(default_factory=dict, description="子项分解 (e.g. {'bosszhipin': 12, '51job': 5})")
    elapsed_ms: int = Field(0, ge=0, description="已运行毫秒数")


class PipelineRunResponse(BaseModel):
    """Pipeline run details."""
    id: str = Field(..., description="流水线运行 ID")
    run_type: str = Field(..., description="full | incremental")
    status: str = Field(..., description="running/completed/failed/cancelled")
    started_at: str | None = Field(default=None, description="ISO 时间戳")
    completed_at: str | None = Field(default=None, description="ISO 时间戳")
    stages: list[StageInfo] = Field(default_factory=list, description="阶段详情列表")
    total_records: int = Field(default=0, ge=0, description="总记录数")
    new_records: int = Field(default=0, ge=0, description="新增记录数")
    updated_records: int = Field(default=0, ge=0, description="更新记录数")
    quality_score: float = 0.0
    error_log: str | None = None
    selected_stages: list[str] | None = None
    selected_sources: list[str] | None = None


class PipelineStatusResponse(BaseModel):
    """Global pipeline status overview."""
    is_running: bool = False
    current_run: PipelineRunResponse | None = None
    last_run: PipelineRunResponse | None = None
    recent_failed_run: PipelineRunResponse | None = None
    run_counts: dict[str, int] = Field(default_factory=dict)
    active_data_sources: int = 0
    today_crawl_volume: int = Field(0, ge=0, description="今日爬虫处理量（各 run crawl 处理量之和，含重复）")
    today_crawl_new: int = Field(0, ge=0, description="今日 jd_raw 实际新增行数")
    total_jd_raw: int = Field(0, ge=0, description="jd_raw 全表行数（历史累计）")
    last_crawl_at: str | None = Field(None, description="ISO timestamp of most recent crawl")
    success_rate: float = Field(0.0, ge=0.0, le=1.0, description="7-day completed/(completed+failed)")
    avg_quality_score: float = Field(0.0, ge=0.0, le=1.0, description="7-day avg quality_score")
    quality_alerts: list[QualityAlertItem] = Field(default_factory=list)
 # 跨模块联动 (2026-08-14): 待审岗位/技能数（与 admin 内容审核同口径，数据产出后的去向指示）
    pending_review_positions: int = Field(0, ge=0, description="待审核岗位数（position_records.review_status=pending_review）")
    pending_review_skills: int = Field(0, ge=0, description="待审核技能数（skill_records.review_status=pending_review）")


class TriggerRequest(BaseModel):
    """Request body for manually triggering a pipeline run."""
    run_type: str = Field(default="full", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(
        None, description="Stages to execute; null = all stages",
        examples=[["crawl", "dedup", "import"]],
    )
    selected_sources: list[str] | None = Field(
        None, description="Source names to crawl; null/empty = all active sources",
        examples=[["V2EX 酷工作", "Remotive (远程)"]],
    )


class TriggerResponse(BaseModel):
    """Response after triggering a pipeline run."""
    run_id: str
    run_type: str
    status: str
    message: str


class RetryStageRequest(BaseModel):
    """Request body for retrying a failed stage."""
    stage_name: str = Field(..., description="Stage name to retry")


class DataSourceResponse(BaseModel):
    """Data source information."""
    id: str
    name: str
    source_type: str
    authority_score: float
    status: str
    last_crawl_at: str | None = None
    total_records: int = 0
    valid_records: int = 0
    duplicate_rate: float = 0.0
    avg_quality_score: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)
 # P0-3/D1 (2026-08-15): 与 schemas/datasource.DataSourceResponse 对齐 ——
 # 爬虫适配器能力由后端注册表判定，pipeline 页"可用源"依赖此字段。
    has_adapter: bool = False
    adapter_platform: str | None = None


class StageStatusResponse(BaseModel):
    """Real-time stage status across recent runs."""
    stages: list[dict[str, Any]] = Field(default_factory=list)


class TrendPoint(BaseModel):
    """A single point in the data-quality trend (date + score)."""
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    score: float = Field(..., ge=0.0, le=1.0)


class DataQualityMetrics(BaseModel):
    """Nested data quality metrics."""
    overall_score: float = 0.0
    completeness: float = 0.0
    accuracy: float = 0.0
    freshness_hours: float = 0.0
    duplicate_rate: float = 0.0
    total_records: int = 0
    valid_records: int = 0
    consistency: float = Field(0.0, ge=0.0, le=1.0, description="Inverse stddev of source_scores")
    timeliness: float = Field(0.0, ge=0.0, le=1.0, description="1 - min(freshness/48h, 1)")
    trend: list[TrendPoint] = Field(default_factory=list, description="14-day overall_score trend")
 # M5（Phase 13 强制规范）：无已质检数据时不得报"完美"，须显式标记不可信
    baseline_available: bool = Field(True, description="是否存在可评估的质检数据；False 时各分数不可信")
    quality_explanation: str = Field("", description="无基线/无数据时的口径说明")


class QualityAlertItem(BaseModel):
    """Single quality alert."""
    level: str
    dimension: str | None = None
    message: str
    source: str | None = None
    value: float | None = None
    threshold: float | None = None
    timestamp: str
    time: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.time and self.timestamp:
            object.__setattr__(self, "time", self.timestamp)


class DataQualityResponse(BaseModel):
    """Data quality metrics and alerts."""
    metrics: DataQualityMetrics = Field(default_factory=DataQualityMetrics.model_construct)
    source_scores: dict[str, float] = Field(default_factory=dict)
    alerts: list[QualityAlertItem] = Field(default_factory=list)
    alert_count: int = 0


class ScheduleCreateRequest(BaseModel):
    """Create a new pipeline schedule."""
    name: str = Field(..., description="Schedule name")
    cron_expression: str = Field(..., description="cron expression, e.g. '0 2 * * *'")
    run_type: str = Field(default="incremental", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(None)
    selected_sources: list[str] | None = Field(
        None, description="Source names to crawl; null/empty = all active sources",
    )
    enabled: bool = Field(default=True)


class ScheduleResponse(BaseModel):
    """Pipeline schedule details."""
    id: str
    name: str
    cron_expression: str
    run_type: str
    selected_stages: list[str] | None = None
    selected_sources: list[str] | None = None
    enabled: bool = True
    last_run_at: str | None = None
    next_run_at: str | None = None
    created_at: str | None = None


class PipelineConfigResponse(BaseModel):
    """Current pipeline configuration from SystemConfig / settings."""
    stage_timeout: int
    worker_concurrency: int
    crawl_concurrency: int
    retry_max: int
    retry_backoff: int


class PipelineConfigUpdateRequest(BaseModel):
    """Update pipeline configuration (SEC-06: all fields have range constraints)."""

    stage_timeout: int | None = Field(
        None,
        ge=60,
        le=7200,
        description="Stage timeout in seconds (60-7200)",
    )
    worker_concurrency: int | None = Field(
        None,
        ge=1,
        le=10,
        description="Worker concurrency (1-10)",
    )
    crawl_concurrency: int | None = Field(
        None,
        ge=1,
        le=20,
        description="Crawl concurrency (1-20)",
    )
    retry_max: int | None = Field(
        None,
        ge=0,
        le=10,
        description="Max retries (0-10)",
    )
    retry_backoff: int | None = Field(
        None,
        ge=1,
        le=300,
        description="Retry backoff base in seconds (1-300)",
    )


class CancelResponse(BaseModel):
    """Response after cancelling a pipeline run."""
    run_id: str
    status: str
    cancelled_at: str
    stopped_stage_names: list[str] = Field(default_factory=list)
