"""Unit tests for graph ingestion helpers (mocked Neo4j)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tasks import stage3_services as s


class DummyDriver:
    pass


class DummyCtx:
    async def __aenter__(self) -> DummyDriver:
        return DummyDriver()

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_write_single_extraction_to_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        s,
        "GraphConfig",
        lambda: SimpleNamespace(get_driver=lambda: DummyCtx()),
    )

    async def fake_batch_write_extractions(extractions: list, driver: object) -> list[dict]:
        return [{"triples_merged": 2, "relationships_touched": 1}]

    monkeypatch.setattr(s, "batch_write_extractions", fake_batch_write_extractions)

    res = await s.write_single_extraction_to_graph(
        {"position_name": "X", "required_skills": []}
    )
    assert res.get("triples_merged") == 2
    assert res.get("relationships_touched") == 1


@pytest.mark.asyncio
async def test_write_single_empty_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        s,
        "GraphConfig",
        lambda: SimpleNamespace(get_driver=lambda: DummyCtx()),
    )

    async def fake_batch_write_extractions(extractions: list, driver: object) -> list:
        return []

    monkeypatch.setattr(s, "batch_write_extractions", fake_batch_write_extractions)

    res = await s.write_single_extraction_to_graph(
        {"position_name": "Y", "required_skills": []}
    )
    assert res == {}


class FakeResult:
    """Mock SQLAlchemy result that returns scalars().all()."""

    def __init__(self, records: list) -> None:
        self._records = records

    def scalars(self) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self._records)


class FakeSession:
    def __init__(self, records: list | None = None) -> None:
        self._records = records or []
        self.committed = False

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, _query: object) -> FakeResult:
        return FakeResult(self._records)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_run_build_graph_from_extractions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run_build_graph_from_extractions with mocked DB + graph."""
    fake_record = SimpleNamespace(
        id=1,
        extracted_skills=None,
        job_title="SRE",
        experience_years=5,
        education="BS",
        created_at=SimpleNamespace(),
    )
    fake_session = FakeSession(records=[fake_record])

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
    monkeypatch.setattr(
        s,
        "GraphConfig",
        lambda: SimpleNamespace(get_driver=lambda: DummyCtx()),
    )

    async def fake_batch_write(extractions: list, driver: object) -> list[dict]:
        return [{"triples_merged": 3, "relationships_touched": 2}]

    monkeypatch.setattr(s, "batch_write_extractions", fake_batch_write)

    result = await s.run_build_graph_from_extractions(limit=10)
    assert result["status"] == "completed"
    assert result["processed"] == 1
    assert result["triples_merged"] == 3
    assert result["relationships_touched"] == 2


@pytest.mark.asyncio
async def test_run_build_graph_clamps_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limit is clamped to [1, 1000]."""
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
    monkeypatch.setattr(
        s,
        "GraphConfig",
        lambda: SimpleNamespace(get_driver=lambda: DummyCtx()),
    )

    async def fake_batch_write(extractions: list, driver: object) -> list:
        return []

    monkeypatch.setattr(s, "batch_write_extractions", fake_batch_write)

    result = await s.run_build_graph_from_extractions(limit=-5)
    assert result["processed"] == 0
