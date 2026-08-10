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
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.dependencies import (
    get_current_user_sse,
    get_db_session,
    get_neo4j_driver,
    get_redis_client,
    resolve_client_ip,
    sse_disconnect,
)
from app.schemas.dashboard import (
    DistributionResponse,
    OverviewResponse,
    RealtimePollResponse,
    TrendPoint,
    TrendsResponse,
)
from app.services.dashboard_service import (
    event_stream,
    get_distribution,
    get_overview,
    get_recent_events,
    get_trends,
)

router = APIRouter(prefix="/dashboard", tags=["数据大屏"])


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
    _user: Annotated[dict[str, Any], Depends(get_current_user_sse)],
) -> StreamingResponse:
    """SSE endpoint for real-time dashboard events.

    Streams events from Redis pub/sub with a 15-second heartbeat.
    Event types: ``pipeline_update``, ``quality_alert``,
    ``data_milestone``, ``extraction_complete``.

    Auth: accepts JWT via query param ``?token=xxx`` (for EventSource)
    or standard ``Authorization: Bearer xxx`` header.

    If Redis is unavailable, the client should fall back to
    ``GET /dashboard/realtime-poll``.
    """
    # API-05: 在连接断开时释放 SSE 连接计数
    client_ip = resolve_client_ip(request)

    async def _stream_with_cleanup():
        try:
            async for chunk in event_stream(redis):
                yield chunk
        finally:
            await sse_disconnect(client_ip)

    return StreamingResponse(
        _stream_with_cleanup(),
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
    _user: Annotated[dict[str, Any], Depends(get_current_user_sse)],
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
