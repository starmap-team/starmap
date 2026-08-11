"""Pipeline 阶段公共层（D-10）。

提供 6 个阶段模块共用的辅助：SSE 进度发布、异步执行桥、错误类型、DB session、
进度结构 TypedDict。新代码请直接 from app.core.pipeline.stages import execute_*。
"""
from __future__ import annotations

from typing import Any, TypedDict

from loguru import logger
from sqlalchemy import select

from app.core.dashboard.sse_broadcaster import publish_event
from app.db.session import get_session_factory
from app.exceptions import PipelineStageError
from app.services.resources import resources as app_resources

# ponytail: 与 executor 中原本的 _run_async 同源（utils.async_helpers）
from app.utils.async_helpers import run_async as _run_async  # noqa: F401


class StageProgress(TypedDict, total=False):
    """SSE 阶段进度事件结构（Task 10 契约文档化将基于此扩展）。"""

    run_id: str
    stage: str
    status: str
    progress: float
    records_processed: int
    message: str
    current_activity: str
    recent_samples: list[dict[str, Any]]
    sub_breakdown: dict[str, int]
    elapsed_ms: int
    sub_step: str  # D-15 子步骤标识（import/crawl/clean 等）


async def publish_stage_progress(
    run_id: str,
    stage_name: str,
    status: str,
    progress: float = 0.0,
    records_processed: int = 0,
    message: str = "",
    *,
    current_activity: str = "",
    recent_samples: list[dict[str, Any]] | None = None,
    sub_breakdown: dict[str, int] | None = None,
    elapsed_ms: int = 0,
    sub_step: str = "",
) -> None:
    """通过 Redis pub/sub 广播流水线阶段进度事件。

    与 executor 原 _publish_stage_progress 同源；新增 sub_step 字段（D-15）。
    """
    redis = app_resources.redis_client
    payload: dict[str, Any] = {
        "run_id": run_id,
        "stage": stage_name,
        "status": status,
        "progress": progress,
        "records_processed": records_processed,
        "message": message,
        "current_activity": current_activity,
        "recent_samples": recent_samples or [],
        "sub_breakdown": sub_breakdown or {},
        "elapsed_ms": elapsed_ms,
    }
    if sub_step:
        payload["sub_step"] = sub_step
    await publish_event(redis, "pipeline_update", payload)


def run_async(coro: Any) -> Any:
    """同步包装：从 Celery/sync 上下文调用 async 代码。"""
    return _run_async(coro)


__all__ = [
    "PipelineStageError",
    "StageProgress",
    "get_session_factory",
    "logger",
    "publish_stage_progress",
    "run_async",
    "select",
]
