"""数据源管理 API。

Sprint 1.2 新增端点：
  GET  /datasources            — 数据源列表
  GET  /datasources/{id}       — 单个数据源详情
  PUT  /datasources/{id}       — 更新数据源配置
  GET  /datasources/{id}/stats — 数据源统计（日/周/月采集量、质量趋势）
  POST /datasources/{id}/sync  — 触发单源同步（执行完整管线）
  GET  /datasources/health     — 数据源健康检查汇总
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_admin
from app.models.pipeline_models import DataSourceRecord
from app.schemas.datasource import (
    CrawlVolumeEntry,
    DataSourceCreateRequest,
    DataSourceResponse,
    DatasourcesHealthResponse,
    DataSourceStatsResponse,
    DataSourceUpdateRequest,
    QualityTrendEntry,
    SourceHealthEntry,
    SyncTriggerResponse,
)

router = APIRouter(prefix="/datasources", tags=["数据源管理"])
admin_router = APIRouter(prefix="/admin/datasources", tags=["数据源管理"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# fix: 敏感配置键的掩码模式，防止 API key/token 经无鉴权列表端点泄露
_SENSITIVE_KEY_PATTERN = re.compile(r"password|token|key|secret|credential", re.IGNORECASE)


def _mask_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """掩码 config 中的敏感键值（password/token/key/secret/credential → '***'）。"""
    if not config:
        return {}
    return {
        k: ("***" if _SENSITIVE_KEY_PATTERN.search(k) else v)
        for k, v in config.items()
    }


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
        config=_mask_config(ds.config),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DataSourceResponse]:
    """数据源列表（按权威度降序）。

    D4 fix (2026-08-12): 返回前先跑 sync_source_quality（D3 聚合，从 jd_raw 回写
    total/valid/quality/dup/last_crawl_at）—— 与 /pipeline/data-quality 同先例，
    保证页面恒显示真实采集数据的聚合口径，不依赖上游触发。经 services 层导入以
    遵守 api→services→core 分层（test_layer_boundary）。
    """
    from app.services.pipeline_service import sync_source_quality

    await sync_source_quality(session)
    result = await session.execute(
        select(DataSourceRecord).order_by(DataSourceRecord.authority_score.desc())
    )
    return [_serialize(ds) for ds in result.scalars().all()]


# ---------------------------------------------------------------------------
# Health check (must be before /{source_id} to avoid route shadowing)
# ---------------------------------------------------------------------------


@router.get("/health", response_model=DatasourcesHealthResponse, dependencies=[Depends(require_admin)])
async def get_datasources_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasourcesHealthResponse:
    """数据源健康检查汇总 — 各源状态 + 最近管线运行状态。"""
    result = await session.execute(
        select(DataSourceRecord).order_by(DataSourceRecord.name.asc())
    )
    sources = list(result.scalars().all())

    entries: list[SourceHealthEntry] = []
    active_count = 0
    error_count = 0

    for ds in sources:
        if ds.status == "active":
            active_count += 1
        elif ds.status == "error":
            error_count += 1

        # ponytail: 原实现循环内查 select(PipelineRun).where(run_type=="source_sync")
        # 未按源过滤（PipelineRun 无 source 外键），所有源返回同一全局最新运行状态——
        # 伪逐源 + N+1。逐源归属需 PipelineRun 迁移，此处诚实降级为 None（语义见
        # schemas/datasource.py SourceHealthEntry.recent_run_status description）。
        entries.append(SourceHealthEntry(
            id=str(ds.id),
            name=ds.name,
            status=ds.status,
            last_crawl_at=ds.last_crawl_at.isoformat() if ds.last_crawl_at else None,
            total_records=ds.total_records,
            recent_run_status=None,
        ))

    return DatasourcesHealthResponse(
        sources=entries,
        total_sources=len(sources),
        active_sources=active_count,
        error_sources=error_count,
    )


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


@router.put("/{source_id}", response_model=DataSourceResponse, dependencies=[Depends(require_admin)])
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


@router.delete("/{source_id}", dependencies=[Depends(require_admin)])
async def delete_datasource(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """软删除数据源（status → 'inactive'）。

    D5 补全 CRUD: 保留 jd_raw / pipeline_runs 历史数据（硬删会孤儿化采集数据），
    仅停用数据源使其退出爬取/同步调度（_get_crawl_configs 只取 active）。
    """
    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    if ds.status == "inactive":
        raise HTTPException(status_code=400, detail="Data source already inactive")
    ds.status = "inactive"
    # D8c fix: 双写 config.disabled=true —— 流水线页 DataSourceManager 只读
    # config.disabled 判断启停，DELETE 仅设 status 导致停用状态在两页不一致
    # （数据源页「已停用」vs 流水线页「待机」）。
    ds.config = {**(ds.config or {}), "disabled": True}
    await session.commit()
    return {"detail": "data source deactivated", "source_id": str(source_id)}


@router.get("/{source_id}/stats", response_model=DataSourceStatsResponse)
async def get_datasource_stats(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: Annotated[Literal["7d", "30d", "90d"], Query(description="统计周期")] = "30d",
) -> DataSourceStatsResponse:
    """数据源统计：日采集量、质量趋势、运行计数。

    E20 fix: previously this endpoint aggregated ALL PipelineRun rows in
    the lookback window, ignoring the {source_id} argument. Result: Jobicy
    / Remotive / ESCO all showed Boss Zhipin's totals (~83k / day) because
    the cron schedule was running Boss crawls that didn't actually belong
    to those sources.

    Fix: read the per-source `sub_breakdown` JSON stored in each
    PipelineRun.stages->crawl and only count records that match this
    source's name (with paren-stripping for "Jobicy (远程)" vs "Jobicy").
    Falls back to run.total_records when the breakdown is absent
    (legacy runs from before the sub_breakdown field was added).
    """
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

    # Build per-source name keys: ["Jobicy (远程)", "Jobicy"]
    ds_name = ds.name
    ds_name_keys = {ds_name.strip().lower(), ds_name.split("(")[0].strip().lower()}

    # Pull the relevant JSON fragment for each run in window.
    # stages->0 is always the "crawl" stage; we read its sub_breakdown map.
    runs_result = await session.execute(
        text("""
            SELECT id, started_at, status, total_records, quality_score,
                   stages
            FROM pipeline_runs
            WHERE started_at >= :cutoff
            ORDER BY started_at ASC
        """),
        {"cutoff": cutoff},
    )
    raw_rows = runs_result.fetchall()

    volume_by_day: dict[str, int] = {}
    quality_by_day: dict[str, list[float]] = {}
    total = 0
    successful = 0
    failed = 0
    total_records = 0

    for _run_id, started_at, status, _total_records_run, quality_score, stages in raw_rows:
        # E20b: try sub_breakdown first (precise), else fall back to
        # counting raw_jd_records by source_platform within the run window.
        # Without the fallback, sources like BOSS Zhipin (whose crawls were
        # recorded in raw_jd_records but never wrote to sub_breakdown) would
        # always show 0.
        source_count = 0
        sub_breakdown: dict[str, Any] = {}
        if isinstance(stages, list):
            for stage in stages:
                if isinstance(stage, dict) and stage.get("name") == "crawl":
                    sub_breakdown = stage.get("sub_breakdown") or {}
                    break
        if sub_breakdown:
            # Sum only the keys that match this DS (case-insensitive, paren-stripped).
            for src_name, cnt in sub_breakdown.items():
                if not isinstance(cnt, (int, float)):
                    continue
                key = str(src_name).strip().lower()
                key_stripped = key.split("(")[0].strip()
                if key in ds_name_keys or key_stripped in {k.split("(")[0].strip() for k in ds_name_keys}:
                    source_count += int(cnt)
        else:
            # No sub_breakdown → we cannot attribute this run's records
            # to a specific source. Count as 0 (under-count rather than
            # mis-attribute). Historical records that pre-date the
            # sub_breakdown field are reflected in DataSourceRecord.total_records
            # (visible in the Tab5 "记录数" column), but they don't show
            # in this 30-day stats chart because they have no associated run.
            source_count = 0

        day_key = started_at.strftime("%Y-%m-%d")
        total += 1
        if status == "completed" and source_count > 0:
            successful += 1
            volume_by_day[day_key] = volume_by_day.get(day_key, 0) + source_count
            total_records += source_count
            if quality_score and quality_score > 0:
                quality_by_day.setdefault(day_key, []).append(quality_score)
        elif status == "failed":
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


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse, dependencies=[Depends(require_admin)])
async def trigger_source_sync(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncTriggerResponse:
    """触发单源同步 — 执行完整管线 (crawl -> dedup -> clean -> import -> graph_sync)。"""

    result = await session.execute(
        select(DataSourceRecord).where(DataSourceRecord.id == source_id)
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Delegate to pipeline executor so stages actually run (previously a no-op)
    # E19 fix: trigger_and_start accepts full/incremental only (DB constraint),
    # so map "source_sync" intent to "incremental" — single-source sync is
    # by definition an incremental crawl.
    # P1-7 fix (functional-review 2026-08-13): 此前未传 selected_sources →
    # 新 run 的 selected_sources=None → crawl 阶段爬全部 active 源，响应却声称
    # "Source sync triggered for 'X'"（单源语义失效）。现透传 ds.name，crawl
    # 阶段按 run.selected_sources 只爬该源。
    from app.services.pipeline_service import trigger_and_start

    run = await trigger_and_start(run_type="incremental", selected_sources=[ds.name])

    return SyncTriggerResponse(
        run_id=str(run.id),
        source_name=ds.name,
        status=run.status,
        message=f"Source sync triggered for '{ds.name}' (run_id={run.id})",
    )


__all__ = ["router", "admin_router"]


# ---------------------------------------------------------------------------
# QA B2: Admin 数据源管理镜像端点。
# 原 admin_router 对象创建后没有任何 @admin_router.get/post 装饰，导致
# GET /api/v1/admin/datasources 返回 404。这里补全列表 + 新建端点。
# ---------------------------------------------------------------------------


@admin_router.get("", response_model=list[DataSourceResponse])
async def list_admin_datasources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    include_inactive: Annotated[bool, Query(description="是否包含已停用/异常数据源")] = True,
) -> list[DataSourceResponse]:
    """管理员视角：列出全部数据源，按状态再按权威度排序。"""
    stmt = select(DataSourceRecord).order_by(
        DataSourceRecord.status.asc(),
        DataSourceRecord.authority_score.desc(),
    )
    if not include_inactive:
        stmt = stmt.where(DataSourceRecord.status == "active")
    result = await session.execute(stmt)
    return [_serialize(ds) for ds in result.scalars().all()]


@admin_router.post("", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    body: DataSourceCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataSourceResponse:
    """管理员：注册一个新数据源记录。"""
    new = DataSourceRecord(
        name=body.name,
        source_type=body.source_type,
        authority_score=body.authority_score,
        status=body.status,
        config=body.config,
    )
    session.add(new)
    await session.flush()
    return _serialize(new)
