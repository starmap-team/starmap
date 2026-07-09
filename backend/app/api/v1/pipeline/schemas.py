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
    duration_ms: int = Field(0, ge=0)
    records_processed: int = Field(0, ge=0)
    errors: list[str] = Field(default_factory=list)
    errors_count: int = Field(0, ge=0, description="Count of errors (alias for len(errors))")
    retry_count: int = Field(0, ge=0)
    depends_on: list[str] = Field(default_factory=list)


class PipelineRunResponse(BaseModel):
    """Pipeline run details."""
    id: str
    run_type: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    stages: list[StageInfo] = Field(default_factory=list)
    total_records: int = 0
    new_records: int = 0
    updated_records: int = 0
    quality_score: float = 0.0
    error_log: str | None = None
    selected_stages: list[str] | None = None


class PipelineStatusResponse(BaseModel):
    """Global pipeline status overview."""
    is_running: bool = False
    current_run: PipelineRunResponse | None = None
    last_run: PipelineRunResponse | None = None
    recent_failed_run: PipelineRunResponse | None = None
    run_counts: dict[str, int] = Field(default_factory=dict)
    active_data_sources: int = 0
    today_crawl_volume: int = Field(0, ge=0, description="JDs crawled since 00:00 today")
    success_rate: float = Field(0.0, ge=0.0, le=1.0, description="7-day completed/(completed+failed)")
    avg_quality_score: float = Field(0.0, ge=0.0, le=1.0, description="7-day avg quality_score")
    quality_alerts: list[QualityAlertItem] = Field(default_factory=list)


class TriggerRequest(BaseModel):
    """Request body for manually triggering a pipeline run."""
    run_type: str = Field(default="full", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(
        None, description="Stages to execute; null = all stages",
        examples=[["crawl", "dedup", "import"]],
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
    metrics: DataQualityMetrics = Field(default_factory=DataQualityMetrics)
    source_scores: dict[str, float] = Field(default_factory=dict)
    alerts: list[QualityAlertItem] = Field(default_factory=list)
    alert_count: int = 0


class ScheduleCreateRequest(BaseModel):
    """Create a new pipeline schedule."""
    name: str = Field(..., description="Schedule name")
    cron_expression: str = Field(..., description="cron expression, e.g. '0 2 * * *'")
    run_type: str = Field(default="incremental", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(None)
    enabled: bool = Field(default=True)


class ScheduleResponse(BaseModel):
    """Pipeline schedule details."""
    id: str
    name: str
    cron_expression: str
    run_type: str
    selected_stages: list[str] | None = None
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
    """Update pipeline configuration."""
    stage_timeout: int | None = None
    worker_concurrency: int | None = None
    crawl_concurrency: int | None = None
    retry_max: int | None = None
    retry_backoff: int | None = None


class CancelResponse(BaseModel):
    """Response after cancelling a pipeline run."""
    run_id: str
    status: str
    cancelled_at: str
    stopped_stage_names: list[str] = Field(default_factory=list)
