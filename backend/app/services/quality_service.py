"""Quality service layer — thin re-export of shared quality KPIs.

Layer-boundary rule: api/v1 → services → core. quality.py must not import
app.core.metrics directly, so this module re-exports the shared metric
functions (D1+D2 fix). Consumers outside services keep their exact signatures.
"""
from __future__ import annotations

from app.core.metrics import (  # noqa: F401 — §metrics re-export (路由经 service 访问 core)
    avg_skill_trust,
    weekly_new_nodes,
)

__all__ = ["avg_skill_trust", "weekly_new_nodes"]
