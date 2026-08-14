"""CONCERN 1.8 (security audit 2026-08-15): audit sink failure must not
break the 429 response.

`RateLimitMiddleware` (app/main.py) calls `audit_log(...)` after a
rate-limit decision. If that sink raises — Redis went down between the
INCR and the audit call, loguru serializer blows up on an unexpected
field, etc — the user must still see a 429 and NOT a 500. The audit
event is best-effort; the rate-limit decision is not.

These tests pin BOTH paths (Redis-backed and in-memory fallback) by
monkeypatching `audit_log` to raise and asserting the 429 still returns.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _low_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tighten rate_limit_max so 1-2 requests trigger 429 deterministically."""
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_max", 2)
    monkeypatch.setattr(settings, "rate_limit_window", 60)


def _make_audit_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace app.main.audit_log with a sink that always raises."""
    import app.main as main_mod

    def boom(_entry: object) -> None:
        raise ConnectionError("simulated audit sink failure")

    monkeypatch.setattr(main_mod, "audit_log", boom)


class TestAuditSinkFailureRedisPath:
    """Redis branch (app/main.py:223): audit sink raising must not break 429."""

    def test_audit_raising_returns_429_in_redis_path(
        self, monkeypatch: pytest.MonkeyPatch, _low_rate_limit: None
    ) -> None:
        from app.main import _rate_buckets, app

        # Redis client whose eval succeeds (so we stay in Redis branch) but
        # the audit sink raises — this is the original CONCERN 1.8 scenario.
        class FakeRedis:
            async def eval(self, *args: Any, **kwargs: Any) -> int:
                return 99  # > rate_limit_max → 429 path

        class FakeResources:
            redis_client = FakeRedis()

        _make_audit_raising(monkeypatch)

        with TestClient(app) as client:
            # Replace resources AFTER lifespan startup (FakeResources has no
            # real DB/Neo4j, so init_resources() would explode).
            monkeypatch.setattr(app.state, "resources", FakeResources())

            resp = client.get("/api/v1/__rl_probe__")
            assert resp.status_code == 429
            # CONCERN 1.8: NOT a 500 — the rate-limit decision still wins.
            assert resp.status_code != 500
            assert "Retry-After" in resp.headers

        # In-memory bucket should NOT have been populated (we stayed on the
        # Redis path the whole way).
        assert _rate_buckets == {}


class TestAuditSinkFailureInMemoryPath:
    """In-memory branch (app/main.py:280): audit sink raising must not break 429."""

    def test_audit_raising_returns_429_in_memory_path(
        self, monkeypatch: pytest.MonkeyPatch, _low_rate_limit: None
    ) -> None:
        from app.main import _rate_buckets, app

        # No Redis client → in-memory fallback path is the only one that fires.
        class FakeResources:
            redis_client = None

        _make_audit_raising(monkeypatch)

        # Pre-fill the bucket using TestClient's reported client.host. To
        # avoid guessing the host string, we send 3 requests without raising
        # audit_log so the bucket naturally fills; the third one crosses
        # the limit (rate_limit_max=2) and exercises the audit-raise path.
        _rate_buckets.clear()

        def _no_audit(_entry: object) -> None:
            return None

        import app.main as main_mod

        monkeypatch.setattr(main_mod, "audit_log", _no_audit)

        with TestClient(app) as client:
            monkeypatch.setattr(app.state, "resources", FakeResources())

            for _ in range(2):
                resp = client.get("/api/v1/__rl_probe__")
                assert resp.status_code in (404, 429), (
                    f"warm-up response unexpected: {resp.status_code}"
                )

            # Now switch audit_log to raise and fire one more request:
            # it must still hit 429.
            _make_audit_raising(monkeypatch)
            resp = client.get("/api/v1/__rl_probe__")
            assert resp.status_code == 429, (
                f"audit-raise path must still enforce 429, got {resp.status_code}; "
                f"body={resp.text!r}"
            )
            assert resp.status_code != 500
            assert "Retry-After" in resp.headers

        _rate_buckets.clear()


class TestAuditLogSinkStillCalled:
    """Sanity: under normal operation, audit_log IS invoked (we didn't break it)."""

    def test_audit_log_invoked_on_redis_path_429(
        self, monkeypatch: pytest.MonkeyPatch, _low_rate_limit: None
    ) -> None:
        from app.main import app

        class FakeRedis:
            async def eval(self, *args: Any, **kwargs: Any) -> int:
                return 99

        class FakeResources:
            redis_client = FakeRedis()

        calls: list[object] = []

        def spy(_entry: object) -> None:
            calls.append(_entry)

        import app.main as main_mod

        monkeypatch.setattr(main_mod, "audit_log", spy)

        with TestClient(app) as client:
            monkeypatch.setattr(app.state, "resources", FakeResources())

            resp = client.get("/api/v1/__rl_probe__")
            assert resp.status_code == 429
            assert len(calls) == 1
