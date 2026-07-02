"""Neo4j connection service — reuses the application-level singleton driver."""

from __future__ import annotations

from typing import Any

from loguru import logger
from neo4j import AsyncManagedTransaction, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from app.services.resources import resources


class _SessionCM:
    """Async context manager that yields an AsyncSession from the singleton."""

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        if resources.neo4j_driver is None:
            raise RuntimeError("Neo4j driver not initialised")
        self._session = resources.neo4j_driver.session(database="neo4j")
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


def get_neo4j_driver() -> _SessionCM:
    """Backward-compatible context manager — yields an AsyncSession.

    Previously this created a brand-new driver per call; now it reuses the
    application singleton from ``resources.py``.
    """
    return _SessionCM()


async def health_check(max_retries: int = 2) -> dict[str, object]:
    """Perform a Neo4j connectivity health check."""
    errors: list[str] = []
    for attempt in range(1, max_retries + 1):
        try:
            async with get_neo4j_driver() as session:
                result = await session.run("RETURN 1 AS ok")
                record = await result.single()
                if record and record.get("ok") == 1:
                    server_info = await session.run("CALL dbms.components() YIELD versions")
                    comp = await server_info.single()
                    version = comp.get("versions", ["unknown"])[0] if comp else "unknown"
                    logger.info("Neo4j health check passed (version={})", version)
                    return {"status": "ok", "version": version}
        except ServiceUnavailable as e:
            msg = f"Attempt {attempt}/{max_retries}: {e}"
            logger.warning(msg)
            errors.append(msg)
        except Exception as e:
            msg = f"Neo4j health check error: {e}"
            logger.error(msg)
            errors.append(msg)

    logger.error("Neo4j health check failed after {} attempts", max_retries)
    return {"status": "error", "errors": errors}


async def execute_transaction(
    query: str,
    parameters: dict | None = None,
) -> list[dict]:
    """Execute a read-write transaction on Neo4j."""
    async with get_neo4j_driver() as session:
        async def _tx(tx: AsyncManagedTransaction) -> list[dict]:
            result = await tx.run(query, parameters or {})
            records = await result.data()
            return records
        return await session.execute_write(_tx)


async def execute_query(
    query: str,
    parameters: dict | None = None,
) -> list[dict]:
    """Execute a read-only query on Neo4j."""
    async with get_neo4j_driver() as session:
        result = await session.run(query, parameters or {})
        records = await result.data()
        return records
