"""Unified async helper for running async coroutines from Celery workers.

Both celery_app.py and stage3_services.py had identical copies of _run_async / run_async.DEDUP-01 consolidates them here.C-W7: also dispose the shared async SQLAlchemy engine after each Celery task
to avoid "attached to a different loop" errors when the worker reuses the same engine
across multiple event loops. The next call will re-create the engine lazily.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

def run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous context (e.g. Celery worker).FIX: Always use a NEW event loop + hard-dispose the async engine
    pool before running. This ensures the SQLAlchemy connection pool is clean and
    bound to the current loop, avoiding "Task got Future attached to a different loop".

    Detects whether a running event loop exists:
    - If no loop: creates one via asyncio.run
    - If loop exists (eg inside FastAPI): uses ThreadPoolExecutor to run in separate thread
    """
 # Dispose the cached engine + session factory BEFORE starting
 # so the coroutine gets a fresh connection pool
    _dispose_engine()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
 # No loop running -> safe to use asyncio.run directly
        return asyncio.run(coro)

 # A loop IS running (likely FastAPI) — use a separate thread
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result

def _dispose_engine() -> None:
    """Dispose cached engine + session factory.

    `get_async_engine` 和 `get_session_factory` 都被 @lru_cache(maxsize=1) 缓存。
    每次 run_async 创建新 event loop 时必须清掉这两个缓存, 否则新 loop 会复用旧的
    engine (旧 engine 的连接池绑定到已关闭的 loop), 导致 "Event loop is closed"。
    """
    try:
        from app.db.session import get_async_engine, get_session_factory
 # 关键: 必须先 cache_clear get_async_engine, 再 clear session factory
 # 然后 run_async 内部 asyncio.run 创建新 loop, 新 engine 绑定到新 loop
        get_async_engine.cache_clear()
        get_session_factory.cache_clear()
    except Exception as exc:
        logger.debug("engine/factory cache clear skipped: %s", exc)
