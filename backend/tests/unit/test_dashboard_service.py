"""Unit tests for dashboard service."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dashboard.dashboard_service import (
    _cache_key,
    _get_cached,
    _set_cached,
    get_distribution,
    get_overview,
    get_trends,
)


class TestCacheKey:
    def test_cache_key_format(self):
        assert _cache_key("overview").startswith("dashboard:overview")


class TestGetCached:
    @pytest.mark.asyncio
    async def test_none_redis_returns_none(self):
        result = await _get_cached(None, "key")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self):
        class FakeRedis:
            async def get(self, key):
                return None
        result = await _get_cached(FakeRedis(), "key")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_cache_returns_dict(self):
        class FakeRedis:
            async def get(self, key):
                return '{"data": 1}'
        result = await _get_cached(FakeRedis(), "key")
        assert result == {"data": 1}

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        class FakeRedis:
            async def get(self, key):
                return "not-json"
        result = await _get_cached(FakeRedis(), "key")
        assert result is None


class TestSetCached:
    @pytest.mark.asyncio
    async def test_none_redis_returns_early(self):
        await _set_cached(None, "key", {"a": 1}, 60)

    @pytest.mark.asyncio
    async def test_sets_cache(self):
        calls = []
        class FakeRedis:
            async def set(self, key, value, ex=None):
                calls.append((key, value, ex))
        await _set_cached(FakeRedis(), "key", {"a": 1}, 60)
        assert len(calls) == 1


class _FakeScalarResult:
    def __init__(self, val):
        self._val = val

    def scalar(self):
        return self._val

    def scalar_one_or_none(self):
        return self._val


class _FakeScalarListResult:
    def __init__(self, vals):
        self._vals = vals

    def scalars(self):
        return self

    def all(self):
        return self._vals


class _FakeRawRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _make_session(execute_return):
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_return)
    return session


@pytest.mark.asyncio
async def test_get_overview_with_cache_hit():
    redis = MagicMock()
    redis.get = AsyncMock(return_value='{"total_nodes": 5}')
    session = MagicMock()
    result = await get_overview(session, None, redis)
    assert result["total_nodes"] == 5
    assert result["stale"] is False


@pytest.mark.asyncio
async def test_get_overview_with_no_redis_no_data():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=Exception("db error"))
    result = await get_overview(session, None, None)
    assert result["stale"] is True


@pytest.mark.asyncio
async def test_get_trends_default_period():
    session = MagicMock()
    run = MagicMock()
    run.started_at = datetime.now(UTC)
    run.total_records = 10
    run.new_records = 5
    run.quality_score = 0.8

    ext = MagicMock()
    ext.created_at = datetime.now(UTC)

    session.execute = AsyncMock(side_effect=[
        _FakeScalarListResult([run]),
        _FakeScalarListResult([ext]),
    ])

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    result = await get_trends(session, redis)
    assert result["period"] == "7d"
    assert len(result["data_points"]) == 7
    redis.set.assert_called()


@pytest.mark.asyncio
async def test_get_distribution():
    session = MagicMock()
    session.execute = AsyncMock(return_value=_FakeScalarListResult([]))

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    result = await get_distribution(session, redis)
    assert "source_distribution" in result
    assert "domain_distribution" in result
    assert "skill_category_distribution" in result
    redis.set.assert_called()
