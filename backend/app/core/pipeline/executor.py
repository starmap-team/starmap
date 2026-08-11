"""Pipeline execution service — 兼容重导出层（Phase 03 Plan 03 / D-11）。

Phase 03 拆分后的职责归属：
- 6 阶段执行函数 → ``app.core.pipeline.stages``（crawl/dedup/clean/import_/graph_sync/timeseries）
- DAG 执行引擎（advance/trigger/retry/resume/STAGE_EXECUTORS）→ ``app.core.pipeline.engine``
- 阶段辅助函数 → 各 stage 模块（spider 注册表、crawl 配置、outbox、DataSourceRecord 更新）

本文件仅做兼容重导出，存量调用方零改动（Celery / routes / crawler.bridge / tests）。
新代码请直接 import 对应模块。
"""
from __future__ import annotations

from app.core.pipeline.engine import (
    STAGE_EXECUTORS,
    advance_pipeline,
    resume_run,
    retry_stage,
    trigger_and_start,
)
from app.core.pipeline.stages.clean import execute_clean
from app.core.pipeline.stages.crawl import (
    SPIDER_REGISTRY,
    _get_crawl_configs,
    _skip_paused_sources_if_needed,
    _update_source_after_crawl,
    build_spider_registry,
    execute_crawl,
)
from app.core.pipeline.stages.dedup import _update_source_after_dedup, execute_dedup
from app.core.pipeline.stages.graph_sync import (
    _complete_outbox_record,
    _create_outbox_record,
    _fail_outbox_record,
    execute_graph_sync,
)
from app.core.pipeline.stages.import_ import _update_source_after_import, execute_import
from app.core.pipeline.stages.timeseries import execute_timeseries
from app.db.session import get_session_factory

__all__ = [
    "SPIDER_REGISTRY",
    "STAGE_EXECUTORS",
    "advance_pipeline",
    "build_spider_registry",
    "execute_clean",
    "execute_crawl",
    "execute_dedup",
    "execute_graph_sync",
    "execute_import",
    "execute_timeseries",
    "get_session_factory",
    "resume_run",
    "retry_stage",
    "trigger_and_start",
    # 私有辅助（tests / stage 模块仍按 executor 路径引用）
    "_complete_outbox_record",
    "_create_outbox_record",
    "_fail_outbox_record",
    "_get_crawl_configs",
    "_skip_paused_sources_if_needed",
    "_update_source_after_crawl",
    "_update_source_after_dedup",
    "_update_source_after_import",
]
