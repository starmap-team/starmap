"""数据流水线监控 API — endpoint handlers.

Split from pipeline.py in Phase 6 architecture refactor.
"""
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.schemas import (
    CancelResponse,
    DataQualityMetrics,
    DataQualityResponse,
    DataSourceResponse,
    PipelineConfigResponse,
    PipelineConfigUpdateRequest,
    PipelineRunResponse,
    PipelineStatusResponse,
    QualityAlertItem,
    RetryStageRequest,
    ScheduleCreateRequest,
    ScheduleResponse,
    StageStatusResponse,
    TriggerRequest,
    TriggerResponse,
)
from app.api.v1.pipeline.serializers import (
    serialize_datasource,
    serialize_run,
    serialize_schedule,
)
from app.core.matching import MatchService
from app.api.v1.upload_validation import validate_resume_upload
from app.dependencies import get_current_user_sse, get_db_session, get_neo4j_driver, require_admin, sse_disconnect
from app.models.pipeline_models import DataSourceRecord, PipelineRun, PipelineSchedule
from app.pipeline.contracts import PipelineContext
from app.pipeline.engine import PipelineEngine
from app.pipeline.steps import (
    LearningPathStep,
    MatchStep,
    RecommendStep,
    ResumeParseStep,
    SkillExtractStep,
)
from app.repositories.position_repository import PositionRepository

# 创建全局 MatchService 实例
_match_service = MatchService()

