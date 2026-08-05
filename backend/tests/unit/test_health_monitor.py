"""Coverage boost: services/health_monitor.py — 加权熔断/启动探针/退避 (PLAN-013)。

覆盖:
- M1 回归: 错误类型加权熔断 (rate_limit 权重 0; 2×auth 触发; 未达阈值不触发)
- H1: 启动探针 4xx/5xx 自动 paused
- M2: 指数退避 1/2/4/8 → 上限截断 + 成功重置
- record_metric / get_health_dashboard / _probe_sync / _derive_probe_url
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.health_monitor import (
    CIRCUIT_BREAKER_THRESHOLD,
    ERROR_WEIGHTS,
    _derive_probe_url,
    _probe_sync,
    check_and_auto_pause_v2,
    get_health_dashboard,
    probe_sources_at_startup,
    rate_limit_backoff,
    record_metric,
    reset_rate_limit_backoff,
)


def _metric(status: str, error_type: str | None) -> SimpleNamespace:
    return SimpleNamespace(status=status, error_type=error_type)


def _source(**overrides: Any) -> SimpleNamespace:
    base = {
        "id": uuid.uuid4(),
        "name": "Test Source",
        "status": "active",
        "config": {"probe_url": "https://example.com/probe"},
        "source_type": "api",
        "last_crawl_at": None,
        "last_successful_crawl_at": None,
        "authority_score": 0.5,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _Scalars:
    """可迭代 scalars 结果（SQLAlchemy ScalarResult 语义：迭代 = 行）。"""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """可编程假 session：execute → 预置 scalars/get 结果。"""

    def __init__(self, *, scalars: list[Any] | None = None, get_result: Any = None,
                 execute_sides: list[Any] | None = None) -> None:
        self._scalars = scalars or []
        self._get_result = get_result
        self._execute_sides = execute_sides
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self._exec_index = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def execute(self, _stmt: Any) -> SimpleNamespace:
        if self._execute_sides is not None:
            result = self._execute_sides[min(self._exec_index, len(self._execute_sides) - 1)]
            self._exec_index += 1
            return result
        return SimpleNamespace(scalars=lambda: _Scalars(self._scalars))

    async def get(self, _model: Any, _id: Any) -> Any:
        return self._get_result


class TestRecordMetric:
    @pytest.mark.asyncio
    async def test_adds_and_commits(self) -> None:
        session = _FakeSession()
        await record_metric(session, source_id=uuid.uuid4(), run_id=None, status="success", records_inserted=5)
        assert len(session.added) == 1
        assert session.committed == 1

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back_non_fatal(self) -> None:
        session = _FakeSession()
        session.commit = _raise_runtime  # type: ignore[method-assign]
        await record_metric(session, source_id=uuid.uuid4(), run_id=None, status="failed", records_inserted=0)
        assert session.rolled_back == 1


async def _raise_runtime() -> None:
    raise RuntimeError("db down")


class TestCheckAndAutoPauseV2:
    @pytest.mark.asyncio
    async def test_rate_limit_has_zero_weight(self) -> None:
        """M1 回归：rate_limit 错误不累计失败分。"""
        session = _FakeSession(scalars=[_metric("failed", "rate_limit")] * 5)
        assert await check_and_auto_pause_v2(session, uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_two_auth_failures_trigger_pause(self) -> None:
        session = _FakeSession(
            scalars=[_metric("failed", "auth"), _metric("failed", "auth")],
            get_result=_source(),
        )
        assert await check_and_auto_pause_v2(session, uuid.uuid4()) is True

    @pytest.mark.asyncio
    async def test_below_threshold_does_not_pause(self) -> None:
        session = _FakeSession(scalars=[_metric("failed", "connection"), _metric("failed", "connection")])
        assert await check_and_auto_pause_v2(session, uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_already_paused_source_not_recommitted(self) -> None:
        """源已 paused → 不重复写。"""
        session = _FakeSession(
            scalars=[_metric("blocked", "blocked"), _metric("blocked", "blocked")],
            get_result=_source(status="paused"),
        )
        assert await check_and_auto_pause_v2(session, uuid.uuid4()) is False
        assert session.committed == 0

    @pytest.mark.asyncio
    async def test_success_statuses_are_ignored(self) -> None:
        session = _FakeSession(scalars=[_metric("success", None), _metric("success", None)])
        assert await check_and_auto_pause_v2(session, uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_weight_table_consistent_with_threshold_docs(self) -> None:
        """M1 文档口径：2×auth=4.0 触发；1×auth+1×parse=3.5 触发；3×connection=3.0 触发。"""
        auth = ERROR_WEIGHTS["auth"]
        assert 2 * auth >= CIRCUIT_BREAKER_THRESHOLD
        assert auth + ERROR_WEIGHTS["parse"] >= CIRCUIT_BREAKER_THRESHOLD
        assert 3 * ERROR_WEIGHTS["connection"] >= CIRCUIT_BREAKER_THRESHOLD
        assert ERROR_WEIGHTS["rate_limit"] == 0.0


class TestProbeSourcesAtStartup:
    @pytest.mark.asyncio
    async def test_ok_probe_keeps_source_active(self) -> None:
        session = _FakeSession(scalars=[_source()])
        with patch("app.services.health_monitor._probe_sync", return_value="ok"):
            out = await probe_sources_at_startup(session)
        assert out == {"Test Source": "ok"}
        assert session.committed == 0

    @pytest.mark.asyncio
    async def test_http_500_auto_pauses(self) -> None:
        session = _FakeSession(scalars=[_source()])
        with patch("app.services.health_monitor._probe_sync", return_value="http_500"):
            out = await probe_sources_at_startup(session)
        assert out == {"Test Source": "auto_paused:http_500"}
        assert session.committed == 1

    @pytest.mark.asyncio
    async def test_no_probe_url_reported(self) -> None:
        session = _FakeSession(scalars=[_source(config={})])
        with patch("app.services.health_monitor._derive_probe_url", return_value=None):
            out = await probe_sources_at_startup(session)
        assert out == {"Test Source": "no_url"}


class TestProbeSync:
    @pytest.mark.asyncio
    async def test_http_error_maps_to_http_code(self) -> None:
        import urllib.error

        class _FakeResp:
            status = 200

        with patch(
            "app.services.health_monitor.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("u", 503, "unavailable", {}, None),
        ):
            assert _probe_sync("https://x.test", 2) == "http_503"

    @pytest.mark.asyncio
    async def test_url_error_maps_to_url_error(self) -> None:
        import urllib.error

        with patch(
            "app.services.health_monitor.urllib.request.urlopen",
            side_effect=urllib.error.URLError("dns fail"),
        ):
            assert _probe_sync("https://x.test", 2) == "url_error:dns fail"

    @pytest.mark.asyncio
    async def test_ok_response(self) -> None:
        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_: Any) -> None:
                return None

        with patch("app.services.health_monitor.urllib.request.urlopen", return_value=_FakeResp()):
            assert _probe_sync("https://x.test", 2) == "ok"


class TestDeriveProbeUrl:
    def test_known_sources_map(self) -> None:
        assert "arbeitnow.com" in (_derive_probe_url("Arbeitnow (远程)") or "")
        assert _derive_probe_url("Unknown Source") is None


class TestRateLimitBackoff:
    @pytest.mark.asyncio
    async def test_exponential_growth_and_cap(self) -> None:
        reset_rate_limit_backoff("src-a")
        waits = []
        with patch("app.services.health_monitor.asyncio.sleep", new_callable=AsyncMock) as sleep:
            for _ in range(7):
                waits.append(await rate_limit_backoff("src-a", max_wait=60))
        assert waits == [1, 2, 4, 8, 16, 32, 60]  # 指数到 32 后下一跳 64→截断 60
        assert sleep.await_count == 7

    @pytest.mark.asyncio
    async def test_reset_restarts_sequence(self) -> None:
        reset_rate_limit_backoff("src-b")
        with patch("app.services.health_monitor.asyncio.sleep", new_callable=AsyncMock):
            assert await rate_limit_backoff("src-b") == 1
        reset_rate_limit_backoff("src-b")
        with patch("app.services.health_monitor.asyncio.sleep", new_callable=AsyncMock):
            assert await rate_limit_backoff("src-b") == 1


class TestGetHealthDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_shape_and_success_rate(self) -> None:
        def metric(status: str, records: int) -> SimpleNamespace:
            return SimpleNamespace(status=status, records_inserted=records)

        src = _source(id=uuid.uuid4())
        session = _FakeSession(
            scalars=[src],
            execute_sides=[
                SimpleNamespace(scalars=lambda: _Scalars([src])),  # sources 查询
                SimpleNamespace(scalars=lambda: _Scalars([
                    metric("success", 3), metric("success", 2), metric("failed", 0),
                ])),  # 24h metrics
            ],
        )
        out = await get_health_dashboard(session)
        assert len(out) == 1
        row = out[0]
        assert row["name"] == "Test Source"
        assert row["success_rate_24h"] == pytest.approx(2 / 3)
        assert row["records_24h"] == 5
        assert row["blocked_24h"] == 1
        assert row["calls_24h"] == 3

    @pytest.mark.asyncio
    async def test_no_metrics_yields_none_rate(self) -> None:
        src = _source(id=uuid.uuid4())
        session = _FakeSession(
            scalars=[src],
            execute_sides=[
                SimpleNamespace(scalars=lambda: _Scalars([src])),
                SimpleNamespace(scalars=lambda: _Scalars([])),
            ],
        )
        out = await get_health_dashboard(session)
        assert out[0]["success_rate_24h"] is None
        assert out[0]["calls_24h"] == 0
