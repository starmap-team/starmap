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
    stale: bool = Field(False, description="True if some data came from cache due to source failure")
    stale_since: float | None = Field(None, description="Unix timestamp when staleness began")
    timestamp: float = Field(0.0, description="Response generation time")
 # IndustryClassifier 第四层监测 — 行业质量 KPI
    unclassified_count: int = Field(0, description="已发布岗位中 industry='未分类' 字面量的数量")
    unclassified_ratio: float = Field(0.0, ge=0.0, le=1.0, description="未分类占比 0-1")
    new_24h_unclassified_count: int = Field(0, description="最近 24h 新增岗位中未分类数量")
    new_24h_total: int = Field(0, description="最近 24h 新增岗位总数")
    per_source_unclassified: list[dict] = Field(
        default_factory=list,
        description="各数据源未分类率分布 [{source_site, unclassified, total, ratio}]",
    )
    neo4j_pg_consistency: bool = Field(True, description="Neo4j Industry 节点与 PG 行业值一致性")
    alert_level: str = Field(
        "info",
        description="告警等级：info / warning / critical（基于 4 个指标越界判定）",
    )
    # 多模块联动 Phase 2 (2026-08-17): 技能数据支撑度 — 数据质量闭环
    avg_score: float = Field(0.0, ge=0.0, le=1.0, description="平均技能数据支撑度 0-1（skill_count + confidence + source_count 加权）")
    full_coverage_count: int = Field(0, description="数据支撑完整（≥0.7）的岗位数")
    partial_coverage_count: int = Field(0, description="数据支撑部分（0.4-0.7）的岗位数")
    low_data_support_count: int = Field(0, description="数据支撑不足（<0.4 且有技能）的岗位数")
    no_data_count: int = Field(0, description="0 技能的岗位数（雷达图无法生成）")
    low_data_position_count: int = Field(0, description="低数据岗位总数（low + no_data）")
    low_data_position_sample: list[dict] = Field(
        default_factory=list,
        description="低数据岗位示例（top 10）",
    )
    zero_source_skills_count: int = Field(0, description="source_count=0 的技能数（孤儿技能）")
    low_confidence_skills_count: int = Field(0, description="置信度 <0.5 的技能数")


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
