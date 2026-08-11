"""Pipeline 配置子路由（D-02 Task 7 拆分）。

/config GET/PUT。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import require_admin
from app.schemas.pipeline import PipelineConfigResponse, PipelineConfigUpdateRequest

router = APIRouter(prefix="", tags=["数据流水线·配置"])


@router.get("/config", response_model=PipelineConfigResponse, dependencies=[Depends(require_admin)])
async def get_pipeline_config() -> PipelineConfigResponse:
    """获取流水线配置（超时/并发/重试）。"""
    from app.config import settings

    return PipelineConfigResponse(
        stage_timeout=settings.pipeline_stage_timeout,
        worker_concurrency=settings.pipeline_worker_concurrency,
        crawl_concurrency=settings.pipeline_crawl_concurrency,
        retry_max=settings.pipeline_retry_max,
        retry_backoff=settings.pipeline_retry_backoff,
    )


@router.put("/config", response_model=PipelineConfigResponse)
async def update_pipeline_config(
    body: PipelineConfigUpdateRequest,
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> PipelineConfigResponse:
    """更新流水线配置（通过 safe_update 防护，不直接修改 settings 单例）。"""
    from app.config import settings

    # Map schema field names to Settings attribute names
    _SCHEMA_TO_SETTINGS = {  # noqa: N806
        "stage_timeout": "pipeline_stage_timeout",
        "worker_concurrency": "pipeline_worker_concurrency",
        "crawl_concurrency": "pipeline_crawl_concurrency",
        "retry_max": "pipeline_retry_max",
        "retry_backoff": "pipeline_retry_backoff",
    }
    raw = body.model_dump(exclude_none=True)
    updates = {_SCHEMA_TO_SETTINGS[k]: v for k, v in raw.items()}
    try:
        settings.safe_update(updates, actor=user.get("sub", "unknown"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return PipelineConfigResponse(
        stage_timeout=settings.pipeline_stage_timeout,
        worker_concurrency=settings.pipeline_worker_concurrency,
        crawl_concurrency=settings.pipeline_crawl_concurrency,
        retry_max=settings.pipeline_retry_max,
        retry_backoff=settings.pipeline_retry_backoff,
    )


__all__ = ["router"]
