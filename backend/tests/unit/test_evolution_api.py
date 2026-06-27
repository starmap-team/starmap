"""API tests for evolution endpoints — contract validation + response shape.

Tests the 6 new evolution API endpoints using the TestClient pattern
from test_stage4_api.py. Uses FakeSession to avoid real DB connections.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


class FakeScalarResult:
    def __init__(self, items: list):
        self._items = items

    def all(self) -> list:
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class FakeResult:
    def __init__(self, items: list):
        self._scalars = FakeScalarResult(items)

    def scalars(self) -> FakeScalarResult:
        return self._scalars

    def all(self) -> list:
        return self._scalars.all()


class FakeAsyncSession:
    """Fake async session for API tests."""

    def __init__(self, return_items: list | None = None):
        self._items = return_items or []
        self._added: list = []
        self.flush = AsyncMock()

    async def execute(self, stmt):
        return FakeResult(self._items)

    def add(self, obj):
        self._added.append(obj)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture(autouse=True)
def _override_deps():
    """Override FastAPI dependencies for all tests."""
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def _make_changelog_record():
    return SimpleNamespace(
        id="cl-1",
        position_name="Backend",
        skill_name="Go",
        change_type="added_required",
        old_proficiency=None,
        new_proficiency="熟悉",
        old_requirement=None,
        new_requirement="required",
        snapshot_from_id=None,
        snapshot_to_id="snap-1",
        trust_score=0.7,
        confidence=0.85,
        evidence_json={},
        created_at=datetime(2026, 6, 27, tzinfo=UTC),
    )


def _make_path_record():
    return SimpleNamespace(
        id="path-1",
        source_position="Backend",
        target_position="FullStack",
        similarity=0.75,
        evidence_count=5,
        skill_overlap=["Python", "SQL"],
        key_gaps=["JavaScript", "React"],
        trust_score=0.8,
        first_detected=datetime(2026, 6, 27, tzinfo=UTC),
        last_updated=datetime(2026, 6, 27, tzinfo=UTC),
    )


def _make_snapshot_record():
    return SimpleNamespace(
        id="snap-1",
        position_name="Backend",
        snapshot_date=datetime(2026, 6, 1, tzinfo=UTC),
        required_skills=[{"name": "Python", "proficiency": "熟悉"}],
        preferred_skills=[{"name": "Docker", "proficiency": "了解"}],
        source_count=5,
        metadata_json={},
    )


def _make_timeseries_record():
    return SimpleNamespace(
        id="ts-1",
        skill_name="RAG",
        window_start=datetime(2026, 1, 1, tzinfo=UTC),
        window_end=datetime(2026, 4, 1, tzinfo=UTC),
        frequency=3,
        source_count=3,
        positions=["AI Engineer"],
        category="hard_skill",
    )


# ─── GET /evolution/changelog/{position} ───


def test_changelog_returns_list():
    """Changelog endpoint returns a list of ChangelogEntry."""
    from app.dependencies import get_db_session

    record = _make_changelog_record()
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/changelog/Backend")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    entry = body[0]
    assert entry["skill_name"] == "Go"
    assert entry["change_type"] == "added_required"
    assert "trust_score" in entry
    assert "confidence" in entry


def test_changelog_empty():
    """Changelog returns empty list when no records."""
    from app.dependencies import get_db_session

    session = FakeAsyncSession(return_items=[])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/changelog/Unknown")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── GET /evolution/paths/{position} ───


def test_paths_returns_list():
    """Paths endpoint returns a list of EvolutionPathEntry."""
    from app.dependencies import get_db_session

    record = _make_path_record()
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/paths/Backend")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    path = body[0]
    assert path["source_position"] == "Backend"
    assert path["target_position"] == "FullStack"
    assert path["similarity"] == 0.75
    assert "skill_overlap" in path
    assert "key_gaps" in path


# ─── GET /evolution/emerging-skills ───


def test_emerging_skills_returns_list():
    """Emerging skills endpoint returns a list of EmergingSkill."""
    from app.dependencies import get_db_session

    record = _make_timeseries_record()
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/emerging-skills")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


def test_emerging_skills_empty():
    """Emerging skills returns empty when no timeseries data."""
    from app.dependencies import get_db_session

    session = FakeAsyncSession(return_items=[])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/emerging-skills")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── GET /evolution/snapshots ───


def test_snapshots_returns_list():
    """Snapshots endpoint returns a list of EvolutionSnapshot."""
    from app.dependencies import get_db_session

    record = _make_snapshot_record()
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/snapshots")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    snap = body[0]
    assert snap["position_name"] == "Backend"
    assert "required_skills" in snap
    assert "preferred_skills" in snap


def test_snapshots_filter_by_position():
    """Snapshots can be filtered by position."""
    from app.dependencies import get_db_session

    session = FakeAsyncSession(return_items=[_make_snapshot_record()])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/snapshots?position=Backend")
    assert resp.status_code == 200


# ─── GET /evolution/review-queue ───


def test_review_queue_returns_list():
    """Review queue returns low-trust changelog items."""
    from app.dependencies import get_db_session

    record = _make_changelog_record()
    record.trust_score = 0.3  # Below 0.5 threshold
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/review-queue")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


# ─── GET /evolution/cii-history/{position} ───


def test_cii_history_returns_history():
    """CII history returns position and history array."""
    from app.dependencies import get_db_session

    record = _make_snapshot_record()
    session = FakeAsyncSession(return_items=[record])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/cii-history/Backend")
    assert resp.status_code == 200
    body = resp.json()
    assert body["position"] == "Backend"
    assert "history" in body
    assert isinstance(body["history"], list)


# ─── Existing endpoints still work ───


def test_trends_still_works():
    """Original /evolution/trends endpoint still responds."""
    from app.dependencies import get_db_session

    session = FakeAsyncSession(return_items=[])
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app) as client:
        resp = client.get("/api/v1/evolution/trends")
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.skip(reason="Requires Redis connection for Celery")
def test_analyze_still_works():
    """Original /evolution/analyze endpoint still responds."""
    with TestClient(app) as client:
        resp = client.post("/api/v1/evolution/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    assert "task_id" in body
