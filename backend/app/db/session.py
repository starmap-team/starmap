"""Shared async SQLAlchemy engine and session factory.

Phase 6 D-04..D-07: every `create_async_engine(settings.postgres_uri, pool_pre_ping=True)`
call site in production backend code is consolidated here. The engine itself is created
on first use and reused (lazy lru_cache) so Celery workers and the FastAPI process can both
talk to PostgreSQL without paying for a new engine per call.

Why a thin module instead of wiring each call site individually:
- One place to tune pool sizing, pre-ping, connection arguments
- One place to switch driver (e.g. asyncpg ↔ psycopg) during a migration
- Cross-process reuse means Celery worker boot can skip its own engine creation

If pool sizing or connection args ever need to vary by caller, prefer adding a kwarg to
get_async_engine() rather than re-introducing inline `create_async_engine` call sites.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide async SQLAlchemy engine. First call creates it.

    AP-06: Explicit pool sizing to match typical uvicorn worker counts.
    - pool_size=10: baseline connections kept open
    - max_overflow=20: allow burst up to 30 total connections
    - pool_recycle=3600: recycle connections hourly to avoid stale sockets
    """
    return create_async_engine(
        settings.postgres_uri or "",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a sessionmaker bound to the shared engine."""
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async DB session that auto-commits on success and auto-rolls back on exception.

    This is the recommended way to obtain a session for any code path (FastAPI routes,
    Celery tasks, pipeline executor, etc.). It ensures every call site either commits
    or rolls back explicitly, preventing silently-lost writes or dangling transactions.

    Usage::

        async with get_db_session() as session:
            result = await session.execute(...)
            # session.commit() is called automatically on clean exit
            # session.rollback() is called automatically on exception
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
