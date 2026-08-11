"""Pipeline 阶段模块聚合入口（D-01）。

各阶段执行函数从 executor.py 迁出至此；executor.py 仍为兼容重导出层（D-11）。
后续 Task 2-6 将逐个迁出 crawl/dedup/clean/import/graph_sync 阶段。
"""
from __future__ import annotations

from typing import Any


def execute_timeseries(run_id: str) -> dict[str, Any]:  # noqa: D401
    """Timeseries 阶段 — 已迁出。"""
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


# 尚未迁出的阶段占位（保持模块 surface 一致，避免 import 顺序问题）
def _not_migrated(stage_name: str):  # noqa: D401
    def _stub(run_id: str) -> dict[str, Any]:  # noqa: ARG001
        raise NotImplementedError(
            f"Stage '{stage_name}' not yet migrated from executor.py "
            f"(see Phase 03 Plan 03 Tasks 2-6)"
        )

    return _stub


execute_crawl = _not_migrated("crawl")
execute_import = _not_migrated("import")
execute_graph_sync = _not_migrated("graph_sync")


__all__ = [
    "execute_clean",
    "execute_crawl",
    "execute_dedup",
    "execute_graph_sync",
    "execute_import",
    "execute_timeseries",
]
