"""Coverage boost: services/admin_ab_service.py — A/B 聚合纯逻辑 (PLAN-013 收尾)。"""

from __future__ import annotations

import pytest

from app.services.admin_ab_service import aggregate_ab_results


class TestAggregateAbResultsEmpty:
    def test_empty_list_returns_zero(self) -> None:
        out = aggregate_ab_results([])
        assert out == {"total": 0, "versions": {}}


class TestAggregateAbResultsSingle:
    def test_one_version_three_samples(self) -> None:
        """成功率/F1/延迟平均; 4 位 / 1 位精度."""
        out = aggregate_ab_results([
            {"version": "v1", "success": True, "f1": 0.9, "latency_ms": 100},
            {"version": "v1", "success": False, "f1": 0.7, "latency_ms": 200},
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 150},
        ])
        assert out["total"] == 3
        v1 = out["versions"]["v1"]
        assert v1["count"] == 3
        assert v1["success_rate"] == round(2 / 3, 4)
        assert v1["avg_f1"] == round(0.8, 4)  # (0.9+0.7+0.8)/3
        assert v1["avg_latency_ms"] == round(150.0, 1)


class TestAggregateAbResultsMultiple:
    def test_split_per_version(self) -> None:
        out = aggregate_ab_results([
            {"version": "v1", "success": True},
            {"version": "v2", "success": False},
            {"version": "v2", "success": False},
        ])
        assert out["total"] == 3
        assert out["versions"]["v1"]["count"] == 1
        assert out["versions"]["v1"]["success_rate"] == 1.0
        assert out["versions"]["v2"]["count"] == 2
        assert out["versions"]["v2"]["success_rate"] == 0.0

    def test_optional_metrics_only_aggregated_when_present(self) -> None:
        """avg_f1/avg_latency_ms 在从没提供时为 None, 不是 0.0."""
        out = aggregate_ab_results([
            {"version": "v1", "success": True},
            {"version": "v1", "success": True, "f1": 0.5},
        ])
        v1 = out["versions"]["v1"]
        assert v1["avg_f1"] == round(0.5, 4)
        assert v1["avg_latency_ms"] is None  # 都没提供

    def test_explicit_none_treated_as_missing(self) -> None:
        """r.get('f1') is not None 才统计; 显式 None 等于缺失."""
        out = aggregate_ab_results([
            {"version": "v1", "success": True, "f1": None, "latency_ms": None},
        ])
        assert out["versions"]["v1"]["avg_f1"] is None
        assert out["versions"]["v1"]["avg_latency_ms"] is None


class TestAggregateAbResultsPrecision:
    @pytest.mark.parametrize("p,expected", [
        (1.0, 1.0),
        (0.0, 0.0),
        (0.12345, 0.1235),  # 4 位四舍五入
        (0.99999, 1.0),
    ])
    def test_f1_rounded_to_4_decimals(self, p: float, expected: float) -> None:
        out = aggregate_ab_results([{"version": "v", "success": True, "f1": p}])
        assert out["versions"]["v"]["avg_f1"] == expected
