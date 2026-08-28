"""Unit tests for persist_extraction_result with mocked DB."""
from __future__ import annotations

import types

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
    async def fake_upsert_position(_session: object, name: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=111, name=name)

    async def fake_upsert_skill(_session: object, name: str, category: str, **_kwargs: object) -> object:
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
    record, _pos_id, _skill_ids = await s.persist_extraction_result(session, "some JD text", result)

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

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
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
    record, _pos_id, _skill_ids = await s.persist_extraction_result(session, "JD", result)
    assert record.job_title == "Backend Engineer"
    # session.add called for the JDExtractionRecord
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_persist_skips_empty_skill_name(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
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
    record, _pos_id, _skill_ids = await s.persist_extraction_result(session, "JD", result)
    assert record.job_title == "Backend Engineer"


@pytest.mark.asyncio
async def test_persist_invalid_extraction_lower_hallucination(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result(is_valid=False, confidence=0.7)
    record, _pos_id, _skill_ids = await s.persist_extraction_result(session, "JD", result)
    assert record.hallucination_score == pytest.approx(0.3, rel=1e-3)


@pytest.mark.asyncio
async def test_persist_evolves_to_successors(monkeypatch: pytest.MonkeyPatch) -> None:
    """R5 根治: evolves_to 后继岗位一并落 PG（不再只写图成孤儿）。"""
    session = FakeSession()
    upserted_positions: list[str] = []

    async def fake_upsert_position(_session: object, name: str, **_kwargs: object) -> object:
        upserted_positions.append(name)
        return types.SimpleNamespace(id=111, name=name)

    async def fake_upsert_skill(_session: object, name: str, category: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=222, name=name, category=category)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result()
    result["data"]["evolves_to"] = ["Data Engineer", {"position": "Data Scientist", "similarity": 0.8}]
    record, _pos_id, _skill_ids = await s.persist_extraction_result(session, "some JD", result)

    assert record.job_title == "Backend Engineer"
    # 主岗位 + 2 个后继都 upsert 了
    assert upserted_positions[0] == "Backend Engineer"
    assert "Data Engineer" in upserted_positions
    assert "Data Scientist" in upserted_positions


@pytest.mark.asyncio
async def test_persist_non_it_position_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 IT 岗位（销售/HR 等）被 industry gate 拦截 → 不建岗位，返回 NON_IT。"""
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        return None  # gate 拦截

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
        raise AssertionError("非 IT 岗位不应建 skill")

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)

    result = _make_extraction_result(position_name="销售代表")
    record, pos_id, skills = await s.persist_extraction_result(session, "JD", result)
    assert pos_id == "NON_IT"
    assert skills == {}
    assert record.job_title == "销售代表"
    assert "non_it" in record.extracted_skills.get("skipped_reason", "")


@pytest.mark.asyncio
async def test_persist_passes_industry_to_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """persist 把 LLM industry 传给 _upsert_position（入库分类，修复 79% 未分类）。"""
    session = FakeSession()
    captured: dict = {}

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        captured.update(_kwargs)
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result()
    result["data"]["industry"] = "互联网/IT"
    record, _pos_id, _skills = await s.persist_extraction_result(session, "JD", result)
    assert captured.get("industry") == "互联网/IT"


@pytest.mark.asyncio
async def test_persist_empty_skills_marks_quality_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """空技能岗位：仍建岗位，但 extracted_skills 标记 quality_hint=no_skills（待重试，不删数据）。"""
    session = FakeSession()

    async def fake_upsert_position(_s: object, name: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=1, name=name)

    async def fake_upsert_skill(_s: object, name: str, cat: str, **_kwargs: object) -> object:
        return types.SimpleNamespace(id=10, name=name, category=cat)

    async def fake_ensure(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(s, "_upsert_position", fake_upsert_position)
    monkeypatch.setattr(s, "_upsert_skill", fake_upsert_skill)
    monkeypatch.setattr(s, "_ensure_position_skill_relation", fake_ensure)

    result = _make_extraction_result()
    result["data"]["required_skills"] = []
    result["data"]["preferred_skills"] = []
    record, _pos_id, skills = await s.persist_extraction_result(session, "JD", result)
    assert skills == {}
    assert record.extracted_skills.get("quality_hint") == "no_skills"
