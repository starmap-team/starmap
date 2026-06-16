"""依赖注入。"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.resources import resources


def get_neo4j_driver(request: Request):
    return request.app.state.resources.neo4j_driver


def get_redis_client(request: Request) -> Redis:
    return request.app.state.resources.redis_client


async def get_db_session() -> AsyncIterator[AsyncSession]:
    if resources.pg_sessionmaker is None:
        raise RuntimeError("PostgreSQL sessionmaker not initialized")
    async with resources.pg_sessionmaker() as session:
        yield session
