"""Comprehensive tests for judge service async API.

Covers: evaluate_sample_async, evaluate_pair_async, evaluate_batch_async,
and the internal _call_llm_judge_async helper.

All LLM calls are mocked at the call_llm_with_fallback boundary.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.extraction.llm_client import LLMResponseError
from app.services.judge_service import (
    _call_llm_judge_async,
    evaluate_batch_async,
    evaluate_pair_async,
    evaluate_sample_async,
)

# ──────────────────────────────────────────────
# evaluate_sample_async
# ──────────────────────────────────────────────


class TestEvaluateSampleAsync:
    """Core single-sample evaluation."""

    async def test_perfect_overlap(self):
        golden = {
            "id": "g1",
            "required_skills": [{"name": "Python"}, {"name": "SQL"}],
            "bonus_skills": [{"name": "Docker"}],
        }
        system = {
            "id": "s1",
            "required_skills": [{"name": "Python"}, {"name": "SQL"}],
            "bonus_skills": [{"name": "Docker"}],
        }
        result = await evaluate_sample_async(golden, system)
        assert result.sample_id == "g1"
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(1.0)
        assert result.f1 == pytest.approx(1.0)
        assert result.errors == []

    async def test_no_overlap(self):
        golden = {
            "id": "g1",
            "required_skills": [{"name": "Python"}],
            "bonus_skills": [],
        }
        system = {
            "id": "s1",
            "required_skills": [{"name": "Rust"}],
            "bonus_skills": [],
        }
        result = await evaluate_sample_async(golden, system)
        assert result.precision == pytest.approx(0.0)
        assert result.recall == pytest.approx(0.0)
        assert result.f1 == pytest.approx(0.0)

    async def test_partial_overlap(self):
        golden = {
            "id": "g2",
            "required_skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Docker"}],
            "bonus_skills": [],
        }
        system = {
            "id": "s2",
            "required_skills": [{"name": "Python"}, {"name": "Kubernetes"}],
            "bonus_skills": [],
        }
        result = await evaluate_sample_async(golden, system)
        assert 0.0 < result.precision < 1.0
        assert 0.0 < result.recall < 1.0
        assert 0.0 < result.f1 < 1.0

    async def test_both_empty_required_skills(self):
        golden = {"id": "g1", "required_skills": [], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.f1 == pytest.approx(0.0)
        assert result.precision == pytest.approx(0.0)
        assert result.recall == pytest.approx(0.0)

    async def test_golden_empty_but_system_has_skills(self):
        golden = {"id": "g1", "required_skills": [], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.f1 == pytest.approx(0.0)
        assert result.precision == pytest.approx(0.0)

    async def test_system_empty_but_golden_has_skills(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.f1 == pytest.approx(0.0)

    async def test_missing_required_skills_field_error(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        system = {"id": "s1", "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert "missing required_skills field" in result.errors

    async def test_missing_bonus_skills_field_error(self):
        golden = {"id": "g1", "required_skills": [], "bonus_skills": [{"name": "Docker"}]}
        system = {"id": "s1", "required_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert "missing bonus_skills field" in result.errors

    async def test_uses_llm_judge_when_requested(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"f1_score": 0.95, "details": "good"}'}),
        ), patch("app.services.judge_service.parse_llm_json_response", return_value={"f1_score": 0.95, "details": "good"}):
            result = await evaluate_sample_async(golden, system, use_llm_judge=True)
        assert result.llm_score == pytest.approx(0.95)
        assert result.llm_reasoning == "good"

    async def test_llm_judge_with_specific_version(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"f1_score": 0.9, "details": "ok"}'}),
        ), patch("app.services.judge_service.parse_llm_json_response", return_value={"f1_score": 0.9, "details": "ok"}):
            result = await evaluate_sample_async(golden, system, use_llm_judge=True, judge_version="v2")
        assert result.llm_score == pytest.approx(0.9)

    async def test_llm_judge_parse_failure_returns_none(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": "invalid json"}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            side_effect=LLMResponseError("parse error"),
        ):
            result = await evaluate_sample_async(golden, system, use_llm_judge=True)
        assert result.llm_score is None
        assert result.llm_reasoning is not None
        assert "Failed to parse" in (result.llm_reasoning or "")

    async def test_string_skills_format(self):
        golden = {"id": "g1", "required_skills": ["Python", "SQL"], "bonus_skills": []}
        system = {"id": "s1", "required_skills": ["Python", "Go"], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.f1 == pytest.approx(0.5)
        assert result.precision == pytest.approx(0.5)
        assert result.recall == pytest.approx(0.5)

    async def test_mixed_skills_format(self):
        golden = {"id": "g1", "required_skills": [{"name": "Python"}, "SQL"], "bonus_skills": []}
        system = {"id": "s1", "required_skills": [{"name": "Python"}, "Go"], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.sample_id == "g1"

    async def test_uses_golden_id_when_system_id_missing(self):
        golden = {"id": "golden-only", "required_skills": [], "bonus_skills": []}
        system = {"required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.sample_id == "golden-only"

    async def test_uses_system_id_when_golden_id_missing(self):
        golden = {"required_skills": [], "bonus_skills": []}
        system = {"id": "system-only", "required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.sample_id == "system-only"

    async def test_fallback_id_when_both_missing(self):
        golden = {"required_skills": [], "bonus_skills": []}
        system = {"required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        assert result.sample_id == "unknown"

    async def test_bonus_skills_only(self):
        golden = {"id": "g1", "required_skills": [], "bonus_skills": [{"name": "Docker"}, {"name": "K8s"}]}
        system = {"id": "s1", "required_skills": [], "bonus_skills": [{"name": "Docker"}]}
        result = await evaluate_sample_async(golden, system)
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(0.5)
        # f1 = 2*1*0.5/(1+0.5) = 1/1.5 = 0.666..., rounded to 4 decimals = 0.6667
        assert result.f1 == pytest.approx(0.6667, abs=1e-4)

    async def test_weighted_required_and_bonus(self):
        golden = {
            "id": "g1",
            "required_skills": [{"name": "Python"}, {"name": "SQL"}],
            "bonus_skills": [{"name": "Docker"}],
        }
        system = {
            "id": "s1",
            "required_skills": [{"name": "Python"}],
            "bonus_skills": [{"name": "Docker"}],
        }
        result = await evaluate_sample_async(golden, system)
        # required: tp=1 (Python), ss_size=1 → p=1.0, gs_size=2 → r=0.5, f1=0.6667
        # bonus: tp=1 (Docker), ss_size=1 → p=1.0, gs_size=1 → r=1.0, f1=1.0
        # weights: w_req=2/3, w_bon=1/3
        # precision = 1.0*2/3 + 1.0*1/3 = 1.0
        # recall = 0.5*2/3 + 1.0*1/3 = 0.6667
        # f1 = 0.6667*2/3 + 1.0*1/3 = 0.7778
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(0.6667, abs=1e-4)
        assert result.f1 == pytest.approx(0.7778, abs=1e-4)


# ──────────────────────────────────────────────
# evaluate_pair_async
# ──────────────────────────────────────────────


class TestEvaluatePairAsync:
    async def test_identical_pairs(self):
        a = {"id": "a1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        b = {"id": "a1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        result = await evaluate_pair_async(a, b)
        assert result.f1 == pytest.approx(1.0)

    async def test_different_pairs(self):
        a = {"id": "a1", "required_skills": [{"name": "Python"}], "bonus_skills": []}
        b = {"id": "b1", "required_skills": [{"name": "Rust"}], "bonus_skills": []}
        result = await evaluate_pair_async(a, b)
        assert result.f1 == pytest.approx(0.0)

    async def test_does_not_call_llm(self):
        a = {"id": "a1", "required_skills": [], "bonus_skills": []}
        b = {"id": "b1", "required_skills": [], "bonus_skills": []}
        with patch("app.services.judge_service.call_llm_with_fallback") as mock_llm:
            await evaluate_pair_async(a, b)
        mock_llm.assert_not_called()


# ──────────────────────────────────────────────
# _call_llm_judge_async
# ──────────────────────────────────────────────


class TestCallLlmJudgeAsync:
    async def test_returns_score_and_reasoning(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"f1_score": 0.88, "details": "good match"}'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value={"f1_score": 0.88, "details": "good match"},
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score == pytest.approx(0.88)
        assert reasoning == "good match"

    async def test_handles_accuracy_field(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"accuracy": 0.75, "reasoning": "ok"}'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value={"accuracy": 0.75, "reasoning": "ok"},
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score == pytest.approx(0.75)

    async def test_handles_precision_field(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"precision": 0.9}'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value={"precision": 0.9},
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score == pytest.approx(0.9)

    async def test_parse_failure_returns_none_and_error(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": "garbage"}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            side_effect=LLMResponseError("parse failed"),
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score is None
        assert reasoning is not None
        assert "Failed to parse" in reasoning

    async def test_non_dict_result_returns_none(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '"just a string"'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value="just a string",
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score is None
        assert "non-dict" in (reasoning or "")

    async def test_non_dict_response_content(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value="plain string response"),
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        # str(raw) = "plain string response" → parse fails → returns (None, error)
        assert score is None
        assert reasoning is not None
        assert "Failed to parse" in reasoning

    async def test_constructs_prompt_with_version(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch("app.services.judge_service._build_judge_prompt") as mock_build, \
             patch(
                "app.services.judge_service.call_llm_with_fallback",
                AsyncMock(return_value={"content": '{"f1_score": 0.9}'}),
             ), patch(
                "app.services.judge_service.parse_llm_json_response",
                return_value={"f1_score": 0.9},
             ):
            await _call_llm_judge_async(golden, system, version="v2")
        mock_build.assert_called_once_with(golden, system, "v2")

    async def test_empty_llm_response_content(self):
        golden = {"required_skills": [{"name": "Python"}]}
        system = {"required_skills": [{"name": "Python"}]}
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": ""}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            side_effect=LLMResponseError("empty"),
        ):
            score, reasoning = await _call_llm_judge_async(golden, system)
        assert score is None
        assert reasoning is not None


# ──────────────────────────────────────────────
# evaluate_batch_async
# ──────────────────────────────────────────────


class TestEvaluateBatchAsync:
    async def test_both_files_have_matching_ids(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[{"name":"Docker"}]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[{"name":"Docker"}]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file, threshold=0.9)
        assert metrics.total_samples == 2
        assert metrics.evaluated_samples == 2
        assert metrics.avg_precision == pytest.approx(1.0)
        assert metrics.avg_recall == pytest.approx(1.0)
        assert metrics.avg_f1 == pytest.approx(1.0)
        assert metrics.quality_gate["passed"] is True
        assert metrics.judge_prompt_version is None

    async def test_partial_match_batch(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Rust"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        assert metrics.evaluated_samples == 1
        assert metrics.avg_f1 == pytest.approx(0.0)

    async def test_skips_missing_system_samples(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        assert metrics.total_samples == 2
        assert metrics.evaluated_samples == 1
        assert metrics.avg_f1 == pytest.approx(1.0)

    async def test_no_matching_samples_returns_empty_metrics(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"other","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        # Early return when no evaluations → total_samples defaults to 0
        assert metrics.total_samples == 0
        assert metrics.evaluated_samples == 0
        assert metrics.avg_f1 == 0.0

    async def test_quality_gate_fails_on_low_score(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Rust"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file, threshold=0.5)
        assert metrics.quality_gate["passed"] is False
        assert metrics.quality_gate["status"] == "red"

    async def test_f1_distribution_excellent(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        assert metrics.f1_distribution["excellent"] == 1

    async def test_f1_distribution_good(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        # 4 required, 3 matches → p=1.0, r=0.75, f1=0.8571 → "good" (>=0.70)
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"A"},{"name":"B"},{"name":"C"},{"name":"D"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"A"},{"name":"B"},{"name":"C"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        assert metrics.f1_distribution["good"] == 1

    async def test_f1_distribution_poor(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"},{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        # f1=0 because golden has skills but system is empty → _f1 returns (0,0,0)
        # Actually: golden_req_set has 2 items, system_req_set is empty → p=0, r=0, f1=0
        assert metrics.f1_distribution["poor"] == 1

    async def test_with_llm_judge_and_version(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"f1_score": 0.99}'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value={"f1_score": 0.99},
        ):
            metrics = await evaluate_batch_async(
                golden_file, system_file, use_llm_judge=True, judge_version="v2",
            )
        assert metrics.judge_prompt_version == "v2"
        assert metrics.per_sample[0].llm_score == pytest.approx(0.99)

    async def test_all_samples_llm_score_and_reasoning(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        with patch(
            "app.services.judge_service.call_llm_with_fallback",
            AsyncMock(return_value={"content": '{"f1_score": 0.95}'}),
        ), patch(
            "app.services.judge_service.parse_llm_json_response",
            return_value={"f1_score": 0.95},
        ):
            metrics = await evaluate_batch_async(
                golden_file, system_file, use_llm_judge=True,
            )
        for sample in metrics.per_sample:
            assert sample.llm_score == pytest.approx(0.95)

    async def test_weighted_score_calculation(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"Rust"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        metrics = await evaluate_batch_async(golden_file, system_file)
        # g1: f1=1.0 → excellent (weight 1.0)
        # g2: f1=0.0 → poor (weight 0.0)
        # weighted = (1*1.0 + 1*0.0) / 2 = 0.5
        assert metrics.weighted_score == pytest.approx(0.5)
