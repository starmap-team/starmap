"""Quality trends + alerts endpoints — extracted from quality.py (Phase 7 quality domain split).

业务说明：质量趋势时间线 + 异常告警 API。
注册到 quality.py 的主 router（prefix="/quality"），最终路径 /quality/trends、/quality/alerts。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.pipeline_models import DataSourceRecord, PipelineRun


class TrendPoint(BaseModel):
    """单日质量趋势数据点。"""

    date: str
    overall_score: float = 0.0
    duplicate_rate: float = 0.0
    freshness_hours: float = 0.0
    total_records: int = 0
    new_records: int = 0
    quality_score: float = 0.0


class QualityTrendsResponse(BaseModel):
    """质量趋势时间线响应。"""

    period: str = Field(..., description="'7d' | '30d' | '90d'")
    data_points: list[TrendPoint] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AlertItem(BaseModel):
    """单条异常告警。"""

    level: str = Field(..., description="'info' | 'warning' | 'critical'")
    dimension: str
    message: str
    source: str | None = None
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = ""
    handled: bool = False


class QualityAlertsResponse(BaseModel):
    """异常告警列表响应。"""

    total: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    alerts: list[AlertItem] = Field(default_factory=list)


router = APIRouter(tags=["质量趋势告警"])


@router.get("/trends", response_model=QualityTrendsResponse)
async def get_quality_trends(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: Annotated[str, Query(description="'7d' | '30d' | '90d'")] = "30d",
) -> QualityTrendsResponse:
    """质量趋势时间线：按天聚合流水线运行质量数据。"""
    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 30)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Fetch completed pipeline runs in the window
    runs_result = await session.execute(
        sa.select(PipelineRun)
        .where(PipelineRun.started_at >= cutoff)
        .where(PipelineRun.status == "completed")
        .order_by(PipelineRun.started_at.asc())
    )
    runs = list(runs_result.scalars().all())

    # Aggregate by day
    daily_quality: dict[str, list[float]] = {}
    daily_records: dict[str, int] = {}
    daily_new: dict[str, int] = {}

    for run in runs:
        day_key = run.started_at.strftime("%Y-%m-%d")
        if run.quality_score > 0:
            daily_quality.setdefault(day_key, []).append(run.quality_score)
        daily_records[day_key] = daily_records.get(day_key, 0) + run.total_records
        daily_new[day_key] = daily_new.get(day_key, 0) + run.new_records

    # Also get source-level duplicate rates for context
    source_result = await session.execute(sa.select(DataSourceRecord))
    sources = list(source_result.scalars().all())
    avg_dup = sum(s.duplicate_rate for s in sources) / len(sources) if sources else 0.0
    avg_freshness = 0.0
    now = datetime.now(UTC)
    for src in sources:
        if src.last_crawl_at is not None:
            last = src.last_crawl_at.replace(tzinfo=UTC) if src.last_crawl_at.tzinfo is None else src.last_crawl_at
            hours = (now - last).total_seconds() / 3600.0
            avg_freshness = max(avg_freshness, hours)

    # Build data points with gap filling
    data_points: list[TrendPoint] = []
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        scores = daily_quality.get(day, [])
        avg_score = sum(scores) / len(scores) if scores else 0.0
        data_points.append(TrendPoint(
            date=day,
            overall_score=round(avg_score, 4),
            duplicate_rate=round(avg_dup, 4),
            freshness_hours=round(avg_freshness, 2),
            total_records=daily_records.get(day, 0),
            new_records=daily_new.get(day, 0),
            quality_score=round(avg_score, 4),
        ))

    # Summary
    all_scores = [dp.quality_score for dp in data_points if dp.quality_score > 0]
    summary = {
        "avg_quality": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
        "min_quality": round(min(all_scores), 4) if all_scores else 0.0,
        "max_quality": round(max(all_scores), 4) if all_scores else 0.0,
        "total_records": sum(dp.total_records for dp in data_points),
        "total_new_records": sum(dp.new_records for dp in data_points),
        "avg_duplicate_rate": round(avg_dup, 4),
        "current_freshness_hours": round(avg_freshness, 2),
    }

    return QualityTrendsResponse(
        period=period,
        data_points=data_points,
        summary=summary,
    )


@router.get("/alerts", response_model=QualityAlertsResponse)
async def get_quality_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    level: Annotated[str | None, Query(description="Filter: 'critical' | 'warning' | 'info'")] = None,
) -> QualityAlertsResponse:
    """异常告警列表：基于 quality_monitor.generate_alerts() 返回实时告警。"""
    from app.core.pipeline.quality_monitor import generate_alerts

    raw_alerts = await generate_alerts(session)

    # Convert to serializable items
    items: list[AlertItem] = []
    for a in raw_alerts:
        if level and a.level != level:
            continue
        items.append(AlertItem(
            level=a.level,
            dimension=a.dimension,
            message=a.message,
            source=a.source,
            value=a.value,
            threshold=a.threshold,
            timestamp=a.timestamp,
            handled=False,
        ))

    # Count by level
    critical = sum(1 for a in items if a.level == "critical")
    warning = sum(1 for a in items if a.level == "warning")
    info = sum(1 for a in items if a.level == "info")

    return QualityAlertsResponse(
        total=len(items),
        critical=critical,
        warning=warning,
        info=info,
        alerts=items,
    )
