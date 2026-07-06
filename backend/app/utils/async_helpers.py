"""Unified async helper for running async coroutines from Celery workers.

Both celery_app.py and stage3_services.py had identical copies of _run_async / run_async.
Phase 6 DEDUP-01 consolidates them here.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous context (e.g. Celery worker).

    Detects whether a running event loop exists:
      - No loop → use asyncio.run()
      - Existing loop → submit to a single-worker ThreadPoolExecutor
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()
