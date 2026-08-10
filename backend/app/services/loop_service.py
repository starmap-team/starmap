"""Loop service layer — thin re-export of the closed-loop orchestrator.

Layer-boundary rule: api/v1 → services → core. loop.py must not import
app.core.pipeline.loop_orchestrator directly.
"""
from __future__ import annotations

from app.core.pipeline.loop_orchestrator import (  # noqa: F401 — §loop re-export (路由经 service 访问 core)
    LoopOrchestrator,
    get_loop_history,
    get_loop_status,
)

__all__ = ["LoopOrchestrator", "get_loop_history", "get_loop_status"]
