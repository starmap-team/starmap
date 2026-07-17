"""Unit tests for dependency injection business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- Dependency callable signatures and types
- get_db_session: async generator behavior
- get_neo4j_driver / get_redis_client: request-based extraction
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dependencies import get_db_session, get_neo4j_driver, get_redis_client

# ══════════════════════════════════════════════════════════════
# Dependency callable signatures
# ══════════════════════════════════════════════════════════════


class TestDependencyCallables:
    """Verify dependency callables exist and have correct signatures."""

    def test_get_neo4j_driver_is_callable(self):
        assert callable(get_neo4j_driver)

    def test_get_redis_client_is_callable(self):
        assert callable(get_redis_client)

    def test_get_db_session_is_callable(self):
        assert callable(get_db_session)

    def test_get_db_session_is_async_gen(self):
        gen = get_db_session()
        assert isinstance(gen, AsyncIterator) or hasattr(gen, "__aiter__")


# ══════════════════════════════════════════════════════════════
# get_neo4j_driver — request-based extraction
# ══════════════════════════════════════════════════════════════


class TestGetNeo4jDriver:
    """get_neo4j_driver(request) — extracts driver from app.state.resources."""

    def test_returns_driver_when_resources_exist(self):
        fake_driver = MagicMock()
        fake_resources = MagicMock(neo4j_driver=fake_driver)
        request = MagicMock()
        request.app.state.resources = fake_resources

        fake_resources

        result = get_neo4j_driver(request)
        assert result is fake_driver

    def test_returns_none_when_no_resources(self):
        request = MagicMock()
        request.app.state.resources = None

        result = get_neo4j_driver(request)
        assert result is None

    def test_returns_none_when_no_state_attr(self):
        """If app.state has no 'resources' attr, getattr returns None."""
        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # state has no 'resources'
        result = get_neo4j_driver(request)
        assert result is None


# ══════════════════════════════════════════════════════════════
# get_redis_client — request-based extraction
# ══════════════════════════════════════════════════════════════


class TestGetRedisClient:
    """get_redis_client(request) — extracts Redis from app.state.resources."""

    def test_returns_client_when_resources_exist(self):
        fake_redis = MagicMock()
        fake_resources = MagicMock(redis_client=fake_redis)
        request = MagicMock()
        request.app.state.resources = fake_resources

        result = get_redis_client(request)
        assert result is fake_redis

    def test_returns_none_when_no_resources(self):
        request = MagicMock()
        request.app.state.resources = None

        result = get_redis_client(request)
        assert result is None


# ══════════════════════════════════════════════════════════════
# get_db_session — async generator behavior
# ══════════════════════════════════════════════════════════════


class TestGetDbSession:
    """get_db_session() — async generator with auto-commit/rollback."""

    async def test_auto_rollback_on_exception(self):
        """When an exception occurs in the caller, session.rollback() is invoked."""
        from app.db.session import get_db_session as _get_db_session

        with patch("app.db.session.get_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError):
                async with _get_db_session() as session:
                    raise ValueError("test error")
            mock_session.rollback.assert_awaited_once()
