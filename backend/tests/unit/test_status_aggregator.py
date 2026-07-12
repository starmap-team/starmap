"""Tests for pipeline status aggregator."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.status_aggregator import (
    CACHE_KEY,
    CACHE_TTL_SECONDS,
    compute_data_quality_aggregates,
    compute_status_aggregates,
    invalidate_status_cache,
    read_or_compute_status_aggregates,
)


# ---------------------------------------------------------------------------
# Fake session infrastructure
# ---------------------------------------------------------------------------

class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class FakeScalarsResult:
    def __init__(self, items: list):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    def __init__(self, scalar_val=None, scalars_list=None):
        self._scalar = FakeScalarResult(scalar_val) if scalar_val is not None else None
        self._scalars = FakeScalarsResult(scalars_list) if scalars_list is not None else None

    def scalar(self):
        return self._scalar.scalar() if self._scalar else None

    def scalars(self):
        return self._scalars


class FakeAsyncSession:
    """Fake async session with configurable per-query results."""

    def __init__(self, results: list | None = None):
        """results: list of FakeResult objects, consumed in order."""
        self._results = results or []
        self._idx = 0

    async def execute(self, stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult(scalar_val=0)


# ---------------------------------------------------------------------------
# compute_status_aggregates
# ---------------------------------------------------------------------------
class TestComputeStatusAggregates:
    @pytest.mark.asyncio
    async def test_normal_case(self):
        session = FakeAsyncSession([
            FakeResult(scalar_val=42),   # today_crawl_volume
            FakeResult(scalar_val=80),   # success_count
            FakeResult(scalar_val=20),   # failed_count
            FakeResult(scalar_val=0.85), # avg_quality_score
        ])
        result = await compute_status_aggregates(session)
        assert result["today_crawl_volume"] == 42
        assert result["success_rate"] == round(80 / 100, 4)
        assert result["avg_quality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_zero_total_success_rate(self):
        session = FakeAsyncSession([
            FakeResult(scalar_val=0),   # today_crawl_volume
            FakeResult(scalar_val=0),   # success_count
            FakeResult(scalar_val=0),   # failed_count
            FakeResult(scalar_val=None),# avg_quality_score
        ])
        result = await compute_status_aggregates(session)
        assert result["success_rate"] == 0.0
        assert result["avg_quality_score"] == 0.0

    @pytest.mark.asyncio
    async def test_db_error_graceful(self):
        class ErrorSession(FakeAsyncSession):
            async def execute(self, stmt):
                raise Exception("db down")

        session = ErrorSession()
        result = await compute_status_aggregates(session)
        assert result["today_crawl_volume"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_quality_score"] == 0.0

    @pytest.mark.asyncio
    async def test_scalar_none_treated_as_zero(self):
        session = FakeAsyncSession([
            FakeResult(scalar_val=None),  # today_crawl_volume
            FakeResult(scalar_val=None),  # success_count
            FakeResult(scalar_val=None),  # failed_count
            FakeResult(scalar_val=None),  # avg_quality_score
        ])
        result = await compute_status_aggregates(session)
        assert result["today_crawl_volume"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_quality_score"] == 0.0


# ---------------------------------------------------------------------------
# compute_data_quality_aggregates
# ---------------------------------------------------------------------------
class TestComputeDataQualityAggregates:
    @pytest.mark.asyncio
    async def test_consistency_with_multiple_sources(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"source_scores": {"A": 0.8, "B": 0.9}, "freshness_hours": 12.0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        # stdev([0.8, 0.9]) ≈ 0.0707, consistency = 1 - min(0.0707/0.5, 1) ≈ 0.8586
        assert 0.8 < result["consistency"] < 0.9
        # timeliness = 1 - min(12/48, 1) = 0.75
        assert result["timeliness"] == 0.75

    @pytest.mark.asyncio
    async def test_consistency_single_source_defaults_1(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"source_scores": {"A": 0.8}, "freshness_hours": 0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        assert result["consistency"] == 1.0
        assert result["timeliness"] == 1.0

    @pytest.mark.asyncio
    async def test_no_existing_metrics(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        result = await compute_data_quality_aggregates(session)
        # No source_scores → consistency=1.0, freshness_hours=0 → timeliness=1.0
        assert result["consistency"] == 1.0
        assert result["timeliness"] == 1.0

    @pytest.mark.asyncio
    async def test_freshness_48h_gives_zero_timeliness(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"freshness_hours": 48.0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        assert result["timeliness"] == 0.0

    @pytest.mark.asyncio
    async def test_freshness_over_48_clamped(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"freshness_hours": 96.0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        assert result["timeliness"] == 0.0  # clamped to 0

    @pytest.mark.asyncio
    async def test_timeliness_calculation_error(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"freshness_hours": "not_a_number"}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        # float("not_a_number") raises ValueError → timeliness = 0.0
        assert result["timeliness"] == 0.0

    @pytest.mark.asyncio
    async def test_consistency_stdev_error(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        # source_scores with non-numeric values that cause stdev error
        metrics = {"source_scores": {"A": "bad", "B": "val"}, "freshness_hours": 0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        # stdev raises TypeError → except → consistency = 0.0
        assert result["consistency"] == 0.0

    @pytest.mark.asyncio
    async def test_high_stdev_gives_zero_consistency(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        metrics = {"source_scores": {"A": 0.0, "B": 1.0}, "freshness_hours": 0}
        result = await compute_data_quality_aggregates(session, existing_metrics=metrics)
        # stdev([0, 1]) ≈ 0.707, 0.707/0.5 = 1.414 → clamped to 1.0
        assert result["consistency"] == 0.0


# ---------------------------------------------------------------------------
# _compute_trend (tested via compute_data_quality_aggregates)
# ---------------------------------------------------------------------------
class TestComputeTrend:
    @pytest.mark.asyncio
    async def test_trend_with_snapshots(self):
        snap1 = SimpleNamespace(snapshot_date=date(2025, 6, 1), overall_score=0.8)
        snap2 = SimpleNamespace(snapshot_date=date(2025, 6, 2), overall_score=0.9)
        session = FakeAsyncSession([FakeResult(scalars_list=[snap1, snap2])])
        result = await compute_data_quality_aggregates(session)
        assert len(result["trend"]) == 2
        assert result["trend"][0]["date"] == "2025-06-01"
        assert result["trend"][0]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_trend_empty_snapshots(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        result = await compute_data_quality_aggregates(session)
        assert result["trend"] == []

    @pytest.mark.asyncio
    async def test_trend_skips_none_snapshot_date(self):
        snap = SimpleNamespace(snapshot_date=None, overall_score=0.5)
        session = FakeAsyncSession([FakeResult(scalars_list=[snap])])
        result = await compute_data_quality_aggregates(session)
        assert result["trend"] == []

    @pytest.mark.asyncio
    async def test_trend_skips_none_overall_score(self):
        snap = SimpleNamespace(snapshot_date=date(2025, 6, 1), overall_score=None)
        session = FakeAsyncSession([FakeResult(scalars_list=[snap])])
        result = await compute_data_quality_aggregates(session)
        assert result["trend"] == []

    @pytest.mark.asyncio
    async def test_trend_db_error_returns_empty(self):
        class ErrorSession(FakeAsyncSession):
            async def execute(self, stmt):
                raise Exception("db error")

        session = ErrorSession()
        result = await compute_data_quality_aggregates(session)
        assert result["trend"] == []

    @pytest.mark.asyncio
    async def test_trend_aggregates_multiple_same_day(self):
        snap1 = SimpleNamespace(snapshot_date=date(2025, 6, 1), overall_score=0.6)
        snap2 = SimpleNamespace(snapshot_date=date(2025, 6, 1), overall_score=0.8)
        session = FakeAsyncSession([FakeResult(scalars_list=[snap1, snap2])])
        result = await compute_data_quality_aggregates(session)
        assert len(result["trend"]) == 1
        assert result["trend"][0]["score"] == round((0.6 + 0.8) / 2, 4)

    @pytest.mark.asyncio
    async def test_trend_no_overall_score_attr(self):
        snap = SimpleNamespace(snapshot_date=date(2025, 6, 1))
        # no overall_score attribute
        session = FakeAsyncSession([FakeResult(scalars_list=[snap])])
        result = await compute_data_quality_aggregates(session)
        assert result["trend"] == []


# ---------------------------------------------------------------------------
# read_or_compute_status_aggregates
# ---------------------------------------------------------------------------
class TestReadOrComputeStatusAggregates:
    @pytest.mark.asyncio
    async def test_redis_cache_hit(self):
        cached_data = {"today_crawl_volume": 10, "success_rate": 0.9, "avg_quality_score": 0.85}
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(cached_data).encode("utf-8"))

        session = FakeAsyncSession()
        result = await read_or_compute_status_aggregates(redis, session)
        assert result["today_crawl_volume"] == 10
        # session.execute should NOT be called
        assert session._idx == 0

    @pytest.mark.asyncio
    async def test_redis_cache_hit_string(self):
        cached_data = {"today_crawl_volume": 5, "success_rate": 0.8, "avg_quality_score": 0.7}
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(cached_data))

        session = FakeAsyncSession()
        result = await read_or_compute_status_aggregates(redis, session)
        assert result["today_crawl_volume"] == 5

    @pytest.mark.asyncio
    async def test_redis_cache_miss_computes(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        session = FakeAsyncSession([
            FakeResult(scalar_val=5),
            FakeResult(scalar_val=10),
            FakeResult(scalar_val=0),
            FakeResult(scalar_val=0.9),
        ])
        result = await read_or_compute_status_aggregates(redis, session)
        assert result["today_crawl_volume"] == 5
        redis.setex.assert_called_once()
        call_args = redis.setex.call_args
        assert call_args[0][0] == CACHE_KEY
        assert call_args[0][1] == CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_no_redis_computes_directly(self):
        session = FakeAsyncSession([
            FakeResult(scalar_val=3),
            FakeResult(scalar_val=5),
            FakeResult(scalar_val=5),
            FakeResult(scalar_val=0.75),
        ])
        result = await read_or_compute_status_aggregates(None, session)
        assert result["today_crawl_volume"] == 3

    @pytest.mark.asyncio
    async def test_redis_read_error_degrades_to_compute(self):
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("redis down"))
        redis.setex = AsyncMock(side_effect=Exception("redis down"))

        session = FakeAsyncSession([
            FakeResult(scalar_val=1),
            FakeResult(scalar_val=1),
            FakeResult(scalar_val=0),
            FakeResult(scalar_val=0.5),
        ])
        result = await read_or_compute_status_aggregates(redis, session)
        assert result["today_crawl_volume"] == 1


# ---------------------------------------------------------------------------
# invalidate_status_cache
# ---------------------------------------------------------------------------
class TestInvalidateStatusCache:
    @pytest.mark.asyncio
    async def test_deletes_cache_key(self):
        redis = AsyncMock()
        await invalidate_status_cache(redis)
        redis.delete.assert_called_once_with(CACHE_KEY)

    @pytest.mark.asyncio
    async def test_none_redis_is_noop(self):
        await invalidate_status_cache(None)  # should not raise

    @pytest.mark.asyncio
    async def test_redis_error_does_not_raise(self):
        redis = AsyncMock()
        redis.delete = AsyncMock(side_effect=Exception("redis down"))
        await invalidate_status_cache(redis)  # should not raise
