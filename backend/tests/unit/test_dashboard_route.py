"""Coverage boost: api/v1/dashboard.py — 路由层组装 (PLAN-013)。

直测 handler（mock service 层），验证:
- overview: 未知字段过滤（仅保留 OverviewResponse 声明字段）
- trends: TrendPoint 组装
- distribution: 三分布 + timestamp
- realtime-poll: 默认 since 窗口 + 自定义 since
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.dashboard import (
    OverviewResponse,
    dashboard_distribution,
    dashboard_overview,
    dashboard_realtime_poll,
    dashboard_trends,
)


class TestDashboardOverview:
    @pytest.mark.asyncio
    async def test_filters_unknown_fields_from_service(self) -> None:
        """契约防御：service 返回多余字段不得进入响应模型。"""
        with patch(
            "app.api.v1.dashboard.get_overview",
            new=AsyncMock(return_value={
                "total_nodes": 100, "total_edges": 50, "total_positions": 20,
                "total_skills": 80, "total_domains": 5, "trust_score": 0.8,
                "hallucination_rate": 0.1, "total_extractions": 300,
                "data_volume": 999, "today_extractions": 3, "pipeline_status": "running",
                "active_data_sources": 4, "weekly_new_nodes": 7, "stale": True,
                "stale_since": 1.0, "timestamp": 2.0,
                "unknown_future_field": "should be dropped",
            }),
        ):
            out = await dashboard_overview(session=None, neo4j_driver=None, redis=None)  # type: ignore[arg-type]
        assert isinstance(out, OverviewResponse)
        assert out.total_nodes == 100
        assert out.pipeline_status == "running"
        assert not hasattr(out, "unknown_future_field")

    @pytest.mark.asyncio
    async def test_missing_keys_default_to_zero(self) -> None:
        with patch("app.api.v1.dashboard.get_overview", new=AsyncMock(return_value={})):
            out = await dashboard_overview(session=None, neo4j_driver=None, redis=None)  # type: ignore[arg-type]
        assert out.total_nodes == 0
        assert out.stale is False
        assert out.timestamp == 0.0


class TestDashboardTrends:
    @pytest.mark.asyncio
    async def test_builds_trend_points(self) -> None:
        with patch(
            "app.api.v1.dashboard.get_trends",
            new=AsyncMock(return_value={
                "period": "30d",
                "data_points": [
                    {"date": "2026-07-01", "total_records": 10, "new_records": 2,
                     "quality_score": 0.9, "extractions": 5},
                ],
                "summary": {"avg_quality": 0.8},
            }),
        ):
            out = await dashboard_trends(session=None, redis=None, period="30d")  # type: ignore[arg-type]
        assert out.period == "30d"
        assert out.data_points[0].date == "2026-07-01"
        assert out.data_points[0].total_records == 10
        assert out.summary == {"avg_quality": 0.8}


class TestDashboardDistribution:
    @pytest.mark.asyncio
    async def test_passes_three_distributions(self) -> None:
        with patch(
            "app.api.v1.dashboard.get_distribution",
            new=AsyncMock(return_value={
                "source_distribution": [{"name": "boss", "count": 3}],
                "domain_distribution": [{"name": "IT", "count": 2}],
                "skill_category_distribution": [{"name": "hard", "count": 5}],
                "timestamp": 123.0,
            }),
        ):
            out = await dashboard_distribution(session=None, redis=None)  # type: ignore[arg-type]
        assert out.source_distribution == [{"name": "boss", "count": 3}]
        assert out.timestamp == 123.0


class TestDashboardRealtimePoll:
    @pytest.mark.asyncio
    async def test_default_since_window(self) -> None:
        with patch(
            "app.api.v1.dashboard.get_recent_events",
            new=AsyncMock(return_value=[{"type": "pipeline_update"}]),
        ) as get_events, patch("app.api.v1.dashboard.time.time", return_value=1000.0):
            out = await dashboard_realtime_poll(redis=None, _user={}, since=None)  # type: ignore[arg-type]
        assert out.poll_interval_ms == 5000
        assert out.events == [{"type": "pipeline_update"}]
        assert get_events.await_args.kwargs["since"] == pytest.approx(995.0)  # now - 5s

    @pytest.mark.asyncio
    async def test_custom_since_forwarded(self) -> None:
        with patch(
            "app.api.v1.dashboard.get_recent_events",
            new=AsyncMock(return_value=[]),
        ) as get_events:
            out = await dashboard_realtime_poll(redis=None, _user={}, since=42.0)  # type: ignore[arg-type]
        assert out.events == []
        assert get_events.await_args.kwargs["since"] == 42.0
