"""Smoke tests for resume_eval module — basic functionality verification.

Covers:
- GoldenSample dataclass and properties
- F1Metrics dataclass and to_dict
- EvaluationResult dataclass and to_dict
- _normalize_skill_name normalization
- _skill_matches fuzzy matching
- evaluate_f1 basic functionality
- evaluate_single basic functionality
- build_golden_set with missing file
"""
from __future__ import annotations

from app.core.extraction.resume_eval import (
    EvaluationResult,
    F1Metrics,
    GoldenSample,
    _normalize_skill_name,
    _skill_matches,
    build_golden_set,
    evaluate_f1,
    evaluate_single,
)


class TestGoldenSample:
    """Tests for GoldenSample dataclass."""

    def test_expected_skill_names_property(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[{"name": "Python"}, {"name": "Docker"}],
            position="DevOps",
        )
        assert sample.expected_skill_names == {"python", "docker"}

    def test_expected_skill_names_strips_whitespace(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[{"name": "  Python  "}, {"name": "  Docker  "}],
            position="DevOps",
        )
        assert sample.expected_skill_names == {"python", "docker"}

    def test_expected_skill_names_ignores_empty(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[{"name": "Python"}, {"name": ""}, {"name": None}],
            position="DevOps",
        )
        assert sample.expected_skill_names == {"python"}

    def test_expected_skill_names_empty_list(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[],
            position="DevOps",
        )
        assert sample.expected_skill_names == set()

    def test_sample_id_default(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[],
            position="DevOps",
        )
        assert sample.sample_id == ""


class TestF1Metrics:
    """Tests for F1Metrics dataclass."""

    def test_to_dict(self):
        metrics = F1Metrics(precision=0.8, recall=0.6, f1=0.6857, true_positives=4)
        result = metrics.to_dict()
        assert result["precision"] == 0.8
        assert result["recall"] == 0.6
        assert result["f1"] == 0.6857
        assert result["true_positives"] == 4

    def test_defaults(self):
        metrics = F1Metrics()
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        assert metrics.true_positives == 0


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_to_dict(self):
        result = EvaluationResult(total_samples=5, avg_precision=0.9, avg_recall=0.8, avg_f1=0.85)
        d = result.to_dict()
        assert d["total_samples"] == 5
        assert d["avg_precision"] == 0.9
        assert d["avg_f1"] == 0.85

    def test_defaults(self):
        result = EvaluationResult()
        assert result.total_samples == 0
        assert result.per_sample == []
        assert result.summary == {}


class TestNormalizeSkillName:
    """Tests for _normalize_skill_name."""

    def test_lowercase(self):
        assert _normalize_skill_name("Python") == "python"

    def test_strip_whitespace(self):
        assert _normalize_skill_name("  Python  ") == "python"

    def test_already_normalized(self):
        assert _normalize_skill_name("python") == "python"

    def test_mixed_case(self):
        assert _normalize_skill_name("PyThOn") == "python"


class TestSkillMatches:
    """Tests for _skill_matches fuzzy matching."""

    def test_exact_match(self):
        assert _skill_matches("python", {"python", "docker"}) is True

    def test_no_match(self):
        assert _skill_matches("cobol", {"python", "docker"}) is False

    def test_substring_match(self):
        """Substring containment matching."""
        assert _skill_matches("react", {"react.js", "vue"}) is True

    def test_reverse_substring_match(self):
        """Expected contained in predicted."""
        assert _skill_matches("react.js", {"react", "vue"}) is True

    def test_empty_expected(self):
        assert _skill_matches("python", set()) is False


class TestBuildGoldenSet:
    """Tests for build_golden_set."""

    def test_missing_file_returns_empty(self):
        result = build_golden_set(path="/nonexistent/path/golden_set.json")
        assert result == []


class TestEvaluateF1:
    """Tests for evaluate_f1 basic functionality."""

    def test_basic_evaluation(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[{"name": "Python"}, {"name": "Docker"}],
            position="DevOps",
            sample_id="s1",
        )
        predictions = [{"python", "docker"}]
        result = evaluate_f1(predictions, [sample])

        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert result["total_samples"] == 1

    def test_mismatched_count_raises(self):
        sample = GoldenSample(
            resume_text="text",
            expected_skills=[],
            position="DevOps",
        )
        with __import__("pytest").raises(ValueError, match="Prediction count"):
            evaluate_f1([], [sample])  # 0 preds, 1 sample


class TestEvaluateSingle:
    """Tests for evaluate_single."""

    def test_basic_single_evaluation(self):
        predicted = ["Python", "Docker"]
        expected = [{"name": "Python", "proficiency": "advanced"}]
        result = evaluate_single(predicted, expected)

        assert "precision" in result
        assert "recall" in result
        assert "f1" in result

    def test_dict_predicted_skills(self):
        predicted = [{"name": "Python", "category": "hard_skill"}]
        expected = [{"name": "Python", "proficiency": "advanced"}]
        result = evaluate_single(predicted, expected)

        assert result["precision"] > 0
