"""数据源域 Schema：数据源详情/统计/健康/同步响应 (PLAN-014 批次8 迁入集中管理)。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DataSourceResponse(BaseModel):
    """数据源详情响应。"""

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


class DataSourceUpdateRequest(BaseModel):
    """数据源更新请求。"""

    authority_score: float | None = Field(None, ge=0, le=1)
    status: Literal["active", "paused", "error"] | None = Field(None, description="数据源状态")
    config: dict[str, Any] | None = None


class CrawlVolumeEntry(BaseModel):
    """单日采集量记录。"""

    date: str
    count: int = 0


class QualityTrendEntry(BaseModel):
    """单日质量趋势记录。"""

    date: str
    score: float = 0.0


class DataSourceStatsResponse(BaseModel):
    """数据源统计响应。"""

    source_id: str
    source_name: str
    crawl_volume: list[CrawlVolumeEntry] = Field(default_factory=list)
    quality_trend: list[QualityTrendEntry] = Field(default_factory=list)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_records_per_run: float = 0.0


class SourceHealthEntry(BaseModel):
    """单个数据源健康状态。"""

    id: str
    name: str
    status: str
    last_crawl_at: str | None = None
    total_records: int = 0
    recent_run_status: str | None = None


class DatasourcesHealthResponse(BaseModel):
    """数据源健康检查汇总。"""

    sources: list[SourceHealthEntry] = Field(default_factory=list)
    total_sources: int = 0
    active_sources: int = 0
    error_sources: int = 0


class SyncTriggerResponse(BaseModel):
    """触发同步响应。"""

    run_id: str
    source_name: str
    status: str
    message: str

class DataSourceCreateRequest(BaseModel):
    """管理员：注册一个新数据源。"""

    name: str = Field(..., min_length=1, max_length=120)
    source_type: Literal["job_board", "blog", "esco", "manual", "rss", "api"] = "job_board"
    authority_score: float = Field(default=0.5, ge=0, le=1)
    status: Literal["active", "paused", "error"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)
