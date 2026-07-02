"""数据流水线监控 API。

对应 Sprint 1.1：ETL 全链路监控（爬虫采集 → SimHash去重 → 清洗标准化 → 入库 → 图谱构建）。
扩展：DAG并行执行、阶段选择、失败重试/断点续跑、定时调度、SSE实时进度。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.pipeline_models import DataSourceRecord, PipelineRun, PipelineSchedule

router = APIRouter(prefix="/pipeline", tags=["数据流水线"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StageInfo(BaseModel):
    """Single pipeline stage details."""
    name: str = Field(..., description="Stage name")
    status: str = Field(..., description="pending/running/completed/failed/skipped")
    started_at: str | None = Field(None, description="ISO timestamp")
    completed_at: str | None = Field(None, description="ISO timestamp")
    duration_ms: int = Field(0, ge=0)
    records_processed: int = Field(0, ge=0)
    errors: list[str] = Field(default_factory=list)
    retry_count: int = Field(0, ge=0)
    depends_on: list[str] = Field(default_factory=list)


class PipelineRunResponse(BaseModel):
    """Pipeline run details."""
    id: str
    run_type: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    stages: list[StageInfo] = Field(default_factory=list)
    total_records: int = 0
    new_records: int = 0
    updated_records: int = 0
    quality_score: float = 0.0
    error_log: str | None = None
    selected_stages: list[str] | None = None


class PipelineStatusResponse(BaseModel):
    """Global pipeline status overview."""
    is_running: bool = False
    current_run: PipelineRunResponse | None = None
    last_run: PipelineRunResponse | None = None
    run_counts: dict[str, int] = Field(default_factory=dict)
    active_data_sources: int = 0


class TriggerRequest(BaseModel):
    """Request body for manually triggering a pipeline run."""
    run_type: str = Field(default="full", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(
        None, description="Stages to execute; null = all stages",
        examples=[["crawl", "dedup", "import"]],
    )


class TriggerResponse(BaseModel):
    """Response after triggering a pipeline run."""
    run_id: str
    run_type: str
    status: str
    message: str


class RetryStageRequest(BaseModel):
    """Request body for retrying a failed stage."""
    stage_name: str = Field(..., description="Stage name to retry")


class DataSourceResponse(BaseModel):
    """Data source information."""
    id: str
    name: str
    source_type: str
    authority_score: float
    status: str
    last_crawl_at: str | None = None
    total_records: int = 0
    valid_records: int = 0
    duplicate_rate: float = 0.0
    avg_quality_score: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)


class StageStatusResponse(BaseModel):
    """Real-time stage status across recent runs."""
    stages: list[dict[str, Any]] = Field(default_factory=list)


class DataQualityResponse(BaseModel):
    """Data quality metrics and alerts."""
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_scores: dict[str, float] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    alert_count: int = 0


class ScheduleCreateRequest(BaseModel):
    """Create a new pipeline schedule."""
    name: str = Field(..., description="Schedule name")
    cron_expression: str = Field(..., description="cron expression, e.g. '0 2 * * *'")
    run_type: str = Field(default="incremental", description="'full' | 'incremental'")
    selected_stages: list[str] | None = Field(None)
    enabled: bool = Field(default=True)


class ScheduleResponse(BaseModel):
    """Pipeline schedule details."""
    id: str
    name: str
    cron_expression: str
    run_type: str
    selected_stages: list[str] | None = None
    enabled: bool = True
    last_run_at: str | None = None
    next_run_at: str | None = None
    created_at: str | None = None


class PipelineConfigResponse(BaseModel):
    """Current pipeline configuration from SystemConfig / settings."""
    stage_timeout: int
    worker_concurrency: int
    crawl_concurrency: int
    retry_max: int
    retry_backoff: int


class PipelineConfigUpdateRequest(BaseModel):
    """Update pipeline configuration."""
    stage_timeout: int | None = None
    worker_concurrency: int | None = None
    crawl_concurrency: int | None = None
    retry_max: int | None = None
    retry_backoff: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_run(run: PipelineRun) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        stages=[StageInfo(**s) for s in (run.stages or [])],
        total_records=run.total_records,
        new_records=run.new_records,
        updated_records=run.updated_records,
        quality_score=run.quality_score,
        error_log=run.error_log,
        selected_stages=run.selected_stages,
    )


def _serialize_datasource(ds: DataSourceRecord) -> DataSourceResponse:
    return DataSourceResponse(
        id=str(ds.id),
        name=ds.name,
        source_type=ds.source_type,
        authority_score=ds.authority_score,
        status=ds.status,
        last_crawl_at=ds.last_crawl_at.isoformat() if ds.last_crawl_at else None,
        total_records=ds.total_records,
        valid_records=ds.valid_records,
        duplicate_rate=ds.duplicate_rate,
        avg_quality_score=ds.avg_quality_score,
        config=ds.config or {},
    )


def _serialize_schedule(s: PipelineSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(s.id),
        name=s.name,
        cron_expression=s.cron_expression,
        run_type=s.run_type,
        selected_stages=s.selected_stages,
        enabled=s.enabled,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
        created_at=s.created_at.isoformat() if s.created_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineStatusResponse:
    """全局流水线状态概览。"""
    from app.core.pipeline.orchestrator import get_status

    data = await get_status(session)
    return PipelineStatusResponse(
        is_running=data["is_running"],
        current_run=PipelineRunResponse(**data["current_run"]) if data["current_run"] else None,
        last_run=PipelineRunResponse(**data["last_run"]) if data["last_run"] else None,
        run_counts=data["run_counts"],
        active_data_sources=data["active_data_sources"],
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
    return [_serialize_run(r) for r in runs]


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
    return _serialize_run(run)


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_pipeline(
    body: TriggerRequest,
) -> TriggerResponse:
    """手动触发流水线（DAG执行，支持阶段选择）。"""
    from app.core.pipeline.executor import trigger_and_start

    run = await trigger_and_start(
        run_type=body.run_type,
        selected_stages=body.selected_stages,
    )
    return TriggerResponse(
        run_id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        message=f"Pipeline '{run.run_type}' triggered (id={run.id}, stages={body.selected_stages or 'all'})",
    )


@router.post("/runs/{run_id}/retry", response_model=PipelineRunResponse)
async def retry_stage(
    run_id: UUID,
    body: RetryStageRequest,
) -> PipelineRunResponse:
    """重试失败阶段（断点续跑）。"""
    from app.core.pipeline.executor import retry_stage as _retry

    run = await _retry(run_id, body.stage_name)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _serialize_run(run)


@router.post("/runs/{run_id}/resume", response_model=PipelineRunResponse)
async def resume_run(
    run_id: UUID,
) -> PipelineRunResponse:
    """断点续跑：重置所有失败阶段并继续执行。"""
    from app.core.pipeline.executor import resume_run as _resume

    run = await _resume(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _serialize_run(run)


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
    for stage in (run.stages or []):
        stage_list.append({
            "name": stage.get("name"),
            "status": stage.get("status"),
            "started_at": stage.get("started_at"),
            "completed_at": stage.get("completed_at"),
            "duration_ms": stage.get("duration_ms", 0),
            "records_processed": stage.get("records_processed", 0),
            "errors": stage.get("errors", []),
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
    snapshot = await get_quality_snapshot(session)
    return DataQualityResponse(**snapshot)


@router.get("/datasources", response_model=list[DataSourceResponse])
async def get_datasources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DataSourceResponse]:
    """数据源列表及状态。"""
    result = await session.execute(
        select(DataSourceRecord).order_by(DataSourceRecord.authority_score.desc())
    )
    sources = list(result.scalars().all())
    return [_serialize_datasource(ds) for ds in sources]


# ---------------------------------------------------------------------------
# SSE 实时进度
# ---------------------------------------------------------------------------

@router.get("/events")
async def pipeline_events() -> Any:
    """SSE 实时流水线进度事件流。"""
    from fastapi.responses import StreamingResponse
    from app.core.dashboard.sse_broadcaster import event_stream
    from app.services.resources import resources as app_resources

    redis = app_resources.redis_client
    return StreamingResponse(
        event_stream(redis),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 定时调度 CRUD
# ---------------------------------------------------------------------------

@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ScheduleResponse]:
    """列出所有定时调度。"""
    result = await session.execute(select(PipelineSchedule).order_by(PipelineSchedule.created_at.desc()))
    return [_serialize_schedule(s) for s in result.scalars().all()]


@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    body: ScheduleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduleResponse:
    """创建定时调度。"""
    schedule = PipelineSchedule(
        name=body.name,
        cron_expression=body.cron_expression,
        run_type=body.run_type,
        selected_stages=body.selected_stages,
        enabled=body.enabled,
    )
    session.add(schedule)
    await session.flush()
    await session.refresh(schedule)
    return _serialize_schedule(schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
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
    await session.refresh(schedule)
    return _serialize_schedule(schedule)


@router.delete("/schedules/{schedule_id}")
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
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# 流水线配置
# ---------------------------------------------------------------------------

@router.get("/config", response_model=PipelineConfigResponse)
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
) -> PipelineConfigResponse:
    """更新流水线配置（写入 .env 或运行时覆盖）。

    ponytail: runtime override via settings object; .env write is optional future work.
    """
    from app.config import settings
    if body.stage_timeout is not None:
        settings.pipeline_stage_timeout = body.stage_timeout
    if body.worker_concurrency is not None:
        settings.pipeline_worker_concurrency = body.worker_concurrency
    if body.crawl_concurrency is not None:
        settings.pipeline_crawl_concurrency = body.crawl_concurrency
    if body.retry_max is not None:
        settings.pipeline_retry_max = body.retry_max
    if body.retry_backoff is not None:
        settings.pipeline_retry_backoff = body.retry_backoff
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

from fastapi import File, Form, UploadFile
from fastapi.responses import StreamingResponse
from typing import Any as _Any

from app.dependencies import get_neo4j_driver as _get_neo4j_driver
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
from app.services.match_service import _load_prerequisite_map


@router.post("/analyze")
async def analyze_pipeline(
    resume_file: UploadFile = File(..., description="求职者简历文件（PDF/DOCX）"),
    target_positions: str | None = Form(None, description="目标岗位列表，逗号分隔（可选）"),
    driver: _Any = Depends(_get_neo4j_driver),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """上传简历，执行完整的6步求职者分析 Pipeline。"""
    from loguru import logger as _logger

    positions: list[str] = []
    if target_positions:
        positions = [p.strip() for p in target_positions.split(",") if p.strip()]

    content_bytes = await resume_file.read()
    ctx = PipelineContext(resume_file=content_bytes, target_positions=positions)
    repo = PositionRepository(driver)

    try:
        await _load_prerequisite_map(driver)
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
    driver: _Any = Depends(_get_neo4j_driver),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> _Any:
    """上传简历并返回 JSON 格式的完整分析结果。"""
    from fastapi.responses import JSONResponse

    positions: list[str] = []
    if target_positions:
        positions = [p.strip() for p in target_positions.split(",") if p.strip()]

    content_bytes = await resume_file.read()
    ctx = PipelineContext(resume_file=content_bytes, target_positions=positions)
    repo = PositionRepository(driver)

    try:
        await _load_prerequisite_map(driver)
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
            data_line = [l for l in event_str.split("\n") if l.startswith("data:")][0]
            import json as _json
            result = _json.loads(data_line[6:])
            return JSONResponse(content=result)

    return JSONResponse(content=_build_result(ctx))
