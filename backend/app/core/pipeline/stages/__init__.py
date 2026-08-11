"""Pipeline 阶段模块聚合入口（D-01）。

各阶段执行函数从 executor.py 迁出至此；executor.py 仍为兼容重导出层（D-11）。
所有 6 阶段均已迁出（Tasks 1-6）。
"""
from __future__ import annotations

from typing import Any


def execute_timeseries(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Timeseries 阶段 — 已迁出（Task 1）。"""
    from app.core.pipeline.stages.timeseries import execute_timeseries as _impl

    return _impl(run_id)


def execute_dedup(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Dedup 阶段 — 已迁出（Task 2）。"""
    from app.core.pipeline.stages.dedup import execute_dedup as _impl

    return _impl(run_id)


def execute_clean(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Clean 阶段 — 已迁出（Task 3）。"""
    from app.core.pipeline.stages.clean import execute_clean as _impl

    return _impl(run_id)


def execute_crawl(run_id: str, run_type: str) -> dict[str, Any]:  # noqa: D401
    """Crawl 阶段 — 已迁出（Task 4）。"""
    from app.core.pipeline.stages.crawl import execute_crawl as _impl

    return _impl(run_id, run_type)


def execute_import(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Import 阶段 — 已迁出（Task 5）。"""
    from app.core.pipeline.stages.import_ import execute_import as _impl

    return _impl(run_id)


def execute_graph_sync(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Graph_sync 阶段 — 已迁出（Task 6）。"""
    from app.core.pipeline.stages.graph_sync import execute_graph_sync as _impl

    return _impl(run_id)


__all__ = [
    "execute_clean",
    "execute_crawl",
    "execute_dedup",
    "execute_graph_sync",
    "execute_import",
    "execute_timeseries",
]
