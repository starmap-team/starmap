"""Serializers: DB model → Pydantic response conversion for the pipeline API."""
from __future__ import annotations

from app.core.pipeline.humanize_error import humanize_error_log, humanize_errors
from app.models.pipeline_models import DataSourceRecord, PipelineRun, PipelineSchedule
from app.schemas.pipeline import (
    DataSourceResponse,
    PipelineRunResponse,
    ScheduleResponse,
    StageInfo,
)


def serialize_run(run: PipelineRun) -> PipelineRunResponse:
    # 2026-08-21: stages errors 翻译为中文可读；原文保留在 errors_raw（前端展开用）。
    # StageInfo 无 errors_raw 字段时多余键会被 Pydantic 忽略，故仅当存在原文时附加。
    stages: list[StageInfo] = []
    raw_stages = run.stages if isinstance(run.stages, list) else ([run.stages] if run.stages else [])
    for s in raw_stages:
        if not isinstance(s, dict):
            continue
        item = dict(s)
        if isinstance(item.get("errors"), list):
            item["errors_raw"] = item["errors"]
            item["errors"] = humanize_errors(item["errors"])
        stages.append(StageInfo(**item))

    return PipelineRunResponse(
        id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        stages=stages,
        total_records=run.total_records,
        new_records=run.new_records,
        updated_records=run.updated_records,
        quality_score=run.quality_score,
        error_log=humanize_error_log(run.error_log),
        error_log_raw=run.error_log,
        selected_stages=run.selected_stages,
        selected_sources=run.selected_sources,
    )


def serialize_datasource(ds: DataSourceRecord) -> DataSourceResponse:
 # /D1 (2026-08-15): 与 /datasources 端点同源——has_adapter/adapter_platform
 # 由后端 spider 注册表判定（唯一事实源），否则 pipeline 页"可用源"恒 0 与源管理不一致。
    from app.api.v1.datasource import _adapter_capability
    from app.services.spider_registry import PLATFORM_DISPLAY_NAME

    has_adapter, adapter_platform = _adapter_capability(ds)
    # 2026-08-23: 中文适配器名 — 数据源卡片显示中文(如 "Jobicy 远程" 而非 "jobicy")
    display_name = PLATFORM_DISPLAY_NAME.get(ds.name) or ds.name
    return DataSourceResponse(
        id=str(ds.id),
        name=ds.name,
        display_name=display_name,
        source_type=ds.source_type,
        authority_score=ds.authority_score,
        status=ds.status,
        last_crawl_at=ds.last_crawl_at.isoformat() if ds.last_crawl_at else None,
        total_records=ds.total_records,
        valid_records=ds.valid_records,
        duplicate_rate=ds.duplicate_rate,
        avg_quality_score=ds.avg_quality_score,
        config=ds.config or {},
        has_adapter=has_adapter,
        adapter_platform=adapter_platform,
    )


def serialize_schedule(s: PipelineSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(s.id),
        name=s.name,
        cron_expression=s.cron_expression,
        run_type=s.run_type,
        selected_stages=s.selected_stages,
        selected_sources=s.selected_sources,
        enabled=s.enabled,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
        created_at=s.created_at.isoformat() if s.created_at else None,
    )
