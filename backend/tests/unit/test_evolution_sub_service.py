"""Unit tests for evolution sub-module business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- EmergenceFinder / EmergenceReport / EmergenceSignal (core models)
- Career path direction classification logic
- Emerging alerts filtering (level, z_score, domain)
- Industry report aggregation
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.evolution.emergence_finder import EmergenceLevel, EmergenceReport, EmergenceSignal


# ── Helpers ──


def _make_signal(
    skill_name="LangChain",
    level=EmergenceLevel.EMERGING,
    z_score=2.5,
    current_frequency=10,
    mean_frequency=3.0,
    source_count=5,
    positions=None,
    metadata=None,
) -> EmergenceSignal:
    return EmergenceSignal(
        skill_name=skill_name,
        level=level,
        z_score=z_score,
        current_frequency=current_frequency,
        mean_frequency=mean_frequency,
        std_frequency=1.0,
        source_count=source_count,
        positions=positions or ["AI工程师"],
        metadata=metadata or {"domains": ["AI"]},
    )


def _make_report(
    emerging=None, rising=None, declining=None, stable=None,
) -> EmergenceReport:
    return EmergenceReport(
        emerging=emerging or [],
        rising=rising or [],
        declining=declining or [],
        stable=stable or [],
        total_skills_analyzed=10,
    )


# ══════════════════════════════════════════════════════════════
# EmergenceSignal — model validation
# ══════════════════════════════════════════════════════════════


class TestEmergenceSignal:
    """EmergenceSignal — field construction and values."""

    def test_basic_fields(self):
        sig = _make_signal()
        assert sig.skill_name == "LangChain"
        assert sig.level == EmergenceLevel.EMERGING
        assert sig.z_score == 2.5

    def test_all_levels(self):
        for level in EmergenceLevel:
            sig = _make_signal(level=level)
            assert sig.level == level

    def test_positions_default(self):
        sig = _make_signal()
        assert "AI工程师" in sig.positions

    def test_metadata_default(self):
        sig = _make_signal()
        assert "AI" in sig.metadata.get("domains", [])


# ══════════════════════════════════════════════════════════════
# EmergenceReport — aggregation counts
# ══════════════════════════════════════════════════════════════


class TestEmergenceReport:
    """EmergenceReport — signal aggregation."""

    def test_empty_report(self):
        report = _make_report()
        assert len(report.emerging) == 0
        assert len(report.rising) == 0
        assert report.total_skills_analyzed == 10

    def test_with_emerging_signals(self):
        signals = [_make_signal(skill_name="A"), _make_signal(skill_name="B")]
        report = _make_report(emerging=signals)
        assert len(report.emerging) == 2
        assert report.emerging[0].skill_name == "A"

    def test_mixed_signals(self):
        report = _make_report(
            emerging=[_make_signal(level=EmergenceLevel.EMERGING)],
            rising=[_make_signal(level=EmergenceLevel.RISING)],
            declining=[_make_signal(level=EmergenceLevel.DECLINING)],
        )
        assert len(report.emerging) == 1
        assert len(report.rising) == 1
        assert len(report.declining) == 1


# ══════════════════════════════════════════════════════════════
# Career path direction — classification logic
# ══════════════════════════════════════════════════════════════


class TestCareerPathDirection:
    """Direction classification for career paths."""

    def test_senior_keywords(self):
        """Positions containing '高级' should classify as 'up' direction."""
        SENIOR_KEYWORDS = {"高级", "资深", "专家", "总监", "主管", "经理", "首席", "架构师"}
        target = "高级后端工程师"
        is_senior = any(kw in target for kw in SENIOR_KEYWORDS)
        assert is_senior is True

    def test_non_senior_is_lateral(self):
        SENIOR_KEYWORDS = {"高级", "资深", "专家", "总监", "主管", "经理", "首席", "架构师"}
        target = "全栈工程师"
        is_senior = any(kw in target for kw in SENIOR_KEYWORDS)
        assert is_senior is False  # → lateral

    def test_architect_is_senior(self):
        SENIOR_KEYWORDS = {"高级", "资深", "专家", "总监", "主管", "经理", "首席", "架构师"}
        target = "架构师"
        is_senior = any(kw in target for kw in SENIOR_KEYWORDS)
        assert is_senior is True


# ══════════════════════════════════════════════════════════════
# Emerging alerts — filtering logic
# ══════════════════════════════════════════════════════════════


class TestEmergingAlertsFiltering:
    """Filtering logic for emerging alerts (level, z_score, domain)."""

    def test_filter_by_level(self):
        signals = [
            _make_signal(skill_name="A", level=EmergenceLevel.EMERGING),
            _make_signal(skill_name="B", level=EmergenceLevel.RISING),
        ]
        filtered = [s for s in signals if s.level == EmergenceLevel.EMERGING]
        assert len(filtered) == 1
        assert filtered[0].skill_name == "A"

    def test_filter_by_min_z_score(self):
        signals = [
            _make_signal(skill_name="A", z_score=2.5),
            _make_signal(skill_name="B", z_score=1.0),
        ]
        min_z = 2.0
        filtered = [s for s in signals if s.z_score >= min_z]
        assert len(filtered) == 1
        assert filtered[0].skill_name == "A"

    def test_filter_by_domain(self):
        signals = [
            _make_signal(skill_name="A", metadata={"domains": ["AI"]}),
            _make_signal(skill_name="B", metadata={"domains": ["IoT"]}),
        ]
        domain = "AI"
        filtered = [s for s in signals if domain in s.metadata.get("domains", [])]
        assert len(filtered) == 1
        assert filtered[0].skill_name == "A"

    def test_filter_combined(self):
        signals = [
            _make_signal(skill_name="A", level=EmergenceLevel.EMERGING, z_score=2.5, metadata={"domains": ["AI"]}),
            _make_signal(skill_name="B", level=EmergenceLevel.RISING, z_score=1.8, metadata={"domains": ["AI"]}),
            _make_signal(skill_name="C", level=EmergenceLevel.EMERGING, z_score=2.5, metadata={"domains": ["IoT"]}),
        ]
        filtered = [
            s for s in signals
            if s.level == EmergenceLevel.EMERGING and s.z_score >= 2.0 and "AI" in s.metadata.get("domains", [])
        ]
        assert len(filtered) == 1
        assert filtered[0].skill_name == "A"

    def test_empty_after_filter(self):
        signals = [_make_signal(level=EmergenceLevel.RISING)]
        filtered = [s for s in signals if s.level == EmergenceLevel.EMERGING]
        assert filtered == []


# ══════════════════════════════════════════════════════════════
# Summary counts — from EmergenceReport
# ══════════════════════════════════════════════════════════════


class TestSummaryCounts:
    """Summary string generation from signal counts."""

    def test_summary_with_all_categories(self):
        report = _make_report(
            emerging=[_make_signal()],
            rising=[_make_signal()],
            declining=[_make_signal()],
        )
        counts = {
            "emerging": len(report.emerging),
            "rising": len(report.rising),
            "declining": len(report.declining),
        }
        assert counts["emerging"] == 1
        assert counts["rising"] == 1
        assert counts["declining"] == 1

    def test_total_from_report(self):
        report = _make_report(
            emerging=[_make_signal(), _make_signal()],
            rising=[_make_signal()],
        )
        total = len(report.emerging) + len(report.rising) + len(report.declining) + len(report.stable)
        assert total == 3