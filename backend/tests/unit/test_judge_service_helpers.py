"""Tests for judge service helper functions."""
from __future__ import annotations

from app.services.judge_service import (
    ExtractionMetrics,
    SampleEvaluation,
    _check_quality_gate,
    _normalize_skill,
    _skill_names,
)


class TestNormalizeSkill:
    def test_empty_string(self):
        assert _normalize_skill("") == ""
        assert _normalize_skill(None) == ""

    def test_returns_lowercase(self):
        result = _normalize_skill("Python")
        assert result == "python"

    def test_strips_whitespace(self):
        result = _normalize_skill("  SQL  ")
        assert result == "sql"


class TestSkillNames:
    def test_empty_list(self):
        assert _skill_names([]) == []

    def test_none_list(self):
        assert _skill_names(None) == []

    def test_dict_items(self):
        items = [{"name": "Python"}, {"name": "SQL"}]
        assert _skill_names(items) == ["Python", "SQL"]

    def test_string_items(self):
        items = ["Python", "SQL"]
        assert _skill_names(items) == ["Python", "SQL"]

    def test_mixed_items(self):
        items = [{"name": "Python"}, "SQL"]
        result = _skill_names(items)
        assert "Python" in result
        assert "SQL" in result


class TestExtractionMetrics:
    def test_default_creation(self):
        metrics = ExtractionMetrics(avg_f1=0.85)
        assert metrics.avg_f1 == 0.85
        assert metrics.total_samples == 0
        assert metrics.evaluated_samples == 0


class TestSampleEvaluation:
    def test_default_creation(self):
        sample = SampleEvaluation()
        assert sample.f1 == 0.0
        assert sample.llm_reasoning is None


class TestCheckQualityGate:
    def test_passes_when_above_threshold(self):
        metrics = ExtractionMetrics(avg_f1=0.85)
        result = _check_quality_gate(metrics, threshold=0.7)
        assert result["passed"] is True
        assert result["status"] == "green"

    def test_fails_when_below_threshold(self):
        metrics = ExtractionMetrics(avg_f1=0.5)
        result = _check_quality_gate(metrics, threshold=0.7)
        assert result["passed"] is False
        assert result["status"] == "red"

    def test_exact_threshold(self):
        metrics = ExtractionMetrics(avg_f1=0.7)
        result = _check_quality_gate(metrics, threshold=0.7)
        assert result["passed"] is True
