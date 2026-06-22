"""Unit tests for run_analyze_evolution_trends (mocked DB)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tasks import stage3_services as s


class FakeResult:
    def __init__(self, records: list) -> None:
        self._records = records

    def scalars(self) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self._records)


class FakeSession:
    def __init__(self, records: list | None = None) -> None:
        self._records = records or []
        self.executed_queries: list = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, query: object) -> FakeResult:
        self.executed_queries.append(query)
        return FakeResult(self._records)

    async def commit(self) -> None:
        pass


def _make_record(
    job_title: str = "Backend",
    required_skills: list | None = None,
    preferred_skills: list | None = None,
    experience_years: int = 3,
    education: str = "BS",
) -> SimpleNamespace:
    extracted_skills = {
        "position_name": job_title,
        "required_skills": required_skills or [],
        "preferred_skills": preferred_skills or [],
        "experience_required": experience_years,
        "education_required": education,
    }
    return SimpleNamespace(
        id=1,
        job_title=job_title,
        extracted_skills=extracted_skills,
        experience_years=experience_years,
        education=education,
        created_at=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_analyze_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _make_record(
        required_skills=[{"name": "Python", "category": "hard_skill"}, {"name": "Docker"}],
        preferred_skills=[{"name": "K8s"}],
    )
    fake_session = FakeSession(records=[record])

    def fake_sessionmaker() -> FakeSession:
        return fake_session

    monkeypatch.setattr(
        s,
        "create_async_engine",
        lambda *_a, **_kw: SimpleNamespace(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        s,
        "async_sessionmaker",
        lambda *_a, **_kw: fake_sessionmaker,
    )

    result = await s.run_analyze_evolution_trends(days=30)
    assert result["status"] == "completed"
    assert result["records_analyzed"] == 1
    assert result["skills_analyzed"] == 3  # Python, Docker, K8s
    assert len(result["trends"]) == 3


@pytest.mark.asyncio
async def test_analyze_empty_records(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = FakeSession(records=[])

    def fake_sessionmaker() -> FakeSession:
        return fake_session

    monkeypatch.setattr(
        s,
        "create_async_engine",
        lambda *_a, **_kw: SimpleNamespace(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        s,
        "async_sessionmaker",
        lambda *_a, **_kw: fake_sessionmaker,
    )

    result = await s.run_analyze_evolution_trends(days=90)
    assert result["status"] == "completed"
    assert result["records_analyzed"] == 0
    assert result["skills_analyzed"] == 0
    assert result["trends"] == []


@pytest.mark.asyncio
async def test_analyze_clamps_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """Days parameter is clamped to [7, 730]."""
    fake_session = FakeSession(records=[])

    def fake_sessionmaker() -> FakeSession:
        return fake_session

    monkeypatch.setattr(
        s,
        "create_async_engine",
        lambda *_a, **_kw: SimpleNamespace(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        s,
        "async_sessionmaker",
        lambda *_a, **_kw: fake_sessionmaker,
    )

    result = await s.run_analyze_evolution_trends(days=1)  # should clamp to 7
    assert result["days"] == 7

    result2 = await s.run_analyze_evolution_trends(days=9999)  # should clamp to 730
    assert result2["days"] == 730


@pytest.mark.asyncio
async def test_analyze_trend_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skills with count >= 5 are 'rising', else 'stable'."""
    # Create 6 records with same skill to make count >= 5
    records = [
        _make_record(required_skills=[{"name": "Python"}])
        for _ in range(6)
    ]
    fake_session = FakeSession(records=records)

    def fake_sessionmaker() -> FakeSession:
        return fake_session

    monkeypatch.setattr(
        s,
        "create_async_engine",
        lambda *_a, **_kw: SimpleNamespace(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        s,
        "async_sessionmaker",
        lambda *_a, **_kw: fake_sessionmaker,
    )

    result = await s.run_analyze_evolution_trends(days=30)
    trends = result["trends"]
    assert len(trends) >= 1
    python_trend = next(t for t in trends if t["skill_name"] == "Python")
    assert python_trend["trend"] == "rising"
    assert python_trend["source_count"] == 6
