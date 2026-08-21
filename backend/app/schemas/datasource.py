"""数据源域 Schema：数据源详情/统计/健康/同步响应 (PLAN-014 批次8 迁入集中管理)。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.constants import DataSourceStatus


class DataSourceResponse(BaseModel):
    """数据源详情响应。"""

    id: str = Field(..., description="数据源 ID")
    name: str = Field(..., min_length=1, max_length=200, description="数据源名称")
    source_type: str = Field(..., description="数据源类型（api/rss/spider/manual 等）")
    authority_score: float = Field(default=0.6, ge=0, le=1, description="权威度评分 0~1")
    status: str = Field(default="active", description="数据源状态 active/paused/error")
    last_crawl_at: str | None = Field(default=None, description="最近一次采集时间（ISO）")
    total_records: int = Field(default=0, ge=0, description="记录总数")
    valid_records: int = Field(default=0, ge=0, description="有效记录数")
    duplicate_rate: float = Field(default=0.0, ge=0, le=1, description="重复率 0~1")
    avg_quality_score: float = Field(default=0.0, ge=0, le=1, description="平均质量分 0~1")
    config: dict[str, Any] = Field(default_factory=dict, description="数据源配置（spider 参数等）")
    has_adapter: bool = Field(default=False, description="是否有可用爬虫适配器（后端 spider 注册表判定，唯一事实源）")
    adapter_platform: str | None = Field(default=None, description="配置的爬虫平台名（无则 None，如 bosszhipin）")


class DataSourceUpdateRequest(BaseModel):
    """数据源更新请求。"""

    authority_score: float | None = Field(None, ge=0, le=1)
    status: DataSourceStatus | None = Field(
        None,
        description="数据源状态（active/paused/error/inactive）——inactive 支持 PATCH 恢复/停用语义",
    )
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
    recent_run_status: str | None = Field(
        default=None,
        description="最近一次 source_sync 运行状态。PipelineRun 无源归属，当前恒为 null；待 run↔source 关联迁移落地后按源计算",
    )


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
    # 新源不能直接建为停用：不含 'inactive'（停用只经 DELETE 软删除 / PATCH）。
    # 运行值全集见 app.core.constants.DataSourceStatus。
    status: Literal["active", "paused", "error"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)


class ManualImportJdItem(BaseModel):
    """单条手动导入的 JD。"""

    source_url: str = Field(..., min_length=1, description="JD 原始 URL")
    raw_text: str = Field(..., min_length=1, description="JD 原文")
    title: str = Field(..., min_length=1, description="职位名称")
    company: str | None = Field(default=None, description="公司名")
    location: str | None = Field(default=None, description="工作地点")
    salary: str | None = Field(default=None, description="薪资")
    clean_text: str | None = Field(default=None, description="清洗后正文")
    job_title: str | None = Field(default=None, description="职位标题")


class ManualImportRequest(BaseModel):
    """手动导入 JD 请求（无需爬虫适配器的兜底入口）。"""

    jds: list[ManualImportJdItem] = Field(..., min_length=1, description="JD 数组（非空）")
