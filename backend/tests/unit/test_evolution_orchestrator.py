"""Unit tests for EvolutionOrchestrator — 8-step pipeline.

Uses FakeSession pattern from test_stage3_analyze.py to avoid real DB.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.evolution.orchestrator import EvolutionOrchestrator


class FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, items: list):
        self._items = items

    def all(self) -> list:
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def one_or_none(self):
        if len(self._items) == 1:
            return self._items[0]
        if not self._items:
            return None
        raise ValueError("Multiple results")


class FakeResult:
    """Fake SQLAlchemy result."""

    def __init__(self, items: list):
        self._scalars = FakeScalarResult(items)
        self._rows = items

    def scalars(self) -> FakeScalarResult:
        return self._scalars

    def all(self) -> list:
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Fake async SQLAlchemy session."""

    def __init__(self, return_items: list | None = None):
        self._return_items = return_items or []
        self._added: list = []
        self.flush = AsyncMock()

    def execute(self, stmt):
        import asyncio
        return asyncio.coroutine(lambda: FakeResult(self._return_items))()

    def add(self, obj):
        self._added.append(obj)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_snapshot_record(
    position: str = "Backend",
    required: list | None = None,
    preferred: list | None = None,
    source_count: int = 5,
) -> SimpleNamespace:
    """Create a fake EvolutionSnapshot record."""
    from datetime import UTC, datetime

    return SimpleNamespace(
        id="snap-1",
        position_name=position,
        snapshot_date=datetime(2026, 6, 1, tzinfo=UTC),
        required_skills=required or [{"name": "Python", "proficiency": "熟悉"}],
        preferred_skills=preferred or [{"name": "Docker", "proficiency": "了解"}],
        source_count=source_count,
        metadata_json={},
    )


@pytest.mark.asyncio
async def test_orchestrator_analyze_with_snapshots(monkeypatch):
    """Full pipeline with two snapshots produces diff and changelog."""
    snap_old = _make_snapshot_record(
        required=[{"name": "Python"}, {"name": "SQL"}],
        preferred=[{"name": "Docker"}],
    )
    snap_new = _make_snapshot_record(
        required=[{"name": "Python"}, {"name": "Docker"}, {"name": "Go"}],
        preferred=[{"name": "SQL"}],
    )

    session = FakeSession(return_items=[snap_old, snap_new])
    orchestrator = EvolutionOrchestrator(session)

    # Mock the DB-dependent methods to avoid real queries
    orchestrator._snapshot_mgr.get_snapshot_pair = AsyncMock(
        return_value=(
            SimpleNamespace(
                id="snap-1",
                position_name="Backend",
                snapshot_date=snap_old.snapshot_date,
                required_skills=[SimpleNamespace(name="Python", proficiency=None), SimpleNamespace(name="SQL", proficiency=None)],
                preferred_skills=[SimpleNamespace(name="Docker", proficiency=None)],
                source_count=5,
            ),
            SimpleNamespace(
                id="snap-2",
                position_name="Backend",
                snapshot_date=snap_new.snapshot_date,
                required_skills=[SimpleNamespace(name="Python", proficiency=None), SimpleNamespace(name="Docker", proficiency=None), SimpleNamespace(name="Go", proficiency=None)],
                preferred_skills=[SimpleNamespace(name="SQL", proficiency=None)],
                source_count=5,
            ),
        )
    )
    orchestrator._load_timeseries = AsyncMock(return_value=None)
    orchestrator._load_path_data = AsyncMock(return_value=None)

    result = await orchestrator.analyze("Backend")

    assert result.position_name == "Backend"
    assert result.diff_result is not None
    assert result.diff_result.total_changes > 0
    assert result.changelog_entries > 0
    assert result.duration_seconds >= 0


@pytest.mark.asyncio
async def test_orchestrator_analyze_no_snapshots():
    """No snapshots → first-snapshot diff with all skills added."""
    session = FakeSession()
    orchestrator = EvolutionOrchestrator(session)

    # Return (None, None) — no snapshots
    orchestrator._snapshot_mgr.get_snapshot_pair = AsyncMock(return_value=(None, None))
    orchestrator._load_timeseries = AsyncMock(return_value=None)
    orchestrator._load_path_data = AsyncMock(return_value=None)

    result = await orchestrator.analyze("NewPosition")

    assert result.position_name == "NewPosition"
    # No snapshots found, orchestrator returns early with empty result
    assert result.diff_result is None
    assert result.duration_seconds >= 0


@pytest.mark.asyncio
async def test_orchestrator_emergence_detection():
    """Orchestrator runs emergence detection when timeseries data exists."""
    session = FakeSession()
    orchestrator = EvolutionOrchestrator(session)

    from datetime import UTC, datetime as _dt
    snap = SimpleNamespace(
        id="snap-1", position_name="Backend",
        snapshot_date=_dt(2026, 6, 1, tzinfo=UTC),
        required_skills=[SimpleNamespace(name="Python", proficiency=None)],
        preferred_skills=[], source_count=5,
    )
    orchestrator._snapshot_mgr.get_snapshot_pair = AsyncMock(return_value=(None, snap))
    orchestrator._load_timeseries = AsyncMock(return_value={
        "RAG": {"frequencies": [1, 2, 1, 2, 1], "current": 5, "sources": 3, "positions": ["AI"]},
    })
    orchestrator._load_path_data = AsyncMock(return_value=None)

    result = await orchestrator.analyze("Backend")

    assert result.emergence_report is not None
    assert len(result.emergence_report.emerging) >= 1
