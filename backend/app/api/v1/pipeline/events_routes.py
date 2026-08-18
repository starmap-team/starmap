"""Pipeline events 子路由（D-02 Task 7 拆分起步）。

包含 SSE 实时事件流 + 轮询降级 2 个端点。后续可继续扩展其他子路由模块。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_current_user_sse,
    resolve_client_ip,
    sse_disconnect,
)
from app.services import resources as _resources_module

router = APIRouter(prefix="", tags=["数据流水线·事件流"])


@router.get("/events")
async def pipeline_events(
    request: Request,
    _user: Annotated[dict[str, Any], Depends(get_current_user_sse)],
) -> Any:
    """SSE 实时流水线进度事件流。

    Auth: accepts JWT via query param ``?token=xxx`` (for EventSource)
    or standard ``Authorization: Bearer xxx`` header.
    """
    from app.services.pipeline_service import event_stream

    redis = _resources_module.resources.redis_client
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/events-poll", response_model=list[dict[str, Any]])
async def poll_pipeline_events(
    _user: Annotated[dict[str, Any], Depends(get_current_user_sse)],
    since: float = Query(0.0, description="Unix timestamp filter"),
) -> list[dict[str, Any]]:
    """Phase 2 POLL-01: SSE polling fallback — 返回最近事件数组。

    Auth: accepts JWT via query param or Authorization header.
    """
    from app.services.pipeline_service import get_recent_events

    redis = _resources_module.resources.redis_client
    if redis is None:
        return []
    events = await get_recent_events(redis, since=since, limit=50)
    return events
