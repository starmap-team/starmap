"""Pipeline status aggregator (Phase 1).

实现需求：
- D-01: 首次调用同步计算 + 后续 Redis 10 分钟 TTL 缓存
- D-02: 不在 Phase 1 引入后台定时刷新（推迟到 Phase 2 CRON-*）
- D-03: 聚合逻辑放在 `app/core/pipeline/status_aggregator.py` 新模块

提供 4 个函数：
- compute_status_aggregates: 同步计算 3 个 STATUS-* 字段
- compute_data_quality_aggregates: 同步计算 4 个 QUAL-* 字段（consistency/timeliness/trend）
- read_or_compute_status_aggregates: 首次调用同步 + 后续 Redis 10 分钟 TTL 缓存
- invalidate_status_cache: 删除缓存 key（被 trigger/cancel handler 调用）
"""
from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CACHE_KEY = "pipeline:status:agg"
CACHE_TTL_SECONDS = 600  # 10 分钟


async def compute_status_aggregates(session: AsyncSession) -> dict[str, Any]:
    """同步计算 3 个 STATUS-* 字段（不带缓存）。

    返回 dict 包含:
      - today_crawl_volume: 今日 0 点至今 raw_jd_records 新增数
      - success_rate: 近 7 天 completed / (completed + failed)
      - avg_quality_score: 近 7 天 quality_score 平均
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    try:
        # 1) today_crawl_volume: 今日 0 点至今 raw_jd_records 新增
        from app.models.extraction_models import RawJDRecord
        vol_result = await session.execute(
            select(func.count()).select_from(RawJDRecord)
            .where(RawJDRecord.crawl_time >= today_start)
        )
        today_volume = int(vol_result.scalar() or 0)
    except Exception as exc:
        logger.warning(f"today_crawl_volume query failed: {exc}")
        today_volume = 0

    try:
        # 2) success_rate: 近 7 天 completed / (completed + failed)
        from app.models.pipeline_models import PipelineRun
        success_count_result = await session.execute(
            select(func.count()).select_from(PipelineRun)
            .where(PipelineRun.status == "completed")
            .where(PipelineRun.started_at >= seven_days_ago)
        )
        success_count = int(success_count_result.scalar() or 0)

        failed_count_result = await session.execute(
            select(func.count()).select_from(PipelineRun)
            .where(PipelineRun.status == "failed")
            .where(PipelineRun.started_at >= seven_days_ago)
        )
        failed_count = int(failed_count_result.scalar() or 0)

        total = success_count + failed_count
        success_rate = success_count / total if total > 0 else 0.0
    except Exception as exc:
        logger.warning(f"success_rate query failed: {exc}")
        success_rate = 0.0

    try:
        # 3) avg_quality_score: 近 7 天 quality_score 平均
        from app.models.pipeline_models import PipelineRun
        avg_result = await session.execute(
            select(func.avg(PipelineRun.quality_score))
            .where(PipelineRun.status == "completed")
            .where(PipelineRun.started_at >= seven_days_ago)
        )
        avg_q = avg_result.scalar()
        avg_quality_score = float(avg_q) if avg_q is not None else 0.0
    except Exception as exc:
        logger.warning(f"avg_quality_score query failed: {exc}")
        avg_quality_score = 0.0

    return {
        "today_crawl_volume": today_volume,
        "success_rate": round(success_rate, 4),
        "avg_quality_score": round(avg_quality_score, 4),
    }


async def compute_data_quality_aggregates(
    session: AsyncSession,
    existing_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """同步计算 4 个 QUAL-* 字段（consistency / timeliness / trend）。

    参数 existing_metrics: 已经计算好的 quality_monitor 指标（避免重复查询）
    返回 dict 包含:
      - consistency: 1.0 - min(source_scores.stddev() / 0.5, 1.0)
      - timeliness: 1.0 - min(freshness_hours / 48.0, 1.0)
      - trend: 最近 14 天 evolution_snapshots 聚合
    """
    metrics = existing_metrics or {}

    # 1) consistency: 基于 source_scores 标准差反向（0.5 stddev 为基准）
    try:
        source_scores = metrics.get("source_scores") or {}
        if len(source_scores) >= 2:
            scores = list(source_scores.values())
            stdev = statistics.stdev(scores)
            consistency = max(0.0, 1.0 - min(stdev / 0.5, 1.0))
        else:
            consistency = 1.0  # 单一 source 或无 source，consistency 默认为 1.0
    except Exception as exc:
        logger.warning(f"consistency calculation failed: {exc}")
        consistency = 0.0

    # 2) timeliness: 基于 freshness_hours
    try:
        freshness = float(metrics.get("freshness_hours", 0))
        timeliness = max(0.0, 1.0 - min(freshness / 48.0, 1.0))
    except Exception as exc:
        logger.warning(f"timeliness calculation failed: {exc}")
        timeliness = 0.0

    # 3) trend: 最近 14 天 evolution_snapshots
    trend = await _compute_trend(session)

    return {
        "consistency": round(consistency, 4),
        "timeliness": round(timeliness, 4),
        "trend": trend,
    }


async def _compute_trend(session: AsyncSession) -> list[dict[str, Any]]:
    """从 evolution_snapshots 表取最近 14 天聚合。"""
    try:
        from app.models.evolution_models import EvolutionSnapshot  # 延迟导入避免循环

        fourteen_days_ago = datetime.now(UTC) - timedelta(days=14)
        result = await session.execute(
            select(EvolutionSnapshot)
            .where(EvolutionSnapshot.snapshot_date >= fourteen_days_ago.date())
            .order_by(EvolutionSnapshot.snapshot_date.asc())
        )
        snapshots = result.scalars().all()

        if not snapshots:
            return []

        # 按日期聚合（snapshot_date 作为 key）
        from collections import defaultdict
        daily_scores = defaultdict(list)
        for snap in snapshots:
            if snap.snapshot_date is None:
                continue
            date_key = snap.snapshot_date.isoformat()
            if hasattr(snap, "overall_score") and snap.overall_score is not None:
                daily_scores[date_key].append(float(snap.overall_score))

        # 计算每日均值并按日期排序
        trend = []
        for date_key in sorted(daily_scores.keys()):
            scores = daily_scores[date_key]
            avg = sum(scores) / len(scores) if scores else 0.0
            trend.append({"date": date_key, "score": round(avg, 4)})

        return trend
    except Exception as exc:
        logger.warning(f"trend query failed: {exc}")
        return []


async def read_or_compute_status_aggregates(
    redis_client: Any | None,
    session: AsyncSession,
) -> dict[str, Any]:
    """首次调用同步计算 + 后续 Redis 10 分钟 TTL 缓存。

    返回 dict 包含 compute_status_aggregates 的全部字段。
    """
    # 1) 尝试读 Redis 缓存
    if redis_client is not None:
        try:
            cached = await redis_client.get(CACHE_KEY)
            if cached:
                # redis-py 异步返回 bytes 或 str，统一 parse
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                return json.loads(cached)
        except Exception as exc:
            logger.warning(f"Redis cache read failed (degrading to sync): {exc}")

    # 2) 同步计算
    result = await compute_status_aggregates(session)

    # 3) 写 Redis 缓存（失败降级，不抛错）
    if redis_client is not None:
        try:
            await redis_client.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(result))
        except Exception as exc:
            logger.warning(f"Redis cache write failed (continuing): {exc}")

    return result


async def invalidate_status_cache(redis_client: Any | None) -> None:
    """删除 Redis 缓存 key。被 trigger/cancel handler 调用。"""
    if redis_client is None:
        return
    try:
        await redis_client.delete(CACHE_KEY)
    except Exception as exc:
        logger.warning(f"Redis cache invalidation failed: {exc}")
