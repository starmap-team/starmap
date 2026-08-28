"""数据大屏域 Schema：KPI 概览 / 趋势 / 分布 / 轮询响应。

NEW-18 遗留迁移（PLAN-014 批次4）：从 api/v1/dashboard.py 内联迁入集中管理。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OverviewResponse(BaseModel):
    """Dashboard overview KPIs."""

    total_nodes: int = Field(0, description="Total graph nodes (positions + skills)")
    total_edges: int = Field(0, description="Total graph edges")
    total_positions: int = Field(0, description="Position count")
    total_skills: int = Field(0, description="Skill count")
    total_domains: int = Field(0, description="Distinct industry domains")
    trust_score: float = Field(0.0, ge=0, le=1, description="Average Skill.trust_score from Neo4j (BUG-4 fix)")
    data_source_quality: float = Field(
        0.0, ge=0, le=1,
        description="Weighted data-source quality score (was incorrectly surfaced as `trust_score` pre-BUG-4 fix)",
    )
    hallucination_rate: float = Field(0.0, ge=0, le=1, description="Hallucination rate")
    total_extractions: int = Field(0, description="Total extraction records")
    data_volume: int = Field(0, description="Total pipeline data volume")
    today_extractions: int = Field(0, description="Extractions today")
    pipeline_status: str = Field("idle", description="Latest pipeline run status")
    active_data_sources: int = Field(0, description="Number of active data sources")
    weekly_new_nodes: int = Field(0, description="New nodes this week")
    # 2026-08-28 (批3 三列口径, MINOR-4): 图内/全量/隐藏岗位数（图内+隐藏=全量）
    graph_positions: int = Field(0, description="Graph-projected positions (Neo4j)")
    pg_positions: int = Field(0, description="PG approved positions")
    hidden_positions: int = Field(0, description="Hidden positions (no_skills + non-IT)")
    stale: bool = Field(False, description="True if some data came from cache due to source failure")
    stale_since: float | None = Field(None, description="Unix timestamp when staleness began")
    timestamp: float = Field(0.0, description="Response generation time")


class TrendPoint(BaseModel):
    """Single time-series data point."""

    date: str = Field(..., min_length=1, description="日期（YYYY-MM-DD）")
    total_records: int = Field(0, ge=0, description="累计记录数")
    new_records: int = Field(0, ge=0, description="新增记录数")
    quality_score: float = Field(0.0, ge=0, le=1, description="质量分")
    extractions: int = Field(0, ge=0, description="抽取次数")


class TrendsResponse(BaseModel):
    """Trends time-series response."""

    period: str = Field(..., min_length=1, description="'7d' | '30d' | '90d'")
    data_points: list[TrendPoint] = Field(default_factory=list, description="时序数据点")
    summary: dict[str, Any] = Field(default_factory=dict, description="汇总指标")


class DistributionResponse(BaseModel):
    """Distribution data for dashboard charts."""

    source_distribution: list[dict[str, Any]] = Field(default_factory=list, description="数据源分布")
    domain_distribution: list[dict[str, Any]] = Field(default_factory=list, description="领域分布")
    skill_category_distribution: list[dict[str, Any]] = Field(default_factory=list, description="技能分类分布")
    timestamp: float = Field(0.0, description="响应生成时间戳")


class RealtimePollResponse(BaseModel):
    """Polling fallback for SSE."""

    events: list[dict[str, Any]] = Field(default_factory=list, description="近期事件列表")
    poll_interval_ms: int = Field(5000, ge=500, description="Recommended poll interval in ms")
