"""应用级数据库与外部服务连接封装。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings
from app.db.session import get_async_engine


@dataclass
class AppResources:
    """应用运行时资源句柄。"""

    pg_engine: AsyncEngine | None = None
    pg_sessionmaker: async_sessionmaker[AsyncSession] | None = None
    neo4j_driver: Any = None
    redis_client: Redis | None = None

    async def close(self) -> None:
        if self.redis_client is not None:
            await self.redis_client.aclose()
            self.redis_client = None
        if self.neo4j_driver is not None:
            await self.neo4j_driver.close()
            self.neo4j_driver = None
        if self.pg_engine is not None:
            await self.pg_engine.dispose()
            self.pg_engine = None
            self.pg_sessionmaker = None


resources = AppResources()


async def init_resources() -> AppResources:
    """初始化 PostgreSQL、Neo4j 与 Redis 客户端。"""
    if resources.pg_engine is None:
        engine = get_async_engine()
        resources.pg_engine = engine
        resources.pg_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    if resources.neo4j_driver is None:
        resources.neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    if resources.redis_client is None:
        resources.redis_client = Redis.from_url(settings.redis_uri, decode_responses=True)

    return resources


async def healthcheck_resources() -> dict[str, str]:
    """执行轻量健康检查。"""
    result: dict[str, str] = {}

    if resources.pg_engine is not None:
        try:
            async with resources.pg_engine.begin() as conn:
                await conn.exec_driver_sql("SELECT 1")
            result["postgres"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            result["postgres"] = f"error:{exc.__class__.__name__}"
    else:
        result["postgres"] = "not_initialized"

    if resources.neo4j_driver is not None:
        try:
            async with resources.neo4j_driver.session() as session:
                await session.run("RETURN 1 AS ok")
            result["neo4j"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            result["neo4j"] = f"error:{exc.__class__.__name__}"
    else:
        result["neo4j"] = "not_initialized"

    if resources.redis_client is not None:
        try:
            await resources.redis_client.ping()
            result["redis"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            result["redis"] = f"error:{exc.__class__.__name__}"
    else:
        result["redis"] = "not_initialized"

    # Ollama ping (settings.qwen_model_path 为 Ollama 基址，如 http://ollama:11434)
    ollama_url = settings.qwen_model_path
    if ollama_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{ollama_url}/api/tags")
            result["ollama"] = "ok" if resp.status_code == 200 else f"error:HTTP{resp.status_code}"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            result["ollama"] = f"error:{exc.__class__.__name__}"
    else:
        result["ollama"] = "not_configured"

    return result
