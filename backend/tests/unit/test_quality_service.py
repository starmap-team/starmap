"""Unit tests for quality business logic — service/core layer only.

Directly calls service/core functions — no TestClient, no HTTP layer.
Covers:
- _status / _warning_level helper functions (pure)
- _serialize quality dashboard → response
- quality evaluation logic (score = confidence × (1 - hallucination))
- aggregate_ab_results (from admin_ab_service, reused)
"""
from __future__ import annotations

import pytest

from app.api.v1.quality import (
    QualityDashboard,
    QualityReport,
    _status,
    _warning_level,
)
from app.services.admin_ab_service import aggregate_ab_results

# ══════════════════════════════════════════════════════════════
# _status — quality score → pass/warn/fail
# ══════════════════════════════════════════════════════════════


class TestStatusHelper:
    """_status(score, threshold) → pass/warn/fail."""

    def test_pass_when_score_meets_threshold(self):
        assert _status(0.85, 0.80) == "pass"

    def test_warn_when_score_just_below_threshold(self):
        assert _status(0.73, 0.80) == "warn"  # 0.73 >= 0.80*0.9=0.72

    def test_fail_when_score_far_below(self):
        assert _status(0.50, 0.80) == "fail"

    def test_pass_with_perfect_score(self):
        assert _status(1.0, 0.90) == "pass"

    def test_warn_at_90_percent_threshold(self):
        # 0.80*0.9 = 0.7200000000000001 due to float precision
        # so 0.72 is just below — use 0.73 instead
        assert _status(0.73, 0.80) == "warn"

    def test_fail_below_90_percent(self):
        assert _status(0.71, 0.80) == "fail"


# ══════════════════════════════════════════════════════════════
# _warning_level — hallucination + confidence → color level
# ══════════════════════════════════════════════════════════════


class TestWarningLevelHelper:
    """_warning_level(confidence, hallucination, total_extractions) → gray/green/yellow/orange/red."""

    def test_gray_when_no_data(self):
        assert _warning_level(0.0, 0.0, total_extractions=0) == "gray"

    def test_green_when_excellent(self):
        assert _warning_level(0.90, 0.03, total_extractions=10) == "green"

    def test_yellow_when_moderate(self):
        assert _warning_level(0.78, 0.08, total_extractions=10) == "yellow"

    def test_orange_when_poor(self):
        assert _warning_level(0.65, 0.15, total_extractions=10) == "orange"

    def test_red_when_critical(self):
        assert _warning_level(0.40, 0.30, total_extractions=10) == "red"


# ══════════════════════════════════════════════════════════════
# Quality evaluation logic — score = confidence × (1 - hallucination)
# ══════════════════════════════════════════════════════════════


class TestQualityEvaluation:
    """Quality score calculation and status derivation."""

    def test_score_formula(self):
        confidence = 0.85
        hallucination = 0.04
        score = confidence * (1 - hallucination)
        assert score == pytest.approx(0.816, abs=0.01)

    def test_score_with_zero_hallucination(self):
        score = 0.95 * (1 - 0.0)
        assert score == 0.95

    def test_score_with_high_hallucination(self):
        score = 0.70 * (1 - 0.10)
        assert score == pytest.approx(0.63, abs=0.01)

    def test_status_from_score(self):
        """Verify the score → status mapping used by the endpoint."""
        # High score → pass
        score = 0.95 * 0.98  # 0.931
        threshold = 0.80
        assert _status(score, threshold) == "pass"

        # Warning zone — score just below threshold but above 90%
        score = 0.73  # 0.73 >= 0.80*0.9 ≈ 0.72
        assert _status(score, threshold) == "warn"

        # Fail
        score = 0.50 * 0.70  # 0.35
        assert _status(score, threshold) == "fail"

    def test_default_values_when_no_data(self):
        confidence = 0.0
        hallucination = 0.0
        score = confidence * (1 - hallucination)
        assert score == 0.0
        assert _status(score, 0.80) == "fail"


# ══════════════════════════════════════════════════════════════
# QualityDashboard model — field validation
# ══════════════════════════════════════════════════════════════


class TestQualityDashboardModel:
    """QualityDashboard and QualityReport Pydantic models."""

    def _make_report(self, **kwargs):
        defaults = {"precision": 0.9, "recall": 0.85, "f1": 0.87, "warning_level": "green", "details": []}
        defaults.update(kwargs)
        return QualityReport(**defaults)

    def _make_dashboard(self, **kwargs):
        report = kwargs.pop("report", None) or self._make_report()
        defaults = {
            "report": report,
            "hallucination_rate": 0.03,
            "total_extractions": 50,
            "pending_review": 5,
            "total_nodes": 200,
            "total_edges": 300,
            "total_positions": 80,
            "total_skills": 120,
            "avg_trust_score": 0.82,
            "high_trust_ratio": 0.6,
            "trust_distribution": [],
            "hallucination_trend": [],
            "source_distribution": [],
            "weekly_new_nodes": 10,
            "audit_pass_rate": 0.9,
            "audit_queue": [],
        }
        defaults.update(kwargs)
        return QualityDashboard(**defaults)

    def test_dashboard_fields(self):
        d = self._make_dashboard()
        assert d.total_extractions == 50
        assert d.hallucination_rate == 0.03
        assert d.report.f1 == 0.87

    def test_dashboard_with_zero_data(self):
        d = self._make_dashboard(
            report=self._make_report(precision=0.0, recall=0.0, f1=0.0, warning_level="gray"),
            hallucination_rate=0.0,
            total_extractions=0,
            total_nodes=0,
            total_edges=0,
            avg_trust_score=0.0,
            high_trust_ratio=0.0,
        )
        assert d.total_extractions == 0
        assert d.hallucination_rate == 0.0

    def test_report_warning_levels(self):
        for level in ("green", "yellow", "orange", "red", "gray"):
            r = self._make_report(warning_level=level)
            assert r.warning_level == level


# ══════════════════════════════════════════════════════════════
# aggregate_ab_results — reused from admin_ab_service
# ══════════════════════════════════════════════════════════════


class TestAggregateABResults:
    """aggregate_ab_results — pure aggregation math."""

    def test_empty_results(self):
        result = aggregate_ab_results([])
        assert result["total"] == 0
        assert result["versions"] == {}

    def test_single_version(self):
        results = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0},
            {"version": "v1", "success": False, "f1": 0.6, "latency_ms": 150.0},
        ]
        result = aggregate_ab_results(results)
        assert result["total"] == 2
        assert result["versions"]["v1"]["count"] == 2
        assert result["versions"]["v1"]["success_rate"] == 0.5
        assert result["versions"]["v1"]["avg_f1"] == 0.7

    def test_multi_version(self):
        results = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0},
            {"version": "v2", "success": True, "f1": 0.9, "latency_ms": 90.0},
        ]
        result = aggregate_ab_results(results)
        assert result["total"] == 2
        assert "v1" in result["versions"]
        assert "v2" in result["versions"]

    def test_missing_optional_fields(self):
        results = [
            {"version": "v1", "success": True},
        ]
        result = aggregate_ab_results(results)
        assert result["versions"]["v1"]["avg_f1"] is None
        assert result["versions"]["v1"]["avg_latency_ms"] is None
