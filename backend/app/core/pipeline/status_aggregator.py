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
# 2026-08-21 (debug 修复): 10 分钟 TTL 太长 —— total_jd_raw/today_crawl_new 等
# 采集指标随流水线实时变化，缓存 10 分钟导致页面"历史累计 0 条"与真实 320 条矛盾。
# 改 60 秒平衡性能与准确性。
CACHE_TTL_SECONDS = 60


async def compute_status_aggregates(session: AsyncSession) -> dict[str, Any]:
    """同步计算 STATUS-* 字段（不带缓存）。

    返回 dict 包含:
      - today_crawl_volume: 今日爬虫处理量 = 今日各 run crawl 阶段 records_processed 之和
        （含重复；与 DAG/历史"处理量"同源，避免"今日跑了多次却显示 0"的困惑）
      - today_crawl_new: 今日 jd_raw 实际新增行数（爬虫 upsert 重复不改 crawled_at）
      - total_jd_raw: jd_raw 全表行数（历史累计）
      - success_rate: 近 7 天 completed / (completed + failed)
      - avg_quality_score: 近 7 天 quality_score 平均
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    try:
        # 1) today_crawl_volume: 今日各 run 的 crawl records_processed 之和（真实采集活动量）
        from sqlalchemy import text as _text
        vol_result = await session.execute(_text(
            """
            SELECT COALESCE(SUM((s->>'records_processed')::int), 0)
            FROM pipeline_runs, jsonb_array_elements(stages::jsonb) s
            WHERE s->>'name' = 'crawl' AND started_at >= :start
              AND status IN ('completed', 'running', 'failed')
            """
        ), {"start": today_start})
        today_volume = int(vol_result.scalar() or 0)
    except Exception:
        logger.exception("today_crawl_volume query failed")
        today_volume = 0

    try:
        # 2) today_crawl_new: 今日 jd_raw 实际新增行数（新增 vs 重复的诚实区分）
        from sqlalchemy import text as _text
        # 2026-08-21 (debug 修复): jd_raw.crawled_at 是 naive 列（crawler 独立库），
        # 传 aware datetime 报 "can't subtract offset-naive and offset-aware" →
        # total_jd_raw 走 fallback 0。对 jd_raw 查询用 naive UTC。
        naive_today_start = today_start.replace(tzinfo=None)
        new_result = await session.execute(
            _text("SELECT COUNT(*) FROM jd_raw WHERE crawled_at >= :start"),
            {"start": naive_today_start},
        )
        today_new = int(new_result.scalar() or 0)
        total_result = await session.execute(_text("SELECT COUNT(*) FROM jd_raw"))
        total_jd_raw = int(total_result.scalar() or 0)
    except Exception:
        logger.exception("today_crawl_new query failed")
        today_new = 0
        total_jd_raw = 0

    try:
        # 3) success_rate: 近 7 天 completed / (completed + failed)
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
    except Exception:
        logger.exception("success_rate query failed")
        success_rate = 0.0

    try:
        # 4) avg_quality_score: 近 7 天 quality_score 平均
        from app.models.pipeline_models import PipelineRun
        avg_result = await session.execute(
            select(func.avg(PipelineRun.quality_score))
            .where(PipelineRun.status == "completed")
            .where(PipelineRun.started_at >= seven_days_ago)
        )
        avg_q = avg_result.scalar()
        avg_quality_score = float(avg_q) if avg_q is not None else 0.0
    except Exception:
        logger.exception("avg_quality_score query failed")
        avg_quality_score = 0.0

    return {
        "today_crawl_volume": today_volume,
        "today_crawl_new": today_new,
        "total_jd_raw": total_jd_raw,
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

    # M5（Phase 13 强制规范）：以“已质检/已入库记录数”判断是否有可评估数据。
    # 无数据时 consistency/timeliness 不得取 vacuous 1.0（否则 overall=1.0 误报“完美”）。
    completeness = float(metrics.get("completeness", 0.0) or 0.0)
    accuracy = float(metrics.get("accuracy", 0.0) or 0.0)
    total_records = int(metrics.get("total_records", 0) or 0)
    valid_records = int(metrics.get("valid_records", 0) or 0)
    # 2026-08-07 修复: source_scores 在 quality_monitor snapshot 顶层,
    # 不在 metrics 内 — 原读取恒 None → consistency 恒 0 (quality 恒 0 根因之一)
    source_scores = metrics.get("source_scores") or {}
    if not source_scores and existing_metrics:
        # 兜底: 从调用方透传的顶层 source_scores (route 层合并)
        source_scores = existing_metrics.get("source_scores") or {}
    has_data = (total_records > 0) or (valid_records > 0)

    # 1) consistency: 基于 source_scores 标准差反向（0.5 stddev 为基准）
    try:
        if len(source_scores) >= 2:
            scores = list(source_scores.values())
            stdev = statistics.stdev(scores)
            consistency = max(0.0, 1.0 - min(stdev / 0.5, 1.0))
        elif len(source_scores) == 1:
            consistency = 1.0  # 单一 source：无方差可比较
        else:
            consistency = 0.0  # M5: 无 source 分数，禁止 vacuous 1.0
    except Exception:
        logger.exception("consistency calculation failed")
        consistency = 0.0

    # 2) timeliness: 基于 freshness_hours（仅在有数据时有意义）
    try:
        freshness = float(metrics.get("freshness_hours", 0))
        timeliness = max(0.0, 1.0 - min(freshness / 48.0, 1.0)) if has_data else 0.0
    except Exception:
        logger.exception("timeliness calculation failed")
        timeliness = 0.0

    # 3) trend: 最近 14 天 evolution_snapshots
    trend = await _compute_trend(session)

    if has_data:
        # 修正：overall 用 4 维均值（含 completeness/accuracy），与文档注释一致
        overall = (completeness + accuracy + consistency + timeliness) / 4.0
        baseline_available = True
        explanation = ""
    else:
        overall = 0.0
        baseline_available = False
        explanation = (
            "暂无已质检/已入库的可评估数据，completeness/accuracy/consistency/timeliness 与 "
            "overall 均不可信（显示为 0，表示‘未评估’而非‘质量差’）。请先运行 pipeline 采集并质检。"
        )

    return {
        "consistency": round(consistency, 4),
        "timeliness": round(timeliness, 4),
        "trend": trend,
        "overall_score": round(overall, 4),
        "baseline_available": baseline_available,
        "quality_explanation": explanation,
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
    except Exception:
        logger.exception("trend query failed")
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
        except Exception:
            logger.exception("Redis cache read failed (degrading to sync)")

    # 2) 同步计算
    result = await compute_status_aggregates(session)

    # 3) 写 Redis 缓存（失败降级，不抛错）
    if redis_client is not None:
        try:
            await redis_client.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(result))
        except Exception:
            logger.exception("Redis cache write failed (continuing)")

    return result


async def invalidate_status_cache(redis_client: Any | None) -> None:
    """删除 Redis 缓存 key。被 trigger/cancel handler 调用。"""
    if redis_client is None:
        return
    try:
        await redis_client.delete(CACHE_KEY)
    except Exception:
        logger.exception("Redis cache invalidation failed")
