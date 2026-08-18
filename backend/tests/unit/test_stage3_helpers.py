"""Unit tests for stage3_services pure helper functions."""
from __future__ import annotations

import asyncio

import pytest

from app.core.extraction.graph_writer import skill_entry_category, skill_entry_name
from app.tasks import stage3_services as s


# ---------------------------------------------------------------------------
# skill_entry_name (shared from graph_writer)
# ---------------------------------------------------------------------------
class TestSkillName:
    def test_plain_string(self) -> None:
        assert skill_entry_name("Python") == "Python"

    def test_dict_with_name(self) -> None:
        assert skill_entry_name({"name": "Go"}) == "Go"

    def test_dict_with_skill_key(self) -> None:
        assert skill_entry_name({"skill": "Rust"}) == "Rust"

    def test_dict_with_title_key(self) -> None:
        assert skill_entry_name({"title": "Kubernetes"}) == "Kubernetes"

    def test_dict_unknown_key_returns_empty(self) -> None:
        assert skill_entry_name({"unknown": None}) == ""

    def test_whitespace_stripped(self) -> None:
        assert skill_entry_name("  Docker  ") == "Docker"

    def test_empty_dict(self) -> None:
        assert skill_entry_name({}) == ""

    def test_int_coerced_to_string(self) -> None:
        assert skill_entry_name(42) == "42"


# ---------------------------------------------------------------------------
# skill_entry_category (shared from graph_writer, default='general' for stage3)
# ---------------------------------------------------------------------------
class TestSkillCategory:
    def test_string_returns_general(self) -> None:
        assert skill_entry_category("x", default="general") == "general"

    def test_dict_with_category(self) -> None:
        assert skill_entry_category({"category": "backend"}, default="general") == "backend"

    def test_dict_without_category(self) -> None:
        assert skill_entry_category({"name": "Go"}, default="general") == "general"

    def test_none_returns_general(self) -> None:
        assert skill_entry_category(None, default="general") == "general"

    def test_default_skill(self) -> None:
        assert skill_entry_category("x") == "skill"

    def test_category_lowered(self) -> None:
        assert skill_entry_category({"category": "Hard_Skill"}, default="general") == "hard_skill"


# ---------------------------------------------------------------------------
# JDExtractionRecord.to_extraction_payload (replaces removed
# _extraction_payload_from_record — see TODO comment that previously lived here).
# ---------------------------------------------------------------------------
class TestExtractionPayload:
    def _make(self, **kw):
        """Build an in-memory JDExtractionRecord without touching the DB."""
        import uuid
        from datetime import UTC, datetime

        from app.models.extraction_models import JDExtractionRecord

        defaults: dict = {
            "jd_content": "Stub JD content",
            "job_title": kw.pop("job_title", "数据工程师"),
            "extracted_skills": kw.pop("extracted_skills", []),
            "experience_years": kw.pop("experience_years", None),
            "education": kw.pop("education", None),
            "confidence": kw.pop("confidence", 0.85),
            "hallucination_score": kw.pop("hallucination_score", None),
            "status": kw.pop("status", "completed"),
        }
        defaults.update(kw)
        rec = JDExtractionRecord(id=uuid.uuid4(), created_at=datetime.now(UTC), **defaults)
        return rec

    def test_minimal_record(self) -> None:
        rec = self._make(extracted_skills=[])
        payload = rec.to_extraction_payload()
        assert payload["position_name"] == "数据工程师"
        assert payload["required_skills"] == []
        assert payload["experience_required"] is None
        assert payload["education_required"] is None

    def test_record_with_existing_skills(self) -> None:
        skills = [
            {"name": "Python", "level": "advanced"},
            {"name": "SQL", "level": "intermediate"},
        ]
        rec = self._make(
            job_title="后端工程师",
            extracted_skills=skills,
            experience_years=3,
            education="本科",
        )
        payload = rec.to_extraction_payload()
        assert payload["position_name"] == "后端工程师"
        assert payload["experience_required"] == 3
        assert payload["education_required"] == "本科"
        # raw list of skill dicts is normalized into required_skills — only the
        # ``name`` field is preserved (level/category stripped at this layer;
        # downstream callers enrich again via normalize.py).
        assert payload["required_skills"] == ["Python", "SQL"]

    def test_record_with_dict_shaped_skills(self) -> None:
        """When extracted_skills already has required/bonus keys, keep that shape."""
        rec = self._make(
            extracted_skills={
                "required_skills": ["Python", "FastAPI"],
                "preferred_skills": ["Docker"],
            }
        )
        payload = rec.to_extraction_payload()
        assert payload["required_skills"] == ["Python", "FastAPI"]
        assert payload["preferred_skills"] == ["Docker"]

    def test_record_with_string_list_skills(self) -> None:
        """When extracted_skills is a flat list of strings, wrap into required_skills."""
        rec = self._make(extracted_skills=["Python", "SQL"])
        payload = rec.to_extraction_payload()
        assert payload["required_skills"] == ["Python", "SQL"]

    def test_record_with_invalid_skills_type(self) -> None:
        """When extracted_skills is None, payload stays empty (no required_skills key)."""
        rec = self._make(extracted_skills=None)
        payload = rec.to_extraction_payload()
        assert payload.get("required_skills") is None
        # setdefault still applies for position_name etc.
        assert payload["position_name"] == "数据工程师"


# ---------------------------------------------------------------------------
# _confidence_from_result
# ---------------------------------------------------------------------------
class TestConfidence:
    def test_with_validation_confidence(self) -> None:
        assert s._confidence_from_result({"validation": {"confidence": 0.9}}) == 0.9

    def test_fallback_default(self) -> None:
        # 2d84351f: 置信度改为真实测量 — 无 validation 数据时默认 confidence=1.0（保守认为无幻觉）
        assert s._confidence_from_result({}) == 1.0

    def test_empty_validation(self) -> None:
        assert s._confidence_from_result({"validation": {}}) == 1.0

    def test_none_validation(self) -> None:
        assert s._confidence_from_result({"validation": None}) == 1.0


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
        from app.utils.async_helpers import run_async

        async def coro() -> int:
            await asyncio.sleep(0)
            return 42

        assert run_async(coro()) == 42

    def test_returns_none_for_none_coroutine(self) -> None:
        from app.utils.async_helpers import run_async

        async def coro() -> None:
            await asyncio.sleep(0)

        assert run_async(coro()) is None
