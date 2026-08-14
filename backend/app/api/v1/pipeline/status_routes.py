"""Pipeline 状态/概览子路由（D-02 Task 7 拆分）。

GET 类端点：/status /stages /data-quality /datasources /metrics。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.pipeline.serializers import serialize_datasource
from app.dependencies import get_db_session
from app.exceptions import StarMapError
from app.models.pipeline_models import DataSourceRecord, PipelineRun
from app.schemas.pipeline import (
    DataQualityMetrics,
    DataQualityResponse,
    DataSourceResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    QualityAlertItem,
    StageStatusResponse,
)

router = APIRouter(prefix="", tags=["数据流水线·状态"])


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

    # 跨模块联动 (2026-08-14): 待审岗位/技能计数——与 admin 内容审核同口径
    # （position_records / skill_records review_status=pending_review），
    # 数据产出后的去向指示（新抽取内容进入审核队列）。
    try:
        from sqlalchemy import func as _func

        from app.models.extraction_models import PositionRecord, SkillRecord

        pending_review_positions = int(
            (await session.execute(
                select(_func.count()).select_from(PositionRecord)
                .where(PositionRecord.review_status == "pending_review")
            )).scalar() or 0
        )
        pending_review_skills = int(
            (await session.execute(
                select(_func.count()).select_from(SkillRecord)
                .where(SkillRecord.review_status == "pending_review")
            )).scalar() or 0
        )
    except Exception:  # noqa: BLE001 — 联动计数失败不阻断状态响应
        pending_review_positions = 0
        pending_review_skills = 0

    return PipelineStatusResponse(
        is_running=data["is_running"],
        current_run=PipelineRunResponse(**data["current_run"]) if data["current_run"] else None,
        last_run=PipelineRunResponse(**data["last_run"]) if data["last_run"] else None,
        run_counts=data["run_counts"],
        active_data_sources=data["active_data_sources"],
        today_crawl_volume=aggregates["today_crawl_volume"],
        today_crawl_new=aggregates.get("today_crawl_new", 0),
        total_jd_raw=aggregates.get("total_jd_raw", 0),
        last_crawl_at=last_crawl_iso,
        success_rate=aggregates["success_rate"],
        avg_quality_score=aggregates["avg_quality_score"],
        quality_alerts=quality_alerts,
        pending_review_positions=pending_review_positions,
        pending_review_skills=pending_review_skills,
    )


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
    # 2026-08-12 (pipeline 修复): 改绑最新一条 run（含 failed/cancelled）。
    # 原逻辑按 "running > completed(records>0) > failed" 择优，导致时间线永远定格在
    # 最近一条 completed run 上，最新失败的 run 在运行历史中可见但在 DAG 中被无视，
    # 用户看到 "记录 failed 但 DAG 全绿 100%" 的矛盾。现在 DAG 与运行历史始终一致；
    # failed run 的红色 stage + 错误明细由前端 PipelineStageCard 渲染。
    result = await session.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)
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
                "records_new": stage.get("records_new"),
                "records_duplicate": stage.get("records_duplicate"),
                # D8c: 补 records_seen（crawl 抓到数）——前端 tooltip 口径依赖它
                "records_seen": stage.get("records_seen"),
                "errors": stage.get("errors", []),
                "errors_count": stage.get("errors_count", len(stage.get("errors", []))),
                "warnings": stage.get("warnings", []),
                "retry_count": stage.get("retry_count", 0),
                "depends_on": stage.get("depends_on", []),
                # D8 fix: 序列化漏传 recent_samples/sub_breakdown/current_activity →
                # DAG 卡片展开 + 运行详情 drawer 看不到"爬了哪些岗位/技能"（DB 有但 API 丢弃）
                "recent_samples": stage.get("recent_samples", []),
                "sub_breakdown": stage.get("sub_breakdown", {}),
                "current_activity": stage.get("current_activity", ""),
                "run_id": str(run.id),
                "run_status": run.status,
            }
        )
    return StageStatusResponse(stages=stage_list)


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


__all__ = ["router"]