router = APIRouter(prefix="/pipeline", tags=["数据流水线"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineStatusResponse:
    """全局流水线状态概览。"""
    from app.core.pipeline.orchestrator import get_status
    from app.core.pipeline.status_aggregator import read_or_compute_status_aggregates

    data = await get_status(session)
    redis_client = getattr(request.app.state.resources, "redis_client", None) if request else None
    aggregates = await read_or_compute_status_aggregates(redis_client, session)

    try:
        from app.core.pipeline.quality_monitor import generate_alerts
        quality_alerts_raw = await generate_alerts(session)
        quality_alerts: list[QualityAlertItem] = [
            QualityAlertItem(
                level=a.level,
                dimension=a.dimension,
                message=a.message,
                source=a.source,
                value=a.value,
                threshold=a.threshold,
                timestamp=a.timestamp,
            )
            for a in quality_alerts_raw
        ]
        if quality_alerts_raw and redis_client:
            from app.core.dashboard.sse_broadcaster import publish_event
            for alert in quality_alerts_raw:
                if alert.level == "error" or alert.level == "critical":
                    await publish_event(redis_client, "quality_alert", {
                        "level": alert.level,
                        "dimension": alert.dimension,
                        "message": alert.message,
                        "source": alert.source,
                        "timestamp": alert.timestamp,
                    })
    except Exception as exc:
        logger.warning("quality_alerts generation failed (non-fatal): {}", exc)
        quality_alerts = []

    return PipelineStatusResponse(
        is_running=data["is_running"],
        current_run=PipelineRunResponse(**data["current_run"]) if data["current_run"] else None,
        last_run=PipelineRunResponse(**data["last_run"]) if data["last_run"] else None,
        run_counts=data["run_counts"],
        active_data_sources=data["active_data_sources"],
        today_crawl_volume=aggregates["today_crawl_volume"],
        success_rate=aggregates["success_rate"],
        avg_quality_score=aggregates["avg_quality_score"],
        quality_alerts=quality_alerts,
    )


@router.get("/runs", response_model=list[PipelineRunResponse])
async def get_pipeline_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
) -> list[PipelineRunResponse]:
    """历史运行记录列表。"""
    from app.core.pipeline.orchestrator import get_run_history

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


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse)
async def cancel_pipeline_run(
    run_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CancelResponse:
    """Phase 1 D-04: 软取消 + Redis STOP flag + Celery 阶段开始时检查。"""
    from app.core.pipeline.orchestrator import RunAlreadyTerminalError, RunNotFoundError, cancel_run

    redis_client = getattr(request.app.state.resources, "redis_client", None)
    try:
        result = await cancel_run(session, redis_client, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RunAlreadyTerminalError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return CancelResponse(
        run_id=str(result.run_id),
        status=result.status,
        cancelled_at=result.cancelled_at.isoformat(),
        stopped_stage_names=result.stopped_stage_names,
    )


@router.post("/trigger", response_model=TriggerResponse, dependencies=[Depends(require_admin)])
async def trigger_pipeline(
    request: Request,
    body: TriggerRequest,
) -> TriggerResponse:
    """手动触发流水线（DAG执行，支持阶段选择）。"""
    from app.core.pipeline.executor import trigger_and_start
    from app.core.pipeline.status_aggregator import invalidate_status_cache

    run = await trigger_and_start(
        run_type=body.run_type,
        selected_stages=body.selected_stages,
    )
    redis_client = getattr(request.app.state.resources, "redis_client", None)
    await invalidate_status_cache(redis_client)
    return TriggerResponse(
        run_id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        message=f"Pipeline '{run.run_type}' triggered (id={run.id}, stages={body.selected_stages or 'all'})",
    )


@router.post("/runs/{run_id}/retry", response_model=PipelineRunResponse, dependencies=[Depends(require_admin)])
async def retry_stage(
    run_id: UUID,
    body: RetryStageRequest,
) -> PipelineRunResponse:
    """重试失败阶段（断点续跑）。"""
    from app.core.pipeline.executor import retry_stage as _retry

    run = await _retry(run_id, body.stage_name)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return serialize_run(run)


@router.post("/runs/{run_id}/resume", response_model=PipelineRunResponse, dependencies=[Depends(require_admin)])
async def resume_run(
    run_id: UUID,
) -> PipelineRunResponse:
    """断点续跑：重置所有失败阶段并继续执行。"""
    from app.core.pipeline.executor import resume_run as _resume

    run = await _resume(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return serialize_run(run)


@router.get("/stages", response_model=StageStatusResponse)
async def get_pipeline_stages(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StageStatusResponse:
    """各阶段实时状态（爬虫/去重/清洗/入库/图谱同步）。"""
    result = await session.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return StageStatusResponse(stages=[])

    stage_list = []
    # Defensive: some legacy rows store stages as a dict (e.g. {"steps": [...]})
    # instead of a list. Normalize to a list to keep the API contract stable.
    raw_stages = run.stages
    if isinstance(raw_stages, dict):
        raw_stages = raw_stages.get("steps") or raw_stages.get("stages") or []
    if not isinstance(raw_stages, list):
        raw_stages = []
    for stage in raw_stages:
        if not isinstance(stage, dict):
            continue
        stage_list.append({
            "name": stage.get("name"),
            "status": stage.get("status"),
            "started_at": stage.get("started_at"),
            "completed_at": stage.get("completed_at"),
            "progress": stage.get("progress", 0.0),
            "duration_ms": stage.get("duration_ms", 0),
            "records_processed": stage.get("records_processed", 0),
            "errors": stage.get("errors", []),
            "errors_count": stage.get("errors_count", len(stage.get("errors", []))),
            "retry_count": stage.get("retry_count", 0),
            "depends_on": stage.get("depends_on", []),
            "run_id": str(run.id),
            "run_status": run.status,
        })
    return StageStatusResponse(stages=stage_list)


@router.get("/data-quality", response_model=DataQualityResponse)
async def get_data_quality(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataQualityResponse:
    """数据质量实时指标。"""
    from app.core.pipeline.quality_monitor import get_quality_snapshot
    from app.core.pipeline.status_aggregator import compute_data_quality_aggregates

    snapshot = await get_quality_snapshot(session)
    extra = await compute_data_quality_aggregates(
        session, existing_metrics=snapshot.get("metrics", {})
    )
    metrics_dict = {**snapshot.get("metrics", {}), **extra}

    alerts_raw = snapshot.get("alerts", [])
    alerts: list[QualityAlertItem] = []
    for a in alerts_raw:
        alerts.append(
            QualityAlertItem(
                level=a.get("level", "info"),
                dimension=a.get("dimension"),
                message=a.get("message", ""),
                source=a.get("source"),
                value=a.get("value"),
                threshold=a.get("threshold"),
                timestamp=a.get("timestamp", ""),
            )
        )

    return DataQualityResponse(
        metrics=DataQualityMetrics(**metrics_dict),
        source_scores=snapshot.get("source_scores", {}),
        alerts=alerts,
        alert_count=len(alerts),
    )


@router.get("/datasources", response_model=list[DataSourceResponse])
async def get_datasources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DataSourceResponse]:
    """数据源列表及状态。"""
    result = await session.execute(
        select(DataSourceRecord).order_by(DataSourceRecord.authority_score.desc())
    )
    sources = list(result.scalars().all())
    return [serialize_datasource(ds) for ds in sources]


# ---------------------------------------------------------------------------
# SSE 实时进度
# ---------------------------------------------------------------------------

@router.get("/events")
async def pipeline_events(
    request: Request,
    _user: Annotated[dict[str, Any], Depends(get_current_user_sse)],
) -> Any:
    """SSE 实时流水线进度事件流。

    Auth: accepts JWT via query param ``?token=xxx`` (for EventSource)
    or standard ``Authorization: Bearer xxx`` header.
    """
    from fastapi.responses import StreamingResponse

    from app.core.dashboard.sse_broadcaster import event_stream
    from app.services.resources import resources as app_resources

    redis = app_resources.redis_client
    # API-05: 在连接断开时释放 SSE 连接计数
    client_ip = request.client.host if request.client else "unknown"

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
    from app.core.dashboard.sse_broadcaster import get_recent_events
    from app.services.resources import resources as app_resources

    redis = app_resources.redis_client
    if redis is None:
        return []
    events = await get_recent_events(redis, since=since, limit=50)
    return events


# ---------------------------------------------------------------------------
# 定时调度 CRUD
# ---------------------------------------------------------------------------

@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ScheduleResponse]:
    """列出所有定时调度。"""
    result = await session.execute(select(PipelineSchedule).order_by(PipelineSchedule.created_at.desc()))
    return [serialize_schedule(s) for s in result.scalars().all()]


@router.post("/schedules", response_model=ScheduleResponse, dependencies=[Depends(require_admin)])
async def create_schedule(
    body: ScheduleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduleResponse:
    """创建定时调度（Phase 2 CRON-02: 创建时计算 next_run_at）。"""
    schedule = PipelineSchedule(
        name=body.name,
        cron_expression=body.cron_expression,
        run_type=body.run_type,
        selected_stages=body.selected_stages,
        enabled=body.enabled,
    )
    try:
        from app.core.pipeline.cron_scheduler import compute_next_cron
        schedule.next_run_at = compute_next_cron(schedule.cron_expression)
    except Exception as exc:
        logger.warning("Failed to compute next_run_at: {}", exc)
    session.add(schedule)
    await session.flush()
    await session.commit()
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
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.name = body.name
    schedule.cron_expression = body.cron_expression
    schedule.run_type = body.run_type
    schedule.selected_stages = body.selected_stages
    schedule.enabled = body.enabled
    await session.flush()
    await session.commit()
    await session.refresh(schedule)
    return serialize_schedule(schedule)


@router.delete("/schedules/{schedule_id}", dependencies=[Depends(require_admin)])
async def delete_schedule(
    schedule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """删除定时调度。"""
    result = await session.execute(select(PipelineSchedule).where(PipelineSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await session.delete(schedule)
    await session.commit()
    return {"status": "deleted"}


@router.post("/schedules/{schedule_id}/trigger", response_model=TriggerResponse, dependencies=[Depends(require_admin)])
async def trigger_schedule(
    schedule_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TriggerResponse:
    """手动触发定时调度：读取调度配置，调用 trigger_pipeline。"""
    result = await session.execute(select(PipelineSchedule).where(PipelineSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    from app.core.pipeline.executor import trigger_and_start
    from app.core.pipeline.status_aggregator import invalidate_status_cache

    run = await trigger_and_start(
        run_type=schedule.run_type,
        selected_stages=schedule.selected_stages,
    )
    # ponytail: update last_run_at on the schedule row
    schedule.last_run_at = run.started_at
    await session.flush()
    await session.commit()

    redis_client = getattr(request.app.state.resources, "redis_client", None)
    await invalidate_status_cache(redis_client)

    return TriggerResponse(
        run_id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        message=f"Schedule '{schedule.name}' triggered (id={run.id})",
    )


# ---------------------------------------------------------------------------
# 流水线配置
# ---------------------------------------------------------------------------

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
    _SCHEMA_TO_SETTINGS = {
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


# ---------------------------------------------------------------------------
# 求职者业务闭环 Pipeline
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_pipeline(
    resume_file: UploadFile = File(..., description="求职者简历文件（PDF/DOCX）"),
    target_positions: str | None = Form(None, description="目标岗位列表，逗号分隔（可选）"),
    driver: Any = Depends(get_neo4j_driver),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """上传简历，执行完整的6步求职者分析 Pipeline。"""
    # INJ-05 / API-06: 统一校验（扩展名 + MIME + 大小 + 魔术字节）
    content_bytes = await validate_resume_upload(resume_file)

    from loguru import logger as _logger

    positions: list[str] = []
    if target_positions:
        positions = [p.strip() for p in target_positions.split(",") if p.strip()]

    ctx = PipelineContext(resume_file=content_bytes, target_positions=positions)
    repo = PositionRepository(driver)

    try:
        await _match_service._load_prerequisite_map(driver)
    except Exception as exc:
        _logger.warning("[Pipeline] Failed to preload prerequisite map: {}", exc)

    engine = PipelineEngine([
        ResumeParseStep(),
        SkillExtractStep(),
        MatchStep(repo=repo, driver=driver, db_session=session),
        LearningPathStep(driver=driver),
        RecommendStep(repo=repo),
    ])

    _logger.info("[Pipeline] Starting analysis for file={}", resume_file.filename)

    return StreamingResponse(
        engine.run(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/export")
async def export_analysis(
    resume_file: UploadFile = File(..., description="求职者简历文件（PDF/DOCX）"),
    target_positions: str | None = Form(None, description="目标岗位列表，逗号分隔（可选）"),
    driver: Any = Depends(get_neo4j_driver),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> Any:
    """上传简历并返回 JSON 格式的完整分析结果。"""
    # INJ-05 / API-06: 统一校验（扩展名 + MIME + 大小 + 魔术字节）
    content_bytes = await validate_resume_upload(resume_file)

    from fastapi.responses import JSONResponse

    positions: list[str] = []
    if target_positions:
        positions = [p.strip() for p in target_positions.split(",") if p.strip()]

    ctx = PipelineContext(resume_file=content_bytes, target_positions=positions)
    repo = PositionRepository(driver)

    try:
        await _match_service._load_prerequisite_map(driver)
    except Exception:
        pass

    engine = PipelineEngine([
        ResumeParseStep(),
        SkillExtractStep(),
        MatchStep(repo=repo, driver=driver, db_session=session),
        LearningPathStep(driver=driver),
        RecommendStep(repo=repo),
    ])

    from app.pipeline.engine import _build_result

    async for event_str in engine.run(ctx):
        if event_str.startswith("event: result"):
            data_line = [line for line in event_str.split("\n") if line.startswith("data:")][0]
            result = json.loads(data_line[6:])
            return JSONResponse(content=result)

    return JSONResponse(content=_build_result(ctx))

