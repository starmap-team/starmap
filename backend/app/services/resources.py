"""应用级数据库与外部服务连接封装。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
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
            # AsyncDriver.close 在 neo4j 6.x 是同步方法; 兼容旧版 async 语义
            close_ret = self.neo4j_driver.close()
            if hasattr(close_ret, "__await__"):
                await close_ret
            self.neo4j_driver = None
        if self.pg_engine is not None:
            await self.pg_engine.dispose()
            self.pg_engine = None
            self.pg_sessionmaker = None

    def dispose_neo4j_driver(self) -> None:
        """同步弃用当前 Neo4j driver(置 None 由 init_resources 懒重建)。

        Celery 的 run_async 每次创建新 event loop, 全局单例 driver 绑定首 loop
        后跨 loop 复用 → "Future attached to a different loop"。每次新 loop 前
        调用本方法弃旧 driver, 下次使用即在当前 loop 重建。API 层(FastAPI
        长驻 loop)的 driver 不受影响。AsyncDriver.close 是同步方法(neo4j 6.x)。
        """
        if self.neo4j_driver is not None:
            try:
                self.neo4j_driver.close()
            except Exception as exc:  # noqa: BLE001 — 弃用失败不阻断
                logger.debug("neo4j driver dispose skipped: %s", exc)
            self.neo4j_driver = None


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
        except SQLAlchemyError as exc:
            result["postgres"] = f"error:{exc.__class__.__name__}"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            logger.exception("PostgreSQL health check failed unexpectedly")
            result["postgres"] = f"error:{exc.__class__.__name__}"
    else:
        result["postgres"] = "not_initialized"

    if resources.neo4j_driver is not None:
        try:
            async with resources.neo4j_driver.session() as session:
                await session.run("RETURN 1 AS ok")
            result["neo4j"] = "ok"
        except Neo4jError as exc:
            result["neo4j"] = f"error:{exc.__class__.__name__}"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            logger.exception("Neo4j health check failed unexpectedly")
            result["neo4j"] = f"error:{exc.__class__.__name__}"
    else:
        result["neo4j"] = "not_initialized"

    if resources.redis_client is not None:
        try:
            await resources.redis_client.ping()  # type: ignore[misc]
            result["redis"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            logger.exception("Redis health check failed unexpectedly")
            result["redis"] = f"error:{exc.__class__.__name__}"
    else:
        result["redis"] = "not_initialized"

 # Ollama ping (settings.qwen_model_path 为 Ollama 基址，如 http://ollama:11434)
    ollama_url = settings.qwen_model_path
    if ollama_url:
        try:
            async with httpx.AsyncClient(timeout=settings.httpx_health_check_timeout) as client:
                resp = await client.get(f"{ollama_url}/api/tags")
            result["ollama"] = "ok" if resp.status_code == 200 else f"error:HTTP{resp.status_code}"
        except httpx.RequestError as exc:
            result["ollama"] = f"error:{exc.__class__.__name__}"
        except Exception as exc:  # pragma: no cover - defensive runtime check
            logger.exception("Ollama health check failed unexpectedly")
            result["ollama"] = f"error:{exc.__class__.__name__}"
    else:
        result["ollama"] = "not_configured"

    return result
