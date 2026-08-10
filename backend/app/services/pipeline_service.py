"""Pipeline service layer — re-exports for pipeline/executor orchestration.

Layer-boundary rule: api/v1 → services → core. Route files must not import
app.core.pipeline.* directly; they consume the re-exports here (or via
pipeline_service submodules) so the dependency direction stays api → services → core.

5b 计划: pipeline/routes.py 的 SSE 编排将整体迁入本服务。
"""
from __future__ import annotations

from app.core.pipeline.executor import (  # noqa: F401 — §pipeline re-export (路由经 service 访问 core)
    build_spider_registry,
    trigger_and_start,
)

__all__ = ["build_spider_registry", "trigger_and_start"]
