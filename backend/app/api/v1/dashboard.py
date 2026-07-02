"""Data dashboard API — real-time system overview.

Endpoints
---------
GET  /dashboard/overview        — KPI aggregation (all system metrics)
GET  /dashboard/trends          — time-series data for charts
GET  /dashboard/distribution    — data source / domain / skill category distributions
GET  /dashboard/realtime        — SSE endpoint for real-time events
GET  /dashboard/realtime-poll   — polling fallback (returns recent events)
"""
from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.dashboard.dashboard_service import get_distribution, get_overview, get_trends
from app.core.dashboard.sse_broadcaster import get_recent_events, event_stream
from app.dependencies import get_db_session, get_neo4j_driver, get_redis_client

router = APIRouter(prefix="/dashboard", tags=["数据大屏"])


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class OverviewResponse(BaseModel):
    """Dashboard overview KPIs."""

    total_nodes: int = Field(0, description="Total graph nodes (positions + skills)")
    total_edges: int = Field(0, description="Total graph edges")
    total_positions: int = Field(0, description="Position count")
    total_skills: int = Field(0, description="Skill count")
    total_domains: int = Field(0, description="Distinct industry domains")
    trust_score: float = Field(0.0, ge=0, le=1, description="Average trust score")
    hallucination_rate: float = Field(0.0, ge=0, le=1, description="Hallucination rate")
    total_extractions: int = Field(0, description="Total extraction records")
    data_volume: int = Field(0, description="Total pipeline data volume")
    today_extractions: int = Field(0, description="Extractions today")
    pipeline_status: str = Field("idle", description="Latest pipeline run status")
    active_data_sources: int = Field(0, description="Number of active data sources")
    stale: bool = Field(False, description="True if some data came from cache due to source failure")
    stale_since: float | None = Field(None, description="Unix timestamp when staleness began")
    timestamp: float = Field(0.0, description="Response generation time")


class TrendPoint(BaseModel):
    """Single time-series data point."""

    date: str
    total_records: int = 0
    new_records: int = 0
    quality_score: float = 0.0
    extractions: int = 0


class TrendsResponse(BaseModel):
    """Trends time-series response."""

    period: str = Field(..., description="'7d' | '30d' | '90d'")
    data_points: list[TrendPoint] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class DistributionResponse(BaseModel):
    """Distribution data for dashboard charts."""

    source_distribution: list[dict[str, Any]] = Field(default_factory=list)
    domain_distribution: list[dict[str, Any]] = Field(default_factory=list)
    skill_category_distribution: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: float = 0.0


class RealtimePollResponse(BaseModel):
    """Polling fallback for SSE."""

    events: list[dict[str, Any]] = Field(default_factory=list)
    poll_interval_ms: int = Field(5000, description="Recommended poll interval in ms")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse)
async def dashboard_overview(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> OverviewResponse:
    """KPI aggregation: total nodes, edges, domains, positions, skills,
    trust score, hallucination rate, data volume, pipeline status."""
    data = await get_overview(session, neo4j_driver, redis)
    return OverviewResponse(**{
        k: v for k, v in data.items() if k in OverviewResponse.model_fields
    })


@router.get("/trends", response_model=TrendsResponse)
async def dashboard_trends(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
    period: Annotated[str, Query(description="'7d' | '30d' | '90d'")] = "7d",
) -> TrendsResponse:
    """Time-series data for dashboard trend charts."""
    data = await get_trends(session, redis, period)
    return TrendsResponse(
        period=data.get("period", period),
        data_points=[TrendPoint(**dp) for dp in data.get("data_points", [])],
        summary=data.get("summary", {}),
    )


@router.get("/distribution", response_model=DistributionResponse)
async def dashboard_distribution(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> DistributionResponse:
    """Data source distribution, domain distribution, skill category distribution."""
    data = await get_distribution(session, redis)
    return DistributionResponse(
        source_distribution=data.get("source_distribution", []),
        domain_distribution=data.get("domain_distribution", []),
        skill_category_distribution=data.get("skill_category_distribution", []),
        timestamp=data.get("timestamp", 0.0),
    )


@router.get("/realtime")
async def dashboard_realtime(
    request: Request,
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> StreamingResponse:
    """SSE endpoint for real-time dashboard events.

    Streams events from Redis pub/sub with a 15-second heartbeat.
    Event types: ``pipeline_update``, ``quality_alert``,
    ``data_milestone``, ``extraction_complete``.

    If Redis is unavailable, the client should fall back to
    ``GET /dashboard/realtime-poll``.
    """
    return StreamingResponse(
        event_stream(redis),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/realtime-poll", response_model=RealtimePollResponse)
async def dashboard_realtime_poll(
    redis: Annotated[Redis | None, Depends(get_redis_client)],
    since: Annotated[
        float | None,
        Query(description="Unix timestamp — only return events after this time"),
    ] = None,
) -> RealtimePollResponse:
    """Polling fallback for the SSE endpoint.

    Returns events from the last 5 seconds (or since the given timestamp).
    Clients should poll every 5 seconds (``poll_interval_ms = 5000``).
    """
    if since is None:
        since = time.time() - 5.0

    events = await get_recent_events(redis, since=since)
    return RealtimePollResponse(events=events, poll_interval_ms=5000)
