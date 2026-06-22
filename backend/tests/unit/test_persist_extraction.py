"""Unit tests for persist_extraction_result with mocked DB."""
from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import stage3_services as s


class FakeSession:
    """Fake AsyncSession that records .add() and .flush() calls."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False

    async def flush(self) -> None:
        self.flushed = True

    def add(self, obj: object) -> None:
        self.added.append(obj)


def _make_extraction_result(
    position_name: str = "Backend Engineer",
    required_skills: list[dict] | None = None,
    preferred_skills: list[dict] | None = None,
    confidence: float = 0.9,
    is_valid: bool = True,
) -> dict:
    return {
        "data": {
            "position_name": position_name,
            "required_skills": required_skills or [{"name": "Python"}],
            "preferred_skills": preferred_skills or [],
            "experience_required": 3,
            "education_required": "BS",
        },
        "validation": {"confidence": confidence, "is_valid": is_valid},
        "success": True,
    }


@pytest.mark.asyncio
async def test_persist_extraction_result_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    # Stub DB upsert helpers
    async def fake_upsert_position(_session: object, name: str) -> object:
        return types.SimpleNamespace(id=111, name=name)

    async def fake_upsert_skill(_session: object, name: str, category: str) -> object:
        return types.SimpleNamespace(id=222, name=name, category=category)

    async def fake_ensure(
        _session: object,
        _position_id: object,
        _skill_id: object,
        _requirement_type: str,
        _confidence: float,
    ) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result()
    record = await s.persist_extraction_result(session, "some JD text", result)

    assert record.job_title == "Backend Engineer"
    assert record.confidence == 0.9
    assert record.status == "completed"
    assert record.hallucination_score == 0.0
    assert session.flushed is True
    # At least one add (JDExtractionRecord)
    assert len(session.added) >= 1


@pytest.mark.asyncio
async def test_persist_with_preferred_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result(
        required_skills=[{"name": "Python", "category": "hard_skill"}],
        preferred_skills=[{"name": "Docker", "category": "tool"}],
    )
    record = await s.persist_extraction_result(session, "JD", result)
    assert record.job_title == "Backend Engineer"
    # session.add called: JDExtractionRecord + position + skill + relation
    assert len(session.added) >= 4


@pytest.mark.asyncio
async def test_persist_skips_empty_skill_name(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    # Empty skill name should be skipped
    result = _make_extraction_result(
        required_skills=[{"unknown": "key"}],
    )
    record = await s.persist_extraction_result(session, "JD", result)
    assert record.job_title == "Backend Engineer"


@pytest.mark.asyncio
async def test_persist_invalid_extraction_lower_hallucination(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result(is_valid=False, confidence=0.7)
    record = await s.persist_extraction_result(session, "JD", result)
    assert record.hallucination_score == pytest.approx(0.3, rel=1e-3)
