"""Pipeline 操作类子路由（D-02 Task 7 拆分）。

POST 操作类端点：/trigger /runs/{id}/cancel|retry|resume|force-advance|force-reset
/crawl-source /analyze /export /crawler-complete。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.serializers import serialize_run
from app.api.v1.upload_validation import validate_resume_upload
from app.dependencies import (
    get_db_session,
    get_neo4j_driver,
    require_admin,
)
from app.exceptions import StarMapError
from app.models.pipeline_models import PipelineRun
from app.repositories.position_repository import PositionRepository
from app.schemas.pipeline import (
    CancelResponse,
    PipelineRunResponse,
    RetryStageRequest,
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

router = APIRouter(prefix="", tags=["数据流水线·操作"])

# 创建全局 MatchService 实例
_match_service = MatchService()


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
    # D5: status 语义诚实化 —— fetched=0 记 no_fetch（网络/平台无数据），
    # 而非误标 success（曾导致"爬了 0 条还显示成功"）
    if len(items) == 0:
        metric_status, metric_error = "no_fetch", "network_or_empty"
    elif not failed:
        metric_status, metric_error = "success", None
    else:
        metric_status, metric_error = "partial", "parse"
    with get_jd_raw_session() as s:
        s.add(DataSourceMetric(
            source_id=ds_id, run_id=None, status=metric_status,
            records_inserted=inserted, records_duplicate=duplicate,
            error_type=metric_error,
            duration_ms=0,
        ))
        s.commit()

    from crawler.persistence import dao
    from crawler.persistence.models import JdStatus

    error_samples = list(dao.get_last_error().items())[:3] if failed else []

    return {
        "source": source, "platform": platform,
        "fetched": len(items), "inserted": inserted,
        "duplicate": duplicate, "failed": failed,
        "error_samples": [
            {"source": k.split("/", 1)[0], "hash_prefix": k.split("/", 1)[1], "error": v}
            for k, v in error_samples
        ],
    }


_PLATFORM_BY_SOURCE_TYPE: dict[str, str] = {
    "api": "arbeitnow",
    "rss": "weworkremotely",
}


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


__all__ = ["router"]
