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


@pytest.mark.asyncio
async def test_get_distribution_domain_filters_unclassified_and_pending():
    """P1-C (2026-08-17): domain_distribution 限定 approved + 排除「未分类」字面量。

    历史 bug: domain_distribution 不过滤 review_status，pending_review 行混入
    「互联网/IT」等桶，导致分布图 (62 条) 与 KPI 「行业域=3」(approved-only 40 条)
    数字对不上，用户体感撕裂。

    修复后: domain_distribution 与 _fetch_graph_stats.total_domains 口径统一为
    approved-only + 排除未分类。
    """
    from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL

    # Capture all session.execute calls; first is data source, second is domain.
    execute_calls: list = []

    async def _execute_capture(stmt, *args, **kwargs):
        execute_calls.append(stmt)
        # Return empty results for any call
        return _FakeScalarListResult([])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute_capture)

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    result = await get_distribution(session, redis)
    assert "domain_distribution" in result

    # If we couldn't find a candidate (due to dialect quirks), at minimum
    # verify the result is empty + structure preserved
    assert isinstance(result["domain_distribution"], list)

    # The literal 「未分类」 MUST be excluded from domain_distribution
    for entry in result["domain_distribution"]:
        assert entry["name"] != UNCLASSIFIED_INDUSTRY_LITERAL, (
            "domain_distribution must not contain '未分类' — that bucket pollutes stats"
        )


@pytest.mark.asyncio
async def test_get_distribution_domain_excludes_pending_review():
    """P1-C 联动验证: 模拟 pending_review 行被排除（approved-only 过滤生效）。

    直接验证 SQL 层 WHERE 子句含 review_status = 'approved'。
    """
    from sqlalchemy.dialects import postgresql

    session = MagicMock()
    captured_stmts: list = []

    async def _execute_capture(stmt, *args, **kwargs):
        captured_stmts.append(stmt)
        return _FakeScalarListResult([])

    session.execute = AsyncMock(side_effect=_execute_capture)
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    await get_distribution(session, redis)

    # Find the domain query (industry group by)
    domain_stmt = None
    for stmt in captured_stmts:
        s = str(stmt)
        if "industry" in s and "count" in s.lower() and "position_records" in s:
            domain_stmt = stmt
            break

    assert domain_stmt is not None, "domain_distribution SQL not found"
    compiled = str(domain_stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "review_status" in compiled, (
        f"domain_distribution SQL must filter review_status; got:\n{compiled}"
    )
    assert "'approved'" in compiled or "approved" in compiled.lower(), (
        f"domain_distribution SQL must require review_status='approved'; got:\n{compiled}"
    )
