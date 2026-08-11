"""数据流水线监控 API — endpoint handlers.

Split from pipeline.py in Phase 6 architecture refactor.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.serializers import (
    serialize_datasource,
    serialize_run,
    serialize_schedule,
)
from app.api.v1.upload_validation import validate_resume_upload
from app.dependencies import (
    get_db_session,
    get_neo4j_driver,
    require_admin,
)
from app.exceptions import StarMapError
from app.models.pipeline_models import DataSourceRecord, PipelineRun, PipelineSchedule
from app.repositories.position_repository import PositionRepository
from app.schemas.pipeline import (
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
from app.services.pipeline_service import (
    LearningPathStep,
    MatchService,
    MatchStep,
    PipelineContext,
    PipelineEngine,
    RecommendStep,
    ResumeParseStep,
    SkillExtractStep,
)

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
    from app.services.pipeline_service import get_status, read_or_compute_status_aggregates

    data = await get_status(session)
    redis_client = getattr(request.app.state.resources, "redis_client", None) if request else None
    aggregates = await read_or_compute_status_aggregates(redis_client, session)

    try:
        from app.services.pipeline_service import generate_alerts

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
            from app.services.pipeline_service import publish_event

            for alert in quality_alerts_raw:
                if alert.level == "error" or alert.level == "critical":
                    await publish_event(
                        redis_client,
                        "quality_alert",
                        {
                            "level": alert.level,
                            "dimension": alert.dimension,
                            "message": alert.message,
                            "source": alert.source,
                            "timestamp": alert.timestamp,
                        },
                    )
    except StarMapError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Unexpected error in pipeline route: {}", exc)
        quality_alerts = []
    # end of alerts block — after this we always return a valid response

    # Phase 4 P3: 查询最近一次 crawl 时间，让用户看到数据陈旧度
    from sqlalchemy import text as _text
    try:
        last_crawl_result = await session.execute(
            _text("SELECT MAX(crawled_at) FROM jd_raw")
        )
        last_crawl_at = last_crawl_result.scalar()
        last_crawl_iso = last_crawl_at.isoformat() if last_crawl_at else None
    except Exception:
        last_crawl_iso = None

    return PipelineStatusResponse(
        is_running=data["is_running"],
        current_run=PipelineRunResponse(**data["current_run"]) if data["current_run"] else None,
        last_run=PipelineRunResponse(**data["last_run"]) if data["last_run"] else None,
        run_counts=data["run_counts"],
        active_data_sources=data["active_data_sources"],
        today_crawl_volume=aggregates["today_crawl_volume"],
        last_crawl_at=last_crawl_iso,
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
    from app.services.pipeline_service import get_run_history

    runs = await get_run_history(session, limit=limit, offset=offset, status_filter=status)
    return [serialize_run(r) for r in runs]


# ---------------------------------------------------------------------------
# QA B5: 5-stage skeleton returned when no PipelineRun rows exist yet.
# ---------------------------------------------------------------------------

_PIPELINE_SKELETON = (
    ("crawl", "采集", "上游数据采集：JD 爬虫 / RSS / API"),
    ("extract", "抽取", "LLM 抽取技能与归一化"),
    ("standardize", "标准化", "反幻觉评分与别名归并"),
    ("ingest", "入库", "写入 Neo4j 节点与关系边"),
    ("audit", "质检", "信任度评估与人工抽检排队"),
)


def _default_stage_skeleton() -> list[dict[str, Any]]:
    """Return the canonical 5-stage skeleton in the same dict shape as a real run."""
    return [
        {
            "name": key,
            "display_name": display,
            "description": desc,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "progress": 0.0,
            "duration_ms": 0,
            "records_processed": 0,
            "errors": [],
            "errors_count": 0,
            "retry_count": 0,
            "depends_on": ([_PIPELINE_SKELETON[i - 1][0]] if i > 0 else []),
            "run_id": None,
            "run_status": None,
            "skeleton": True,
        }
        for i, (key, display, desc) in enumerate(_PIPELINE_SKELETON)
    ]


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
    from app.services.pipeline_service import RunAlreadyTerminalError, RunNotFoundError, cancel_run

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
    from app.services.pipeline_service import invalidate_status_cache, trigger_and_start

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
    from app.services.pipeline_service import retry_stage as _retry

    run = await _retry(run_id, body.stage_name)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return serialize_run(run)


@router.post("/runs/{run_id}/force-advance", response_model=PipelineRunResponse, dependencies=[Depends(require_admin)])
async def force_advance_pipeline(run_id: UUID) -> PipelineRunResponse:
    """强制推进流水线 (修复 Celery event loop 错误导致的卡死).

    当 Celery 任务因 event loop 错误失败时, run 可能处于 'running' 状态但所有
    stage 既不是 running 也不是 completed。这个接口会先将卡死的 stage 标记为
    FAILED (error_type='stuck_force_advanced'),再调用 advance_pipeline 继续推进。
    """
    from sqlalchemy import select as sa_select

    from app.db.session import get_session_factory
    from app.models.pipeline_models import PipelineRun
    from app.services.pipeline_service import StageStatus, advance_pipeline

    sm = get_session_factory()

    # Phase 7 fix: detect and mark stuck stages before advancing
    async with sm() as session:
        async with session.begin():
            result = await session.execute(sa_select(PipelineRun).where(PipelineRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                raise HTTPException(status_code=404, detail="Pipeline run not found")

            raw_stages = run.stages or []
            stages: list[dict] = raw_stages if isinstance(raw_stages, list) else []
            terminal = {StageStatus.COMPLETED.value, StageStatus.FAILED.value, StageStatus.SKIPPED.value}
            stuck = False

            for s in stages:
                if s["status"] not in terminal and s["status"] != StageStatus.RUNNING.value:
                    # Stuck stage: mark as failed so downstream can proceed
                    s["status"] = StageStatus.FAILED.value
                    s["completed_at"] = datetime.now(UTC).isoformat()
                    s["error_type"] = "stuck_force_advanced"
                    if not s.get("errors"):
                        s["errors"] = []
                    s["errors"].append("Marked as stuck by force-advance command")
                    stuck = True
                    logger.warning("force_advance: marked stuck stage %s as FAILED", s["name"])

            if stuck:
                await session.execute(update(PipelineRun).where(PipelineRun.id == run_id).values(stages=stages))

    # Now advance normally (get_ready_stages will find PENDING successors)
    await advance_pipeline(run_id)

    # 返回最新状态
    sm = get_session_factory()
    async with sm() as session:
        result = await session.execute(sa_select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        return serialize_run(run)


@router.post("/runs/{run_id}/force-reset", response_model=PipelineRunResponse, dependencies=[Depends(require_admin)])
async def force_reset_pipeline(run_id: UUID) -> PipelineRunResponse:
    """Phase 3.8.5: 强制重置卡死的 run (is_running=true 但无 stage running).

    适用场景: advance_pipeline 失败, run 处于幽灵 running 状态。
    操作: 取消这个 run, 但不清空 stage 数据, 方便用户查看发生了什么。
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.session import get_session_factory
    from app.models.pipeline_models import PipelineRun

    sm = get_session_factory()
    async with sm() as session:
        async with session.begin():
            result = await session.execute(sa_select(PipelineRun).where(PipelineRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                raise HTTPException(status_code=404, detail="Pipeline run not found")

            if run.status != "running":
                return serialize_run(run)

            cancelled_at = datetime.now(UTC)
            run.status = "cancelled"
            run.completed_at = cancelled_at
            run.error_log = "force-reset by admin (stuck in running state)"

            if run.stages:
                for stage in run.stages:
                    if stage.get("status") in ("running", "pending"):
                        stage["status"] = "cancelled"
                        stage["completed_at"] = cancelled_at.isoformat()
                flag_modified(run, "stages")

            logger.warning(
                "force_reset_pipeline: run_id={} forced from running to cancelled",
                run_id,
            )

        result = await session.execute(sa_select(PipelineRun).where(PipelineRun.id == run_id))
        return serialize_run(result.scalar_one())


@router.post("/runs/{run_id}/resume", response_model=PipelineRunResponse, dependencies=[Depends(require_admin)])
async def resume_run(
    run_id: UUID,
) -> PipelineRunResponse:
    """断点续跑：重置所有失败阶段并继续执行。"""
    from app.services.pipeline_service import resume_run as _resume

    run = await _resume(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return serialize_run(run)


@router.get("/stages", response_model=StageStatusResponse)
async def get_pipeline_stages(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StageStatusResponse:
    """各阶段实时状态（爬虫/去重/清洗/入库/图谱同步）。

    QA B5: when no PipelineRun exists yet, return the 5-stage skeleton so the
    PipelineMonitor UI is not stuck on a flat "暂无" empty state. The skeleton
    mirrors the canonical pipeline (crawl → extract → standardize → ingest →
    audit) and is purely informational — none of the stages have run.
    """
    # M3（Phase 13 强制规范）：取“最有意义”的最新 run，而非无脑 latest-started_at。
    # cancelled 且 0 记录的 run 是 zombie/孤儿（典型：Celery worker 重启后 task 引用丢失），
    # 它的 stage 快照里常含 “crawl|running” 的过期 in-flight 状态，呈现给用户=误报。
    # 优先：running → completed(records>0) → failed → cancelled(records>0) → latest cancelled（最差兜底）。
    from sqlalchemy import case as _case

    ordering = _case(
        (PipelineRun.status == "running", 0),
        ((PipelineRun.status == "completed") & (PipelineRun.total_records > 0), 1),
        (PipelineRun.status == "failed", 2),
        ((PipelineRun.status == "cancelled") & (PipelineRun.total_records > 0), 3),
        else_=4,
    )
    result = await session.execute(
        select(PipelineRun).order_by(ordering, PipelineRun.started_at.desc()).limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return StageStatusResponse(stages=_default_stage_skeleton())

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
        stage_list.append(
            {
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
            }
        )
    return StageStatusResponse(stages=stage_list)


@router.post("/crawl-source")
def crawl_single_source(  # sync def: 爬取+DB 同步操作放线程池, 避免阻塞 event loop (2026-08-07 修复)
    source: str,
) -> dict[str, Any]:
    """按数据源名称触发单源爬取 (C1 修复, 2026-08-07)。

    前端 triggerCrawl 原调此端点但后端缺失 (404) — 补实现:
    1. 按名称查 DataSourceRecord → platform (config.platform)
    2. spider_registry 找适配器 → run_sync 爬取
    3. 经 crawler.dao.upsert_jd 写入 jd_raw (dedup)
    4. 写 data_source_metrics 指标 (表已补建, D1)
    """
    from crawler.persistence import dao
    from crawler.persistence.database import get_jd_raw_session

    from app.models.data_source_metric import DataSourceMetric
    from app.models.pipeline_models import DataSourceRecord
    from app.services.pipeline_service import build_spider_registry

    # sync def: 用 crawler 同步 engine (psycopg) 查数据源 + 写指标
    # session 内提取所需字段 (detached 实例不可访问属性)
    with get_jd_raw_session() as s:
        row = s.execute(
            select(DataSourceRecord.id, DataSourceRecord.name, DataSourceRecord.config,
                   DataSourceRecord.source_type)
            .where(DataSourceRecord.name == source)
        ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据源 '{source}' 不存在")
    ds_id, ds_name, ds_config, ds_source_type = row
    config = ds_config or {}
    platform = config.get("platform") or _PLATFORM_BY_SOURCE_TYPE.get(ds_source_type)
    if not platform:
        raise HTTPException(status_code=400, detail=f"数据源 '{source}' 未配置爬虫平台")

    spider_fn = build_spider_registry().get(platform)
    if spider_fn is None:
        raise HTTPException(status_code=400, detail=f"平台 '{platform}' 无 spider 适配器")

    keyword = config.get("keyword", "python")
    max_count = int(config.get("max_count", 50))
    items = spider_fn(keyword=keyword, max_count=max_count)

    inserted = duplicate = failed = 0
    from crawler.persistence.models import JdStatus

    for it in items:
        rec = {
            "source_site": it.get("source_site", platform),
            "source_url": it.get("source_url", ""),
            "raw_html": it.get("raw_html", ""),
            "clean_text": it.get("clean_text", ""),
            "job_title": it.get("job_title", "")[:200],
            "company": it.get("company", ""),
            "salary_min": int(it.get("salary_min", 0) or 0),
            "salary_max": int(it.get("salary_max", 0) or 0),
            "location": it.get("location", ""),
            "publish_date": it.get("publish_date", ""),
            "content_hash": it.get("content_hash", ""),
            "status": JdStatus.raw,
        }
        result = dao.upsert_jd(rec)
        if result == "inserted":
            inserted += 1
        elif result == "duplicate":
            duplicate += 1
        else:
            failed += 1

    # 写爬取指标 (D1 后表存在) — 同步 engine
    with get_jd_raw_session() as s:
        s.add(DataSourceMetric(
            source_id=ds_id, run_id=None, status="success" if not failed else "partial",
            records_inserted=inserted, records_duplicate=duplicate,
            error_type=None if not failed else "parse",
            duration_ms=0,
        ))
        s.commit()

    return {
        "source": source, "platform": platform,
        "fetched": len(items), "inserted": inserted,
        "duplicate": duplicate, "failed": failed,
    }


_PLATFORM_BY_SOURCE_TYPE: dict[str, str] = {
    "api": "arbeitnow",
    "rss": "weworkremotely",
}


@router.get("/data-quality", response_model=DataQualityResponse)
async def get_data_quality(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataQualityResponse:
    """数据质量实时指标。"""
    # D3 (2026-08-07): 先聚合真实数据回写 data_sources 统计 (质量评估的来源)
    from app.services.pipeline_service import compute_data_quality_aggregates, get_quality_snapshot, sync_source_quality

    await sync_source_quality(session)
    snapshot = await get_quality_snapshot(session)
    # 2026-08-07 修复: source_scores 在 snapshot 顶层, 合并进 metrics 供聚合读取
    snap_metrics = {**snapshot.get("metrics", {}), "source_scores": snapshot.get("source_scores", {})}
    extra = await compute_data_quality_aggregates(session, existing_metrics=snap_metrics)
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
    result = await session.execute(select(DataSourceRecord).order_by(DataSourceRecord.authority_score.desc()))
    sources = list(result.scalars().all())
    return [serialize_datasource(ds) for ds in sources]


# ---------------------------------------------------------------------------
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
        from app.services.pipeline_service import compute_next_cron

        schedule.next_run_at = compute_next_cron(schedule.cron_expression)
    except StarMapError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Failed to compute next_run_at, saving with None: {}", exc)
        schedule.next_run_at = None
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

    from app.services.pipeline_service import invalidate_status_cache, trigger_and_start

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
    except StarMapError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Unexpected error in pipeline route: {}", exc)
        raise HTTPException(status_code=500, detail="内部处理异常") from exc

    engine = PipelineEngine(
        [
            ResumeParseStep(),
            SkillExtractStep(),
            MatchStep(repo=repo, driver=driver, db_session=session),
            LearningPathStep(driver=driver),
            RecommendStep(repo=repo),
        ]
    )

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
    except StarMapError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Unexpected error in pipeline route: {}", exc)
        raise HTTPException(status_code=500, detail="内部处理异常") from exc

    engine = PipelineEngine(
        [
            ResumeParseStep(),
            SkillExtractStep(),
            MatchStep(repo=repo, driver=driver, db_session=session),
            LearningPathStep(driver=driver),
            RecommendStep(repo=repo),
        ]
    )

    from app.services.pipeline_service import _build_result

    async for event_str in engine.run(ctx):
        if event_str.startswith("event: result"):
            data_line = [line for line in event_str.split("\n") if line.startswith("data:")][0]
            result = json.loads(data_line[6:])
            return JSONResponse(content=result)

    return JSONResponse(content=_build_result(ctx))


# ── Phase 7: Crawler completion Webhook (P0-2 fix) ──


@router.post("/crawler-complete", response_model=dict)
async def crawler_complete_callback(
    source_name: str = Form(...),
    records_crawled: int = Form(0),
) -> dict[str, Any]:
    """废弃此端点。CRAWL 阶段将通过 crawl_source_data 内部感知爬虫完成。

    此端点保有仅为向后兼容，永远返回 noop 状态。
    """
    logger.info("crawler_complete_callback (noop) source=%s records=%s", source_name, records_crawled)
    return {"status": "noop", "source": source_name, "records_crawled": records_crawled}


# ── Phase 7: Pipeline observability metrics (Prometheus-compatible) ──


@router.get("/metrics", response_model=dict)
async def pipeline_metrics(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Expose pipeline observability metrics for Prometheus / Grafana.

    Returns per-stage duration histogram, error_type counts, and run summary.
    Does NOT require admin — designed for scrape access.
    """

    # Recent runs per-stage duration histogram (last 30 days)
    since = datetime.now(UTC) - timedelta(days=30)
    result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.started_at >= since)
        .where(PipelineRun.status.in_(["completed", "failed"]))
        .order_by(PipelineRun.started_at.desc())
        .limit(100)
    )
    runs = result.scalars().all()

    # Per-stage duration aggregation
    stage_durations: dict[str, list[int]] = {}
    error_type_counts: dict[str, int] = {}
    total_runs = len(runs)
    failed_runs = 0

    for run in runs:
        if run.status == "failed":
            failed_runs += 1
        raw_stages = run.stages or []
        stages: list[dict] = raw_stages if isinstance(raw_stages, list) else []
        for s in stages:
            name = s.get("name", "unknown")
            dur = s.get("elapsed_ms", s.get("duration_ms", 0))
            if isinstance(dur, (int, float)) and dur > 0:
                stage_durations.setdefault(name, []).append(int(dur))
            et = s.get("error_type", "")
            if et:
                error_type_counts[et] = error_type_counts.get(et, 0) + 1

    return {
        "total_runs_30d": total_runs,
        "failed_runs_30d": failed_runs,
        "success_rate_30d": round((total_runs - failed_runs) / max(total_runs, 1), 4),
        "stage_duration_p50_ms": {k: sorted(v)[len(v) // 2] if v else 0 for k, v in stage_durations.items()},
        "stage_duration_p95_ms": {
            k: sorted(v)[int(len(v) * 0.95)] if len(v) >= 20 else 0 for k, v in stage_durations.items()
        },
        "error_type_counts": error_type_counts,
    }

# ---------------------------------------------------------------------------# 子路由聚合 (D-02 Task 7)# 当前已拆分：events_routes（2 endpoints）# 未来拆分：status_routes / runs_routes / trigger_routes / schedule_routes / config_routes# ---------------------------------------------------------------------------
from app.api.v1.pipeline.events_routes import router as _events_router  # noqa: E402,F401

router.include_router(_events_router)
