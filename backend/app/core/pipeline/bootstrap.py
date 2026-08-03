"""PIPE-03 (c): celery-worker 启动一次性 bootstrap。

检测 PIPELINE_BOOTSTRAP=true → 延迟 30s 后入队一次完整 pipeline run。
仅一次性（不循环）。在 worker 进程内同步触发 executor.trigger_and_start。
"""
from __future__ import annotations

import asyncio
import os
import threading

from loguru import logger

BOOTSTRAP_DELAY_SECONDS = 30


def schedule_bootstrap_if_enabled() -> None:
    """Celery worker 启动时调用 — 仅在 PIPELINE_BOOTSTRAP=true 时入队一次。

    使用 threading.Timer 而非 asyncio，避免在 worker 主循环阻塞 30 秒。
    错误吞掉并 logger.exception（不影响 worker 启动）。
    """
    flag = os.getenv("PIPELINE_BOOTSTRAP", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return

    logger.info(
        "PIPELINE_BOOTSTRAP={}; will enqueue a single pipeline run in {}s",
        flag, BOOTSTRAP_DELAY_SECONDS,
    )

    def _fire() -> None:
        try:
            from app.core.pipeline.executor import trigger_and_start
            run = asyncio.run(
                trigger_and_start(run_type="bootstrap", selected_stages=None)
            )
            logger.info(
                "Bootstrap pipeline run dispatched (id={}, status={})",
                run.id, run.status,
            )
        except Exception:
            logger.exception("Bootstrap pipeline trigger failed")

    t = threading.Timer(BOOTSTRAP_DELAY_SECONDS, _fire)
    t.daemon = True
    t.start()


__all__ = ["schedule_bootstrap_if_enabled", "BOOTSTRAP_DELAY_SECONDS"]
