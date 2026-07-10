"""PIPE-03 (b): CLI 触发 pipeline 的薄包装。

调用方: crawler/run.py 中的 run-pipeline 子命令.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 让脚本独立运行（与 crawler/run.py 一致）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log = logging.getLogger(__name__)


async def _trigger_async(source: str, limit: int) -> dict:
    """直接调后端 executor.trigger_and_start;不通过 HTTP(CLI 与后端同进程内)。"""
    from app.core.pipeline.executor import trigger_and_start
    from app.core.pipeline.status_aggregator import invalidate_status_cache

    run_type = f"cli-{source}"
    run = await trigger_and_start(run_type=run_type, selected_stages=None)
    log.info("Pipeline run triggered: id=%s, type=%s, status=%s", run.id, run_type, run.status)
    # 失效 status 缓存以让 /api/v1/pipeline/status 立刻看到新 run
    try:
        from app.services.resources import resources as app_resources
        await invalidate_status_cache(app_resources.redis_client)
    except Exception:  # noqa: BLE001
        # 失效失败不应该阻断 trigger;CLI 主流程已成功
        pass
    return {
        "run_id": str(run.id),
        "status": run.status,
        "source": source,
        "limit": limit,
    }


def trigger_pipeline_run(source: str = "boss", limit: int = 20) -> int:
    """同步入口给 argparse 调用。返回 0/1 作为子命令退出码。"""
    logging.basicConfig(level=logging.INFO)
    try:
        result = asyncio.run(_trigger_async(source, limit))
        print(f"Pipeline run triggered: {result}")
        return 0
    except Exception:  # noqa: BLE001
        log.exception("Pipeline trigger failed")
        return 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CLI 触发一次完整 pipeline run")
    p.add_argument("--source", default="boss", choices=["boss", "lagou", "51job"])
    p.add_argument("--limit", type=int, default=20)
    a = p.parse_args()
    sys.exit(trigger_pipeline_run(a.source, a.limit))
