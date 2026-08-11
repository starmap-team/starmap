"""Pipeline timeseries 阶段（D-01 + D-18）。

聚合技能频率时间序列，供演化分析使用。本模块从 executor.execute_timeseries 迁出；
executor.py 保留兼容重导出，存量调用方零改动（D-11）。
"""
from __future__ import annotations

from typing import Any

from app.core.pipeline.stages.common import (
    PipelineStageError,
    get_session_factory,
    logger,
    run_async,
)


def execute_timeseries(run_id: str) -> dict[str, Any]:
    """执行 timeseries 阶段：聚合技能频率时间序列。"""
    processed = 0
    errors: list[str] = []

    try:
        result = run_async(_run_timeseries_refresh())
        processed = result.get("windows_created", 0)
        skills_updated = result.get("skills_updated", 0)
        logger.info(
            "Timeseries stage: {} skills updated, {} windows created",
            skills_updated,
            processed,
        )
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"timeseries failed: {exc}")
        logger.opt(exception=True).error("Timeseries stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors}


async def _run_timeseries_refresh() -> dict[str, Any]:
    """Async bridge for execute_timeseries to call refresh_skill_timeseries."""
    from app.services.timeseries_service import refresh_skill_timeseries

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            return await refresh_skill_timeseries(session)


__all__ = ["execute_timeseries"]
