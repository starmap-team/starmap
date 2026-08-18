"""Pipeline 定时调度子路由（ Task 7 拆分）。

/schedules CRUD + /schedules/{id}/trigger。
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.serializers import serialize_schedule
from app.dependencies import get_db_session, require_admin
from app.exceptions import StarMapError
from app.models.pipeline_models import PipelineSchedule
from app.schemas.pipeline import ScheduleCreateRequest, ScheduleResponse, TriggerResponse

router = APIRouter(prefix="", tags=["数据流水线·定时调度"])

async def _validate_sources_have_adapters(
 session: AsyncSession, source_names: list[str] | None
) -> None:
 """P1-6 (2026-08-15): 调度目标源必须配置爬虫适配器，否则 400 拒绝。

 selected_sources=None 表示"全部源"，不校验（crawl 阶段对未配置源已跳过）。
 """
 if not source_names:
 return
 from app.models.pipeline_models import DataSourceRecord
 from app.services.spider_registry import has_adapter

 result = await session.execute(
 select(DataSourceRecord).where(DataSourceRecord.name.in_(source_names))
 )
 sources = {s.name: s for s in result.scalars.all}
 missing = [
 name
 for name in source_names
 if name not in sources or not has_adapter(
 (sources[name].config or {}).get("platform")
 or (sources[name].config or {}).get("source_site")
 )
 ]
 if missing:
 raise HTTPException(
 status_code=400,
 detail=(
 "以下数据源未配置爬虫适配器，无法定时调度: "
 + ", ".join(missing)
 ),
 )

@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules(
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ScheduleResponse]:
 """列出所有定时调度。"""
 result = await session.execute(select(PipelineSchedule).order_by(PipelineSchedule.created_at.desc))
 return [serialize_schedule(s) for s in result.scalars.all]

@router.post("/schedules", response_model=ScheduleResponse, dependencies=[Depends(require_admin)])
async def create_schedule(
 body: ScheduleCreateRequest,
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduleResponse:
 """创建定时调度（02: 创建时计算 next_run_at）。"""
 await _validate_sources_have_adapters(session, body.selected_sources)
 schedule = PipelineSchedule(
 name=body.name,
 cron_expression=body.cron_expression,
 run_type=body.run_type,
 selected_stages=body.selected_stages,
 selected_sources=body.selected_sources,
 enabled=body.enabled,
 )
 try:
 from app.services.pipeline_service import compute_next_cron

 schedule.next_run_at = compute_next_cron(schedule.cron_expression)
 except StarMapError:
 raise
 except Exception as exc:
 logger.opt(exception=True).error("Failed to compute next_run_at, saving with None: {}", exc)
 schedule.next_run_at = None
 session.add(schedule)
 await session.flush
 await session.commit
 await session.refresh(schedule)
 return serialize_schedule(schedule)

@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse, dependencies=[Depends(require_admin)])
async def update_schedule(
 schedule_id: UUID,
 body: ScheduleCreateRequest,
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduleResponse:
 """更新定时调度。"""
 result = await session.execute(select(PipelineSchedule).where(PipelineSchedule.id == schedule_id))
 schedule = result.scalar_one_or_none
 if schedule is None:
 raise HTTPException(status_code=404, detail="Schedule not found")
 await _validate_sources_have_adapters(session, body.selected_sources)
 schedule.name = body.name
 schedule.cron_expression = body.cron_expression
 schedule.run_type = body.run_type
 schedule.selected_stages = body.selected_stages
 schedule.selected_sources = body.selected_sources
 schedule.enabled = body.enabled
 await session.flush
 await session.commit
 await session.refresh(schedule)
 return serialize_schedule(schedule)

@router.delete("/schedules/{schedule_id}", dependencies=[Depends(require_admin)])
async def delete_schedule(
 schedule_id: UUID,
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
 """删除定时调度。"""
 result = await session.execute(select(PipelineSchedule).where(PipelineSchedule.id == schedule_id))
 schedule = result.scalar_one_or_none
 if schedule is None:
 raise HTTPException(status_code=404, detail="Schedule not found")
 await session.delete(schedule)
 await session.commit
 return {"status": "deleted"}

@router.post("/schedules/{schedule_id}/trigger", response_model=TriggerResponse, dependencies=[Depends(require_admin)])
async def trigger_schedule(
 schedule_id: UUID,
 request: Request,
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TriggerResponse:
 """手动触发定时调度：读取调度配置，调用 trigger_pipeline。"""
 result = await session.execute(select(PipelineSchedule).where(PipelineSchedule.id == schedule_id))
 schedule = result.scalar_one_or_none
 if schedule is None:
 raise HTTPException(status_code=404, detail="Schedule not found")

 from app.services.pipeline_service import invalidate_status_cache, trigger_and_start

 run = await trigger_and_start(
 run_type=schedule.run_type,
 selected_stages=schedule.selected_stages,
 selected_sources=schedule.selected_sources,
 )
 # ponytail: update last_run_at on the schedule row
 schedule.last_run_at = run.started_at
 await session.flush
 await session.commit

 redis_client = getattr(request.app.state.resources, "redis_client", None)
 await invalidate_status_cache(redis_client)

 return TriggerResponse(
 run_id=str(run.id),
 run_type=run.run_type,
 status=run.status,
 message=f"Schedule '{schedule.name}' triggered (id={run.id})",
 )

__all__ = ["router"]
