"""Serializers: DB model → Pydantic response conversion for the pipeline API."""
from __future__ import annotations

from app.models.pipeline_models import DataSourceRecord, PipelineRun, PipelineSchedule
from app.schemas.pipeline import (
    DataSourceResponse,
    PipelineRunResponse,
    ScheduleResponse,
    StageInfo,
)


def serialize_run(run: PipelineRun) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=str(run.id),
        run_type=run.run_type,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
                stages=[
            StageInfo(**s)
            for s in (
                run.stages if isinstance(run.stages, list)
                else ([run.stages] if run.stages else [])
            )
        ],
        total_records=run.total_records,
        new_records=run.new_records,
        updated_records=run.updated_records,
        quality_score=run.quality_score,
        error_log=run.error_log,
        selected_stages=run.selected_stages,
        selected_sources=run.selected_sources,
    )


def serialize_datasource(ds: DataSourceRecord) -> DataSourceResponse:
    # P0-3/D1 (2026-08-15): 与 /datasources 端点同源——has_adapter/adapter_platform
    # 由后端 spider 注册表判定（唯一事实源），否则 pipeline 页"可用源"恒 0 与源管理不一致。
    from app.api.v1.datasource import _adapter_capability

    has_adapter, adapter_platform = _adapter_capability(ds)
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
