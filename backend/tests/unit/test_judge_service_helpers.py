"""Tests for judge service helper functions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.judge_service import (
    ExtractionMetrics,
    SampleEvaluation,
    _build_judge_prompt,
    _check_quality_gate,
    _load_jsonl,
    _normalize_skill,
    _safe_resolve_jsonl_path,
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

    def test_removes_non_alphanumeric_except_hash_dot_plus(self):
        result = _normalize_skill("C++ (Expert)")
        # regex [^a-z0-9+#.] keeps +, #, . but removes spaces and parens
        assert result == "c++expert"

    def test_uses_alias_normalization_when_available(self):
        with patch("app.services.judge_service._HAS_NORMALIZE", True), \
             patch("app.services.judge_service.normalize_by_alias", return_value="react.js"):
            result = _normalize_skill("ReactJS")
            assert result == "react.js"

    def test_alias_normalization_returns_none_falls_back_to_regex(self):
        with patch("app.services.judge_service._HAS_NORMALIZE", True), \
             patch("app.services.judge_service.normalize_by_alias", return_value=None):
            result = _normalize_skill("Python 3.x")
            assert result == "python3.x"


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

    def test_dict_missing_name_key(self):
        items = [{"skill": "Python"}, {"name": "SQL"}]
        assert _skill_names(items) == ["", "SQL"]


class TestExtractionMetrics:
    def test_default_creation(self):
        metrics = ExtractionMetrics(avg_f1=0.85)
        assert metrics.avg_f1 == 0.85
        assert metrics.total_samples == 0
        assert metrics.evaluated_samples == 0

    def test_f1_distribution_default(self):
        metrics = ExtractionMetrics()
        assert metrics.f1_distribution == {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

    def test_per_sample_default(self):
        metrics = ExtractionMetrics()
        assert metrics.per_sample == []


class TestSampleEvaluation:
    def test_default_creation(self):
        sample = SampleEvaluation()
        assert sample.f1 == 0.0
        assert sample.llm_reasoning is None

    def test_with_values(self):
        sample = SampleEvaluation(
            sample_id="s1",
            precision=0.95,
            recall=0.80,
            f1=0.87,
            llm_score=0.90,
            llm_reasoning="good match",
            errors=["missing field"],
        )
        assert sample.sample_id == "s1"
        assert sample.precision == 0.95
        assert sample.llm_reasoning == "good match"
        assert sample.errors == ["missing field"]


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

    def test_returns_rounded_f1_and_threshold(self):
        metrics = ExtractionMetrics(avg_f1=0.66666)
        result = _check_quality_gate(metrics, threshold=0.5)
        assert result["avg_f1"] == 0.6667
        assert result["threshold"] == 0.5


class TestSafeResolveJsonlPath:
    def test_accepts_path_in_eval_data_dir(self, tmp_path):
        allowed = tmp_path / "evaluation"
        allowed.mkdir()
        target = allowed / "test.jsonl"
        target.touch()
        with patch("app.services.judge_service._EVAL_DATA_DIR", allowed):
            result = _safe_resolve_jsonl_path(str(target))
        assert str(result) == str(target.resolve())

    def test_rejects_path_outside_allowed_dirs(self, tmp_path):
        outside = tmp_path / "outside.jsonl"
        outside.touch()
        with patch("app.services.judge_service._EVAL_DATA_DIR", tmp_path / "safe"), \
             patch("app.services.judge_service.settings.app_env", "production"):
            with pytest.raises(ValueError, match="File path must be within allowed directories"):
                _safe_resolve_jsonl_path(str(outside))

    def test_accepts_path_in_temp_dir_for_non_production(self, tmp_path):
        target = tmp_path / "test.jsonl"
        target.touch()
        with patch("app.services.judge_service._EVAL_DATA_DIR", Path("/safe")), \
             patch("app.services.judge_service.settings.app_env", "development"):
            result = _safe_resolve_jsonl_path(str(target))
        assert str(result) == str(target.resolve())

    def test_rejects_path_in_temp_dir_for_production(self, tmp_path):
        target = tmp_path / "test.jsonl"
        target.touch()
        with patch("app.services.judge_service._EVAL_DATA_DIR", Path("C:/safe")), \
             patch("app.services.judge_service.settings.app_env", "production"):
            with pytest.raises(ValueError, match="File path must be within allowed directories"):
                _safe_resolve_jsonl_path(str(target))


class TestLoadJsonl:
    def test_returns_empty_list_for_nonexistent_file(self, tmp_path):
        result = _load_jsonl(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_reads_valid_jsonl(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text(
            '{"id":"a","skills":["Python"]}\n'
            '{"id":"b","skills":["SQL"]}\n',
            encoding="utf-8",
        )
        result = _load_jsonl(f)
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_skips_empty_lines(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text('{"id":"a"}\n\n{"id":"b"}\n', encoding="utf-8")
        result = _load_jsonl(f)
        assert len(result) == 2

    def test_skips_invalid_json_lines(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text('{"id":"a"}\nnot json\n{"id":"b"}\n', encoding="utf-8")
        result = _load_jsonl(f)
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_returns_empty_for_all_invalid(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text("not json\nstill not\n", encoding="utf-8")
        result = _load_jsonl(f)
        assert result == []

    def test_delegates_to_safe_resolve(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text('{"id":"a"}\n', encoding="utf-8")
        with patch("app.services.judge_service._safe_resolve_jsonl_path") as mock_resolve:
            mock_resolve.return_value = f
            _load_jsonl(str(f))
        mock_resolve.assert_called_once_with(str(f))


class TestBuildJudgePrompt:
    def test_constructs_prompt_with_default_version(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch("app.services.judge_service.get_prompt") as mock_get:
            mock_get.return_value = "filled prompt"
            result = _build_judge_prompt(golden, system)
        assert result == "filled prompt"
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert "golden_json" in kwargs
        assert "system_json" in kwargs

    def test_constructs_prompt_with_specific_version(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch("app.services.judge_service.get_prompt_version") as mock_get_ver:
            mock_get_ver.return_value = "versioned prompt"
            result = _build_judge_prompt(golden, system, version="v2")
        assert result == "versioned prompt"
        mock_get_ver.assert_called_once()
        args, kwargs = mock_get_ver.call_args
        assert args[0] == "llm_judge"
        assert args[1] == "v2"
        assert "golden_json" in kwargs
        assert "system_json" in kwargs

    def test_falls_back_when_version_not_found(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch("app.services.judge_service.get_prompt_version", side_effect=KeyError("v2")), \
             patch("app.services.judge_service.get_prompt") as mock_get:
            mock_get.return_value = "fallback prompt"
            result = _build_judge_prompt(golden, system, version="v2")
        assert result == "fallback prompt"

    def test_includes_golden_and_system_json(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Go"}]}
        with patch("app.services.judge_service.get_prompt") as mock_get:
            mock_get.return_value = "prompt"
            _build_judge_prompt(golden, system)
        _, kwargs = mock_get.call_args
        assert "Python" in kwargs["golden_json"]
        assert "Go" in kwargs["system_json"]
