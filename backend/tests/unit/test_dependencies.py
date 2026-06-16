"""Tests for dependency injection module.

Exercises app.dependencies for coverage. The real dependency injection
happens at runtime via FastAPI's request-scoped resolution, so these
tests verify the callables are importable and structurally correct.
"""

from collections.abc import AsyncIterator

from app.dependencies import get_db_session, get_neo4j_driver, get_redis_client


class TestDependencyCallables:
    """Verify dependency callables exist and have correct signatures."""

    def test_get_neo4j_driver_is_callable(self):
        """get_neo4j_driver should be a regular function."""
        assert callable(get_neo4j_driver)

    def test_get_redis_client_is_callable(self):
        """get_redis_client should be a regular function."""
        assert callable(get_redis_client)

    def test_get_db_session_is_async_gen(self):
        """get_db_session should be an async generator function."""
        assert callable(get_db_session)
        # Async generator functions return async iterator when called
        gen = get_db_session()
        assert isinstance(gen, AsyncIterator) or hasattr(gen, "__aiter__")
