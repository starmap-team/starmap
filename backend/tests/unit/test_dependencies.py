"""Tests for dependency injection module.

Exercises app.dependencies for coverage. The real dependency injection
happens at runtime via FastAPI's request-scoped resolution, so these
tests verify the callables are importable and structurally correct.
"""

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.dependencies import (
    get_current_user,
    get_current_user_sse,
    get_db_session,
    get_neo4j_driver,
    get_redis_client,
    sse_connect,
    sse_disconnect,
)


class TestDependencyCallables:
    """Verify dependency callables exist and have correct signatures."""

    def test_get_neo4j_driver_is_callable(self):
        """get_neo4j_driver should be a regular function."""
        assert callable(get_neo4j_driver)

    def test_get_redis_client_is_callable(self):
        """get_redis_client should be a callable."""
        assert callable(get_redis_client)

    def test_get_db_session_is_async_gen(self):
        """get_db_session should be an async generator function."""
        assert callable(get_db_session)
        # Async generator functions return async iterator when called
        gen = get_db_session()
        assert isinstance(gen, AsyncIterator) or hasattr(gen, "__aiter__")


# ═══════════════════════════════════════════════════════════════════════
# W1-T2 regression coverage (PLAN §W1-T2): dev anon-admin opt-in.
# The legacy behaviour "missing token in dev = role=admin" was a real
# residual risk once prod guards were dormant. After this fix the
# default dev user is role=viewer; opt-in is via DEV_ANON_ADMIN=true.
# ═══════════════════════════════════════════════════════════════════════


def _run(coro):
    """Helper: run an async coroutine in a sync test.

    Uses asyncio.run() instead of get_event_loop().run_until_complete()
    to avoid issues with pytest-asyncio's event loop management in
    Python 3.12+ (where get_event_loop() may return a closed loop).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # If there's already a running loop (e.g. inside pytest-asyncio),
        # we can't use asyncio.run() — create a new loop instead.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _mock_request() -> MagicMock:
    """Create a mock Request with a client.host for P0-F2 SSE auth."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


async def _noop_sse_check_for_limit_tests(client_ip: str) -> None:
    """No-op SSE check — used by TestSSEConnectionLimit to restore real sse_connect
    after the global conftest bypasses it."""
    pass


@pytest.fixture
def restore_dev_anon_admin():
    """Snapshot+restore dev_anon_admin so tests can't leak across."""
    original = settings.dev_anon_admin
    yield
    settings.dev_anon_admin = original


class TestDevAnonAdminOptIn:
    """Dev-mode anonymous admin must be opt-in, not default."""

    def test_default_dev_returns_viewer_not_admin(
        self, restore_dev_anon_admin
    ):
        """dev_anon_admin=False (default): missing token → role=viewer.

        Before W1-T2 this returned role=admin, which was a real residual
        risk — every admin endpoint was effectively public in default dev.
        """
        settings.dev_anon_admin = False
        user = _run(get_current_user(credentials=None))
        assert user["role"] == "viewer"
        assert user["sub"] == "dev"

    def test_opt_in_dev_returns_admin(self, restore_dev_anon_admin):
        """dev_anon_admin=True (opt-in): missing token → role=admin.

        This is the legacy convenience path kept for local debugging.
        CI / shared dev envs MUST leave this False.
        """
        settings.dev_anon_admin = True
        user = _run(get_current_user(credentials=None))
        assert user["role"] == "admin"
        assert user["sub"] == "dev"

    def test_dev_token_role_matches_opt_in(self, restore_dev_anon_admin):
        """`dev-token` shortcut honours dev_anon_admin like the no-token path."""
        # Default (False) → viewer
        settings.dev_anon_admin = False
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token")
        user = _run(get_current_user(credentials=creds))
        assert user["role"] == "viewer"

        # Opt-in (True) → admin
        settings.dev_anon_admin = True
        user = _run(get_current_user(credentials=creds))
        assert user["role"] == "admin"

    def test_sse_dev_token_role_matches_opt_in(self, restore_dev_anon_admin):
        """SSE auth path honours dev_anon_admin consistently."""
        settings.dev_anon_admin = False
        user = _run(get_current_user_sse(request=_mock_request(), token="dev-token"))
        assert user["role"] == "viewer"

        settings.dev_anon_admin = True
        user = _run(get_current_user_sse(request=_mock_request(), token="dev-token"))
        assert user["role"] == "admin"

    def test_prod_missing_token_always_401(self, monkeypatch):
        """Production must reject any request without a valid Bearer token.

        This is the same contract as before but is now pinned by a test
        so dev_anon_admin=true in a misconfigured .env.production is
        caught by config.py's startup assertion (not at request time).
        """
        # Temporarily pretend we're in production without touching settings.app_env
        monkeypatch.setattr(settings, "app_env", "production")
        with pytest.raises(HTTPException) as exc:
            _run(get_current_user(credentials=None))
        assert exc.value.status_code == 401


