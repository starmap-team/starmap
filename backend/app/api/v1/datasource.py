"""数据源管理 API。

Sprint 1.2 新增端点：
  GET  /datasources            — 数据源列表
  GET  /datasources/{id}       — 单个数据源详情
  PUT  /datasources/{id}       — 更新数据源配置
  GET  /datasources/{id}/stats — 数据源统计（日/周/月采集量、质量趋势）
  POST /datasources/{id}/sync  — 触发单源同步
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.pipeline_models import DataSourceRecord, PipelineRun

router = APIRouter(prefix="/datasources", tags=["数据源管理"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DataSourceResponse(BaseModel):
    """数据源详情响应。"""

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


class DataSourceUpdateRequest(BaseModel):
    """数据源更新请求。"""

    authority_score: float | None = Field(None, ge=0, le=1)
    status: str | None = Field(None, description="'active' | 'paused' | 'error'")
    config: dict[str, Any] | None = None


class CrawlVolumeEntry(BaseModel):
    """单日采集量记录。"""

    date: str
    count: int = 0


class QualityTrendEntry(BaseModel):
    """单日质量趋势记录。"""

    date: str
    score: float = 0.0


class DataSourceStatsResponse(BaseModel):
    """数据源统计响应。"""

    source_id: str
    source_name: str
    crawl_volume: list[CrawlVolumeEntry] = Field(default_factory=list)
    quality_trend: list[QualityTrendEntry] = Field(default_factory=list)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_records_per_run: float = 0.0


class SyncTriggerResponse(BaseModel):
    """触发同步响应。"""

    run_id: str
    source_name: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(ds: DataSourceRecord) -> DataSourceResponse:
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DataSourceResponse]:
    """数据源列表（按权威度降序）。"""
    result = await session.execute(
        select(DataSourceRecord).order_by(DataSourceRecord.authority_score.desc())
    )
    return [_serialize(ds) for ds in result.scalars().all()]


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_datasource(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataSourceResponse:
    """单个数据源详情。"""
    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _serialize(ds)


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_datasource(
    source_id: UUID,
    body: DataSourceUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataSourceResponse:
    """更新数据源配置（authority_score / status / config）。"""
    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    values: dict[str, Any] = {}
    if body.authority_score is not None:
        values["authority_score"] = body.authority_score
    if body.status is not None:
        if body.status not in ("active", "paused", "error"):
            raise HTTPException(status_code=400, detail="Invalid status")
        values["status"] = body.status
    if body.config is not None:
        values["config"] = body.config

    if values:
        await session.execute(
            update(DataSourceRecord)
            .where(DataSourceRecord.id == source_id)
            .values(**values)
        )
        await session.flush()
        # Re-fetch
        result = await session.execute(
            select(DataSourceRecord).where(DataSourceRecord.id == source_id)
        )
        ds = result.scalar_one()

    return _serialize(ds)


@router.get("/{source_id}/stats", response_model=DataSourceStatsResponse)
async def get_datasource_stats(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: Annotated[str, Query(description="'7d' | '30d' | '90d'")] = "30d",
) -> DataSourceStatsResponse:
    """数据源统计：日采集量、质量趋势、运行计数。"""
    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Determine lookback window
    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 30)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Pipeline runs that mention this source (run_type == 'source_sync' or
    # completed within window) — aggregate by day
    runs_result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.started_at >= cutoff)
        .order_by(PipelineRun.started_at.asc())
    )
    runs = list(runs_result.scalars().all())

    # Build daily aggregates
    volume_by_day: dict[str, int] = {}
    quality_by_day: dict[str, list[float]] = {}
    total = 0
    successful = 0
    failed = 0
    total_records = 0

    for run in runs:
        day_key = run.started_at.strftime("%Y-%m-%d")
        total += 1
        if run.status == "completed":
            successful += 1
            volume_by_day[day_key] = volume_by_day.get(day_key, 0) + run.total_records
            total_records += run.total_records
            if run.quality_score > 0:
                quality_by_day.setdefault(day_key, []).append(run.quality_score)
        elif run.status == "failed":
            failed += 1

    # Fill gaps for continuous timeline
    crawl_volume: list[CrawlVolumeEntry] = []
    quality_trend: list[QualityTrendEntry] = []
    now = datetime.now(UTC)
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        crawl_volume.append(CrawlVolumeEntry(date=day, count=volume_by_day.get(day, 0)))
        scores = quality_by_day.get(day, [])
        avg = sum(scores) / len(scores) if scores else 0.0
        quality_trend.append(QualityTrendEntry(date=day, score=round(avg, 4)))

    avg_per_run = (total_records / successful) if successful > 0 else 0.0

    return DataSourceStatsResponse(
        source_id=str(ds.id),
        source_name=ds.name,
        crawl_volume=crawl_volume,
        quality_trend=quality_trend,
        total_runs=total,
        successful_runs=successful,
        failed_runs=failed,
        avg_records_per_run=round(avg_per_run, 1),
    )


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse)
async def trigger_source_sync(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncTriggerResponse:
    """触发单源同步（创建一条 source_sync 类型的流水线运行记录）。"""
    from app.core.pipeline.orchestrator import trigger_full_pipeline

    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Create a source_sync pipeline run
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type="source_sync",
        status="running",
        started_at=datetime.now(UTC),
        stages=[
            {
                "name": "crawl",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            },
            {
                "name": "dedup",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            },
            {
                "name": "clean",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            },
            {
                "name": "import",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            },
            {
                "name": "graph_sync",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            },
        ],
    )
    session.add(run)
    await session.flush()

    return SyncTriggerResponse(
        run_id=str(run.id),
        source_name=ds.name,
        status="running",
        message=f"Source sync triggered for '{ds.name}' (run_id={run.id})",
    )
