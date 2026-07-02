"""Dashboard aggregation service.

Aggregates data from multiple subsystems (graph stats, data sources,
quality metrics, pipeline processing) with graceful degradation.
Single-source failures never cause 500 errors — stale cached data
is returned with a ``"stale": true`` indicator instead.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    RawJDRecord,
    SkillRecord,
)
from app.models.pipeline_models import DataSourceRecord, PipelineRun
from app.services.graph_service import count_edges_neo4j, count_positions_neo4j, count_skills_neo4j

# ---------------------------------------------------------------------------
# Redis cache helpers
# ---------------------------------------------------------------------------

_CACHE_PREFIX = "dashboard"
_OVERVIEW_TTL = 60  # seconds
_TRENDS_TTL = 60
_DISTRIBUTION_TTL = 60


def _cache_key(namespace: str) -> str:
    return f"{_CACHE_PREFIX}:{namespace}"


async def _get_cached(redis: Redis | None, key: str) -> dict | None:
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Redis cache read failed for {}: {}", key, exc)
    return None


async def _set_cached(redis: Redis | None, key: str, data: dict, ttl: int) -> None:
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(data, default=str), ex=ttl)
    except Exception as exc:
        logger.debug("Redis cache write failed for {}: {}", key, exc)


# ---------------------------------------------------------------------------
# Data source helpers (individual subsystem fetchers)
# ---------------------------------------------------------------------------

async def _fetch_graph_stats(session: AsyncSession, neo4j_driver: Any) -> dict[str, Any]:
    """Fetch graph statistics from PostgreSQL + Neo4j."""
    # PostgreSQL counts
    pos_count = (
        await session.execute(sa.select(sa.func.count()).select_from(PositionRecord))
    ).scalar() or 0
    skill_count = (
        await session.execute(sa.select(sa.func.count()).select_from(SkillRecord))
    ).scalar() or 0
    edge_count = (
        await session.execute(sa.select(sa.func.count()).select_from(PositionSkillRelation))
    ).scalar() or 0

    # Neo4j counts (may be higher due to external imports)
    neo4j_pos, neo4j_skill, neo4j_edge = await asyncio.gather(
        count_positions_neo4j(neo4j_driver),
        count_skills_neo4j(neo4j_driver),
        count_edges_neo4j(neo4j_driver),
        return_exceptions=True,
    )

    total_nodes = max(int(pos_count) + int(skill_count), int(neo4j_pos or 0) + int(neo4j_skill or 0))
    total_edges = max(int(edge_count), int(neo4j_edge or 0))
    total_domains = (
        await session.execute(
            sa.select(sa.func.count(sa.distinct(PositionRecord.industry)))
            .where(PositionRecord.industry.isnot(None))
        )
    ).scalar() or 0

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "total_positions": int(pos_count),
        "total_skills": int(skill_count),
        "total_domains": int(total_domains),
    }


async def _fetch_quality_stats(session: AsyncSession) -> dict[str, Any]:
    """Fetch quality / trust / hallucination metrics from DB."""
    # Extraction stats
    ext_stmt = sa.select(
        sa.func.count(JDExtractionRecord.id),
        sa.func.count(JDExtractionRecord.id).filter(JDExtractionRecord.status == "completed"),
        sa.func.count(JDExtractionRecord.id).filter(
            sa.and_(
                JDExtractionRecord.hallucination_score.isnot(None),
                JDExtractionRecord.hallucination_score > 0.5,
            )
        ),
    )
    total_ext, completed_ext, hallucinated = (await session.execute(ext_stmt)).one()
    total_extractions = int(total_ext or 0)
    hallucination_rate = (int(hallucinated or 0) / total_extractions) if total_extractions else 0.0

    # Average trust from extraction confidence + skill source_count proxy
    avg_confidence = 0.0
    if total_extractions > 0:
        avg_confidence = (
            await session.execute(
                sa.select(sa.func.coalesce(sa.func.avg(JDExtractionRecord.confidence), 0.0))
                .where(JDExtractionRecord.confidence > 0)
            )
        ).scalar() or 0.0

    avg_source = (
        await session.execute(
            sa.select(sa.func.coalesce(sa.func.avg(SkillRecord.source_count), 0.0))
        )
    ).scalar() or 0.0
    source_trust = min(1.0, float(avg_source) / 10.0) if float(avg_source) > 0 else 0.0
    avg_trust_score = max(float(avg_confidence), source_trust)

    return {
        "trust_score": round(float(avg_trust_score), 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "total_extractions": total_extractions,
    }


async def _fetch_pipeline_stats(session: AsyncSession) -> dict[str, Any]:
    """Fetch pipeline processing metrics."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total data volume (all records across runs)
    total_volume = (
        await session.execute(
            sa.select(sa.func.coalesce(sa.func.sum(PipelineRun.total_records), 0))
        )
    ).scalar() or 0

    # Today's extractions
    today_extractions = (
        await session.execute(
            sa.select(sa.func.count()).select_from(JDExtractionRecord)
            .where(JDExtractionRecord.created_at >= today_start)
        )
    ).scalar() or 0

    # Latest pipeline run status
    latest_run = (
        await session.execute(
            sa.select(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    pipeline_status = "idle"
    if latest_run:
        pipeline_status = latest_run.status

    # Active data sources
    active_sources = (
        await session.execute(
            sa.select(sa.func.count()).select_from(DataSourceRecord)
            .where(DataSourceRecord.status == "active")
        )
    ).scalar() or 0

    return {
        "data_volume": int(total_volume),
        "today_extractions": int(today_extractions),
        "pipeline_status": pipeline_status,
        "active_data_sources": int(active_sources),
    }


# ---------------------------------------------------------------------------
# Public API: overview
# ---------------------------------------------------------------------------

async def get_overview(
    session: AsyncSession,
    neo4j_driver: Any,
    redis: Redis | None,
) -> dict[str, Any]:
    """Return the full dashboard KPI overview.

    Aggregates 4 data sources: graph stats, quality metrics,
    pipeline stats. Uses ``asyncio.gather(return_exceptions=True)``
    so a single-source failure never causes a 500.
    """
    cache_k = _cache_key("overview")
    cached = await _get_cached(redis, cache_k)
    if cached is not None:
        cached["stale"] = False
        return cached

    # Run data-source fetchers sequentially (SQLAlchemy async sessions
    # do not support concurrent operations on the same session).
    results: list[Any] = []
    for fn in (
        _fetch_graph_stats(session, neo4j_driver),
        _fetch_quality_stats(session),
        _fetch_pipeline_stats(session),
    ):
        try:
            results.append(await fn)
        except BaseException as exc:
            results.append(exc)

    graph_stats: dict = {}
    quality_stats: dict = {}
    pipeline_stats: dict = {}

    stale = False
    stale_since = None

    for i, res in enumerate(results):
        if isinstance(res, BaseException):
            logger.warning("Dashboard source {} failed: {}", i, res)
            stale = True
            stale_since = stale_since or time.time()
        elif i == 0:
            graph_stats = res
        elif i == 1:
            quality_stats = res
        elif i == 2:
            pipeline_stats = res

    overview = {
        **graph_stats,
        **quality_stats,
        **pipeline_stats,
        "stale": stale,
        "stale_since": stale_since,
        "timestamp": time.time(),
    }

    # Cache successful aggregation
    if not stale:
        await _set_cached(redis, cache_k, overview, _OVERVIEW_TTL)
    else:
        # Try returning stale cache from Redis
        stale_cache = await _get_cached(redis, cache_k)
        if stale_cache is not None:
            stale_cache["stale"] = True
            stale_cache["stale_since"] = stale_since
            return stale_cache

    return overview


# ---------------------------------------------------------------------------
# Public API: trends
# ---------------------------------------------------------------------------

async def get_trends(
    session: AsyncSession,
    redis: Redis | None,
    period: str = "7d",
) -> dict[str, Any]:
    """Return time-series data for dashboard charts.

    Aggregates daily pipeline run data (records, quality, new extractions).
    """
    cache_k = _cache_key(f"trends:{period}")
    cached = await _get_cached(redis, cache_k)
    if cached is not None:
        return cached

    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 7)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)

    # Pipeline runs in window
    runs_result = await session.execute(
        sa.select(PipelineRun)
        .where(PipelineRun.started_at >= cutoff)
        .order_by(PipelineRun.started_at.asc())
    )
    runs = list(runs_result.scalars().all())

    # Daily aggregations
    daily_records: dict[str, int] = {}
    daily_new: dict[str, int] = {}
    daily_quality: dict[str, list[float]] = {}
    daily_extractions: dict[str, int] = {}

    for run in runs:
        day_key = run.started_at.strftime("%Y-%m-%d")
        daily_records[day_key] = daily_records.get(day_key, 0) + run.total_records
        daily_new[day_key] = daily_new.get(day_key, 0) + run.new_records
        if run.quality_score > 0:
            daily_quality.setdefault(day_key, []).append(run.quality_score)

    # Daily extractions
    ext_result = await session.execute(
        sa.select(JDExtractionRecord)
        .where(JDExtractionRecord.created_at >= cutoff)
    )
    for ext in ext_result.scalars().all():
        day_key = ext.created_at.strftime("%Y-%m-%d")
        daily_extractions[day_key] = daily_extractions.get(day_key, 0) + 1

    # Build data points
    data_points: list[dict[str, Any]] = []
    for i in range(days):
        dt = now - timedelta(days=days - 1 - i)
        day = dt.strftime("%Y-%m-%d")
        scores = daily_quality.get(day, [])
        avg_q = sum(scores) / len(scores) if scores else 0.0
        data_points.append({
            "date": day,
            "total_records": daily_records.get(day, 0),
            "new_records": daily_new.get(day, 0),
            "quality_score": round(avg_q, 4),
            "extractions": daily_extractions.get(day, 0),
        })

    result = {
        "period": period,
        "data_points": data_points,
        "summary": {
            "total_records": sum(dp["total_records"] for dp in data_points),
            "total_new_records": sum(dp["new_records"] for dp in data_points),
            "total_extractions": sum(dp["extractions"] for dp in data_points),
            "avg_quality": round(
                sum(dp["quality_score"] for dp in data_points if dp["quality_score"] > 0)
                / max(1, sum(1 for dp in data_points if dp["quality_score"] > 0)),
                4,
            ),
        },
    }

    await _set_cached(redis, cache_k, result, _TRENDS_TTL)
    return result


# ---------------------------------------------------------------------------
# Public API: distribution
# ---------------------------------------------------------------------------

async def get_distribution(
    session: AsyncSession,
    redis: Redis | None,
) -> dict[str, Any]:
    """Return multiple distributions for dashboard charts:
    - Data source distribution (by DataSourceRecord)
    - Domain distribution (by PositionRecord.industry)
    - Skill category distribution (by SkillRecord.category)
    """
    cache_k = _cache_key("distribution")
    cached = await _get_cached(redis, cache_k)
    if cached is not None:
        return cached

    # 1. Data source distribution
    src_result = await session.execute(
        sa.select(DataSourceRecord)
        .where(DataSourceRecord.status == "active")
        .order_by(DataSourceRecord.total_records.desc())
    )
    sources = list(src_result.scalars().all())
    if sources:
        source_distribution = [
            {
                "name": s.name,
                "source_type": s.source_type,
                "total_records": s.total_records,
                "valid_records": s.valid_records,
                "authority_score": round(s.authority_score, 2),
                "duplicate_rate": round(s.duplicate_rate, 4),
            }
            for s in sources
        ]
    else:
        # Fallback: aggregate from raw_jd_records by source_platform
        fallback_result = await session.execute(
            sa.select(
                RawJDRecord.source_platform,
                sa.func.count().label("count"),
            )
            .group_by(RawJDRecord.source_platform)
            .order_by(sa.func.count().desc())
        )
        platform_rows = fallback_result.all()
        total_raw = sum(int(r.count) for r in platform_rows) or 1
        platform_names = {
            "lagou": "拉勾网", "zhaopin": "智联招聘", "indeed": "Indeed",
            "sap": "SAP", "talent": "猎聘", "freelancer": "Freelancer",
            "linkedin": "LinkedIn", "51job": "前程无忧", "bosszhipin": "BOSS直聘",
            "test_real_crawl": "测试数据",
        }
        source_distribution = [
            {
                "name": platform_names.get(row.source_platform, row.source_platform),
                "source_type": "crawl",
                "count": int(row.count),
                "total_records": int(row.count),
                "valid_records": int(row.count),
                "percentage": round(int(row.count) / total_raw * 100, 1),
                "authority_score": 0.8,
                "duplicate_rate": 0.0,
            }
            for row in platform_rows
        ]

    # 2. Domain distribution (by industry)
    domain_result = await session.execute(
        sa.select(
            PositionRecord.industry,
            sa.func.count().label("count"),
        )
        .where(PositionRecord.industry.isnot(None))
        .group_by(PositionRecord.industry)
        .order_by(sa.func.count().desc())
        .limit(15)
    )
    domain_distribution = [
        {"name": row.industry or "unknown", "count": int(row.count)}
        for row in domain_result.all()
    ]

    # 3. Skill category distribution
    cat_result = await session.execute(
        sa.select(
            SkillRecord.category,
            sa.func.count().label("count"),
            sa.func.avg(SkillRecord.source_count).label("avg_source_count"),
        )
        .group_by(SkillRecord.category)
        .order_by(sa.func.count().desc())
        .limit(15)
    )
    skill_category_distribution = [
        {
            "name": row.category or "unknown",
            "count": int(row.count),
            "avg_source_count": round(float(row.avg_source_count or 0), 2),
        }
        for row in cat_result.all()
    ]

    result = {
        "source_distribution": source_distribution,
        "domain_distribution": domain_distribution,
        "skill_category_distribution": skill_category_distribution,
        "timestamp": time.time(),
    }

    await _set_cached(redis, cache_k, result, _DISTRIBUTION_TTL)
    return result

