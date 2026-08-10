"""Dashboard service layer — thin re-export of core dashboard aggregations.

Layer-boundary rule: api/v1 → services → core. dashboard.py / admin_data_truth.py
must not import app.core.dashboard.* directly, so this module re-exports the
shared aggregation functions (D1/D2 口径统一). Consumers keep exact signatures.
"""
from __future__ import annotations

from app.core.dashboard.dashboard_service import (  # noqa: F401 — §dashboard re-export (路由经 service 访问 core)
    get_distribution,
    get_overview,
    get_trends,
)
from app.core.dashboard.sse_broadcaster import (  # noqa: F401
    event_stream,
    get_recent_events,
)

__all__ = ["get_distribution", "get_overview", "get_trends", "event_stream", "get_recent_events"]