class TestSSETokenExpired:
    """P0-F2: SSE auth returns X-Token-Expired header on expired JWT."""

    def test_sse_expired_token_includes_header(self, monkeypatch):
        """When SSE query-param token is expired, 401 includes X-Token-Expired."""
        monkeypatch.setattr(settings, "app_env", "production")
        # Create a token that will fail with "expired" in the error message
        # by using an invalid token string that triggers the expired path

        # We need a real expired JWT to trigger the "expired" error path
        import time as _time

        import jwt as pyjwt

        expired_payload = {
            "sub": "testuser",
            "role": "admin",
            "username": "testuser",
            "uid": "00000000-0000-0000-0000-000000000000",
            "type": "access",
            "exp": _time.time() - 3600,  # expired 1 hour ago
            "iat": _time.time() - 7200,
            "nbf": _time.time() - 7200,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        expired_token = pyjwt.encode(expired_payload, settings.secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc:
            _run(get_current_user_sse(request=_mock_request(), token=expired_token))
        assert exc.value.status_code == 401
        # P0-F2: X-Token-Expired header signals frontend to silent-refresh
        assert exc.value.headers is not None
        assert exc.value.headers.get("X-Token-Expired") == "true"

    def test_sse_invalid_token_no_expired_header(self, monkeypatch):
        """When SSE token is invalid (not expired), 401 omits X-Token-Expired."""
        monkeypatch.setattr(settings, "app_env", "production")
        with pytest.raises(HTTPException) as exc:
            _run(get_current_user_sse(request=_mock_request(), token="not-a-jwt"))
        assert exc.value.status_code == 401
        # Invalid (not expired) token should NOT have X-Token-Expired
        assert exc.value.headers is None or exc.value.headers.get("X-Token-Expired") is None


class TestSSEConnectionLimit:
    """API-05: SSE per-IP and global connection limits.

    These tests exercise sse_connect/sse_disconnect directly (not via
    get_current_user_sse) to avoid the _sse_connect_check bypass.
    """

    @pytest.fixture(autouse=True)
    def _reset_sse_counters(self):
        """Reset SSE connection counters before and after each test."""
        import app.dependencies as dep_mod
        dep_mod._sse_global_connections = 0
        dep_mod._sse_ip_connections.clear()
        yield
        dep_mod._sse_global_connections = 0
        dep_mod._sse_ip_connections.clear()

    def test_sse_connect_increments_counters(self):
        """sse_connect should increment per-IP and global counters."""
        import app.dependencies as dep_mod
        _run(sse_connect("10.0.0.1"))
        assert dep_mod._sse_global_connections == 1
        assert dep_mod._sse_ip_connections["10.0.0.1"] == 1

    def test_sse_disconnect_decrements_counters(self):
        """sse_disconnect should decrement per-IP and global counters."""
        import app.dependencies as dep_mod
        dep_mod._sse_global_connections = 1
        dep_mod._sse_ip_connections["10.0.0.1"] = 1
        _run(sse_disconnect("10.0.0.1"))
        assert dep_mod._sse_global_connections == 0
        assert dep_mod._sse_ip_connections["10.0.0.1"] == 0

    def test_per_ip_limit_rejects_excess(self):
        """When per-IP limit is reached, sse_connect raises 429."""
        import app.dependencies as dep_mod
        # Fill up to the per-IP limit
        for _ in range(dep_mod._SSE_MAX_PER_IP):
            _run(sse_connect("10.0.0.1"))
        # Next connection from same IP should be rejected
        with pytest.raises(HTTPException) as exc:
            _run(sse_connect("10.0.0.1"))
        assert exc.value.status_code == 429

    def test_global_limit_rejects_excess(self):
        """When global limit is reached, sse_connect raises 429 even for new IPs."""
        import app.dependencies as dep_mod
        dep_mod._sse_global_connections = dep_mod._SSE_MAX_GLOBAL
        dep_mod._sse_ip_connections.clear()
        with pytest.raises(HTTPException) as exc:
            _run(sse_connect("new-ip"))
        assert exc.value.status_code == 429
