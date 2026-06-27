"""Dependency injection."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.resources import resources


def get_neo4j_driver(request: Request):
    res = getattr(request.app.state, "resources", None)
    if res is None:
        return None
    return res.neo4j_driver


def get_redis_client(request: Request) -> Redis:
    res = getattr(request.app.state, "resources", None)
    if res is None:
        return None
    return res.redis_client


async def get_db_session() -> AsyncIterator[AsyncSession]:
    if resources.pg_sessionmaker is None:
        raise RuntimeError("PostgreSQL sessionmaker not initialized")
    async with resources.pg_sessionmaker() as session:
        yield session