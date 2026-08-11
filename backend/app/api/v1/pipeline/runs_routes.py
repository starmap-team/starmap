"""Pipeline 运行历史子路由（D-02 Task 7 拆分）。

GET 类端点：/runs /runs/{run_id}。
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.serializers import serialize_run
from app.dependencies import get_db_session
from app.models.pipeline_models import PipelineRun
from app.schemas.pipeline import PipelineRunResponse

router = APIRouter(prefix="", tags=["数据流水线·运行历史"])


@router.get("/runs", response_model=list[PipelineRunResponse])
async def get_pipeline_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
) -> list[PipelineRunResponse]:
    """历史运行记录列表。"""
    from app.services.pipeline_service import get_run_history

    runs = await get_run_history(session, limit=limit, offset=offset, status_filter=status)
    return [serialize_run(r) for r in runs]


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineRunResponse:
    """单次运行详情（各阶段状态/耗时/数据量）。"""
    result = await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return serialize_run(run)


__all__ = ["router"]
