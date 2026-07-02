"""Tests for resources healthcheck."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.resources import healthcheck_resources, resources


@pytest.mark.asyncio
async def test_healthcheck_not_initialized():
    """When resources are not initialized, all should show 'not_initialized'."""
    result = await healthcheck_resources()
    assert result["postgres"] == "not_initialized"
    assert result["neo4j"] == "not_initialized"
    assert result["redis"] == "not_initialized"


@pytest.mark.asyncio
async def test_healthcheck_pg_ok():
    """When pg_engine is available and works, it should show ok."""
    conn = AsyncMock()
    conn.exec_driver_sql = AsyncMock()

    # SQLAlchemy's engine.begin() returns an AsyncConnection which is an async context manager
    resources.pg_engine = MagicMock()
    resources.pg_engine.begin = MagicMock(return_value=conn)

    # Set other resources to None so they don't interfere
    resources.neo4j_driver = None
    resources.redis_client = None

    result = await healthcheck_resources()
    assert result["postgres"] == "ok"

    # Clean up
    resources.pg_engine = None
    resources.neo4j_driver = None
    resources.redis_client = None
