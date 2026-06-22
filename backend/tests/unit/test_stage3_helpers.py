"""Unit tests for stage3_services pure helper functions."""
from __future__ import annotations

import asyncio
import types

import pytest

from app.tasks import stage3_services as s


# ---------------------------------------------------------------------------
# _skill_name
# ---------------------------------------------------------------------------
class TestSkillName:
    def test_plain_string(self) -> None:
        assert s._skill_name("Python") == "Python"

    def test_dict_with_name(self) -> None:
        assert s._skill_name({"name": "Go"}) == "Go"

    def test_dict_with_skill_key(self) -> None:
        assert s._skill_name({"skill": "Rust"}) == "Rust"

    def test_dict_unknown_key_returns_empty(self) -> None:
        assert s._skill_name({"unknown": None}) == ""

    def test_whitespace_stripped(self) -> None:
        assert s._skill_name("  Docker  ") == "Docker"

    def test_empty_dict(self) -> None:
        assert s._skill_name({}) == ""

    def test_int_coerced_to_string(self) -> None:
        assert s._skill_name(42) == "42"


# ---------------------------------------------------------------------------
# _skill_category
# ---------------------------------------------------------------------------
class TestSkillCategory:
    def test_string_returns_general(self) -> None:
        assert s._skill_category("x") == "general"

    def test_dict_with_category(self) -> None:
        assert s._skill_category({"category": "backend"}) == "backend"

    def test_dict_without_category(self) -> None:
        assert s._skill_category({"name": "Go"}) == "general"

    def test_none_returns_general(self) -> None:
        assert s._skill_category(None) == "general"


# ---------------------------------------------------------------------------
# _extraction_payload_from_record
# ---------------------------------------------------------------------------
class TestExtractionPayload:
    def test_minimal_record(self) -> None:
        record = types.SimpleNamespace(
            extracted_skills=None,
            job_title="SRE",
            experience_years=5,
            education="BS",
        )
        payload = s._extraction_payload_from_record(record)
        assert payload["position_name"] == "SRE"
        assert payload["experience_required"] == 5
        assert payload["education_required"] == "BS"

    def test_record_with_existing_skills(self) -> None:
        record = types.SimpleNamespace(
            extracted_skills={"position_name": "DevOps", "required_skills": [{"name": "K8s"}]},
            job_title="DevOps",
            experience_years=3,
            education="MS",
        )
        payload = s._extraction_payload_from_record(record)
        # extracted_skills dict merges into payload, position_name kept from record
        assert payload["position_name"] == "DevOps"
        assert payload["required_skills"] == [{"name": "K8s"}]


# ---------------------------------------------------------------------------
# _confidence_from_result
# ---------------------------------------------------------------------------
class TestConfidence:
    def test_with_validation_confidence(self) -> None:
        assert s._confidence_from_result({"validation": {"confidence": 0.9}}) == 0.9

    def test_fallback_default(self) -> None:
        assert s._confidence_from_result({}) == 0.85

    def test_empty_validation(self) -> None:
        assert s._confidence_from_result({"validation": {}}) == 0.85

    def test_none_validation(self) -> None:
        assert s._confidence_from_result({"validation": None}) == 0.85


# ---------------------------------------------------------------------------
# _hallucination_score_from_result
# ---------------------------------------------------------------------------
class TestHallucinationScore:
    def test_valid_returns_zero(self) -> None:
        assert s._hallucination_score_from_result({"validation": {"is_valid": True}}) == 0.0

    def test_invalid_with_confidence(self) -> None:
        score = s._hallucination_score_from_result(
            {"validation": {"is_valid": False, "confidence": 0.8}}
        )
        assert score == pytest.approx(0.2, rel=1e-3)

    def test_invalid_no_confidence(self) -> None:
        score = s._hallucination_score_from_result({"validation": {"is_valid": False}})
        assert score == pytest.approx(1.0, rel=1e-3)

    def test_no_validation_key(self) -> None:
        assert s._hallucination_score_from_result({}) == 0.0

    def test_valid_true_default(self) -> None:
        # is_valid defaults to True when absent
        assert s._hallucination_score_from_result({"validation": {}}) == 0.0


# ---------------------------------------------------------------------------
# run_async
# ---------------------------------------------------------------------------
class TestRunAsync:
    def test_executes_coroutine(self) -> None:
        async def coro() -> int:
            await asyncio.sleep(0)
            return 42

        assert s.run_async(coro()) == 42

    def test_returns_none_for_none_coroutine(self) -> None:
        async def coro() -> None:
            await asyncio.sleep(0)

        assert s.run_async(coro()) is None
