"""Quality trends + alerts endpoints — extracted from quality.py (Phase 7 quality domain split).

业务说明：质量趋势时间线 + 异常告警 API。
注册到 quality.py 的主 router（prefix="/quality"），最终路径 /quality/trends、/quality/alerts。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.pipeline_models import DataSourceRecord, PipelineRun
from app.schemas.quality import (
    AlertHandleRequest,
    AlertItem,
    QualityAlertsResponse,
    QualityTrendsResponse,
    TrendPoint,
)

router = APIRouter(tags=["质量趋势告警"])

# ── 告警处理状态持久化（Redis hash）：用户"解决/忽略"后跨刷新保留 ──
ALERT_HANDLED_KEY = "quality:alert:handled"
ALERT_HANDLED_TTL = 60 * 60 * 24 * 7  # 7 天；告警实时生成，处理状态是用户操作记录


def _alert_key(dimension: str, source: str | None) -> str:
    """告警稳定标识：dimension:source（实时生成告警中可重复的键）。"""
    return f"{dimension}:{source or 'pipeline'}"


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

    # Also get hallucination rate from extraction records
    from app.models.extraction_models import JDExtractionRecord

    ext_result = await session.execute(
        sa.select(JDExtractionRecord)
        .where(JDExtractionRecord.created_at >= cutoff)
    )
    daily_halluc: dict[str, list[float]] = {}
    for ext in ext_result.scalars().all():
        day_key = ext.created_at.strftime("%Y-%m-%d")
        if ext.hallucination_score is not None:
            daily_halluc.setdefault(day_key, []).append(ext.hallucination_score)

    # Build data points with gap filling
    data_points: list[TrendPoint] = []
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        scores = daily_quality.get(day, [])
        avg_score = sum(scores) / len(scores) if scores else 0.0
        halluc_scores = daily_halluc.get(day, [])
        avg_halluc = sum(halluc_scores) / len(halluc_scores) if halluc_scores else 0.0
        data_points.append(TrendPoint(
            date=day,
            overall_score=round(avg_score, 4),
            duplicate_rate=round(avg_dup, 4),
            freshness_hours=round(avg_freshness, 2),
            total_records=daily_records.get(day, 0),
            new_records=daily_new.get(day, 0),
            quality_score=round(avg_score, 4),
            hallucination_rate=round(avg_halluc, 4),
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
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    level: Annotated[str | None, Query(description="Filter: 'critical' | 'warning' | 'info'")] = None,
) -> QualityAlertsResponse:
    """异常告警列表：基于 quality_monitor.generate_alerts() 返回实时告警。

    已处理告警（用户点"解决/忽略"）从 Redis 读取状态并叠加，跨刷新保留。
    """
    from app.services.quality_service import generate_alerts

    raw_alerts = await generate_alerts(session)

    # 读取已处理告警状态（dimension:source → resolved|ignored）
    handled_map: dict[str, str] = {}
    redis_client = getattr(request.app.state.resources, "redis_client", None)
    if redis_client:
        try:
            handled_map = await redis_client.hgetall(ALERT_HANDLED_KEY)
            if isinstance(handled_map, dict):
                handled_map = {k.decode() if isinstance(k, bytes) else str(k): v.decode() if isinstance(v, bytes) else str(v) for k, v in handled_map.items()}
        except Exception:  # noqa: BLE001 — Redis 不可用时告警仍可用（仅失去已处理状态）
            handled_map = {}

    # Convert to serializable items
    items: list[AlertItem] = []
    for idx, a in enumerate(raw_alerts):
        if level and a.level != level:
            continue
        item = AlertItem(
            id=_alert_key(a.dimension, a.source) if a.source else f"alert_{idx}_{a.dimension}",
            type="quality",
            level=a.level,
            dimension=a.dimension,
            message=a.message,
            source=a.source,
            value=a.value,
            threshold=a.threshold,
            timestamp=a.timestamp,
            status="pending",
            created_at=a.timestamp,
            handled=False,
        )
        # 叠加已处理状态（跨刷新保留）
        stored = handled_map.get(item.id)
        if stored in ("resolved", "ignored"):
            item.status = stored
            item.handled = True
        items.append(item)

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


@router.post("/alerts/handle", response_model=QualityAlertsResponse)
async def handle_quality_alert(
    request: Request,
    body: AlertHandleRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QualityAlertsResponse:
    """处理告警：resolve（解决）/ ignore（忽略）。持久化到 Redis，跨刷新保留。"""
    if body.action not in ("resolve", "ignore"):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="action 必须是 'resolve' 或 'ignore'")

    redis_client = getattr(request.app.state.resources, "redis_client", None)
    if redis_client is not None:
        # 存完整词形（resolved/ignored），与 GET /alerts 的 status 判断一致
        stored = "resolved" if body.action == "resolve" else "ignored"
        await redis_client.hset(ALERT_HANDLED_KEY, body.id, stored)
        await redis_client.expire(ALERT_HANDLED_KEY, ALERT_HANDLED_TTL)

    return await get_quality_alerts(request, session)
