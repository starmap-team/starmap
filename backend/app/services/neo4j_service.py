"""Neo4j connection service with async context manager."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from neo4j import AsyncGraphDatabase, AsyncManagedTransaction, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from app.config import settings


@asynccontextmanager
async def get_neo4j_driver() -> AsyncIterator[AsyncSession]:
    """Async context manager providing a Neo4j session.

    Yields:
        An open AsyncSession that auto-closes on exit.

    Raises:
        ServiceUnavailable: If Neo4j is unreachable.
    """
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        async with driver.session(database="neo4j") as session:
            logger.debug("Neo4j session opened")
            yield session
    finally:
        await driver.close()
        logger.debug("Neo4j driver closed")


async def health_check(max_retries: int = 2) -> dict[str, object]:
    """Perform a Neo4j connectivity health check.

    Args:
        max_retries: Number of retry attempts.

    Returns:
        dict with keys: status, version, error (if any).
    """
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
    """Execute a read-write transaction on Neo4j.

    Args:
        query: Cypher query string.
        parameters: Query parameters.

    Returns:
        List of record dicts.
    """
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
    """Execute a read-only query on Neo4j.

    Args:
        query: Cypher query string.
        parameters: Query parameters.

    Returns:
        List of record dicts.
    """
    async with get_neo4j_driver() as session:
        result = await session.run(query, parameters or {})
        records = await result.data()
        return records
