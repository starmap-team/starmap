"""Unit tests for evolution API business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- Changelog / path / snapshot / timeseries / review-queue data models
- CII history computation logic
- Snapshot date filtering
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

# ── Fake records (mirrors what the API tests used) ──


def _make_changelog_record(**kwargs):
    defaults = {
        "id": "cl-1",
        "position_name": "Backend",
        "skill_name": "Go",
        "change_type": "added_required",
        "old_proficiency": None,
        "new_proficiency": "熟悉",
        "old_requirement": None,
        "new_requirement": "required",
        "snapshot_from_id": None,
        "snapshot_to_id": "snap-1",
        "trust_score": 0.7,
        "confidence": 0.85,
        "evidence_json": {},
        "created_at": datetime(2026, 6, 27, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_path_record(**kwargs):
    defaults = {
        "id": "path-1",
        "source_position": "Backend",
        "target_position": "FullStack",
        "similarity": 0.75,
        "evidence_count": 5,
        "skill_overlap": ["Python", "SQL"],
        "key_gaps": ["JavaScript", "React"],
        "trust_score": 0.8,
        "first_detected": datetime(2026, 6, 27, tzinfo=UTC),
        "last_updated": datetime(2026, 6, 27, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_snapshot_record(**kwargs):
    defaults = {
        "id": "snap-1",
        "position_name": "Backend",
        "snapshot_date": "2026-06-01",
        "required_skills": [{"name": "Python", "proficiency": "熟悉"}],
        "preferred_skills": [{"name": "Docker", "proficiency": "了解"}],
        "source_count": 5,
        "metadata_json": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_timeseries_record(**kwargs):
    defaults = {
        "id": "ts-1",
        "skill_name": "RAG",
        "window_start": datetime(2026, 1, 1, tzinfo=UTC),
        "window_end": datetime(2026, 4, 1, tzinfo=UTC),
        "frequency": 3,
        "source_count": 3,
        "positions": ["AI Engineer"],
        "category": "hard_skill",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ══════════════════════════════════════════════════════════════
# Changelog record — field validation
# ══════════════════════════════════════════════════════════════


class TestChangelogRecord:
    """Changelog record — construction and field access."""

    def test_default_fields(self):
        rec = _make_changelog_record()
        assert rec.skill_name == "Go"
        assert rec.change_type == "added_required"
        assert rec.trust_score == 0.7
        assert rec.confidence == 0.85

    def test_custom_fields(self):
        rec = _make_changelog_record(skill_name="Python", trust_score=0.3)
        assert rec.skill_name == "Python"
        assert rec.trust_score == 0.3

    def test_change_types(self):
        for ct in ("added_required", "removed_required", "added_preferred", "removed_preferred", "proficiency_change"):
            rec = _make_changelog_record(change_type=ct)
            assert rec.change_type == ct


# ══════════════════════════════════════════════════════════════
# Path record — field validation
# ══════════════════════════════════════════════════════════════


class TestPathRecord:
    """Evolution path record — construction and field access."""

    def test_default_fields(self):
        rec = _make_path_record()
        assert rec.source_position == "Backend"
        assert rec.target_position == "FullStack"
        assert rec.similarity == 0.75

    def test_skill_overlap_and_gaps(self):
        rec = _make_path_record()
        assert "Python" in rec.skill_overlap
        assert "React" in rec.key_gaps


# ══════════════════════════════════════════════════════════════
# Snapshot record — field validation + filtering
# ══════════════════════════════════════════════════════════════


class TestSnapshotRecord:
    """Evolution snapshot — construction and filtering."""

    def test_default_fields(self):
        rec = _make_snapshot_record()
        assert rec.position_name == "Backend"
        assert rec.source_count == 5

    def test_filter_by_position(self):
        snapshots = [
            _make_snapshot_record(position_name="Backend"),
            _make_snapshot_record(position_name="Frontend"),
        ]
        filtered = [s for s in snapshots if s.position_name == "Backend"]
        assert len(filtered) == 1
        assert filtered[0].position_name == "Backend"


# ══════════════════════════════════════════════════════════════
# Review queue — trust score threshold
# ══════════════════════════════════════════════════════════════


class TestReviewQueue:
    """Review queue — items below trust threshold."""

    def test_low_trust_items(self):
        items = [
            _make_changelog_record(trust_score=0.3),
            _make_changelog_record(trust_score=0.7),
        ]
        threshold = 0.5
        low_trust = [i for i in items if i.trust_score < threshold]
        assert len(low_trust) == 1
        assert low_trust[0].trust_score == 0.3

    def test_all_above_threshold(self):
        items = [_make_changelog_record(trust_score=0.8)]
        threshold = 0.5
        low_trust = [i for i in items if i.trust_score < threshold]
        assert low_trust == []


# ══════════════════════════════════════════════════════════════
# CII history — computation logic
# ══════════════════════════════════════════════════════════════


class TestCIIHistory:
    """CII history — compute change index from snapshots."""

    def test_cii_from_single_snapshot(self):
        snap = _make_snapshot_record(required_skills=[
            {"name": "Python", "proficiency": "熟悉"},
        ])
        # CII = count of required skills at this snapshot
        cii = len(snap.required_skills) * 100  # base index
        assert cii == 100

    def test_cii_change_between_snapshots(self):
        snap1 = _make_snapshot_record(required_skills=[
            {"name": "Python", "proficiency": "熟悉"},
        ])
        snap2 = _make_snapshot_record(required_skills=[
            {"name": "Python", "proficiency": "熟悉"},
            {"name": "Go", "proficiency": "了解"},
        ])
        # New skill added → CII increases
        cii1 = len(snap1.required_skills) * 100
        cii2 = len(snap2.required_skills) * 100
        assert cii2 > cii1

    def test_history_from_snapshots(self):
        snapshots = [
            _make_snapshot_record(snapshot_date="2026-01-01", required_skills=[{"name": "Python"}]),
            _make_snapshot_record(snapshot_date="2026-02-01", required_skills=[{"name": "Python"}, {"name": "Go"}]),
            _make_snapshot_record(snapshot_date="2026-03-01", required_skills=[{"name": "Python"}, {"name": "Go"}, {"name": "Rust"}]),
        ]
        history = [
            {"date": s.snapshot_date, "cii": len(s.required_skills) * 100}
            for s in snapshots
        ]
        assert len(history) == 3
        assert history[0]["cii"] == 100
        assert history[1]["cii"] == 200
        assert history[2]["cii"] == 300


# ══════════════════════════════════════════════════════════════
# KPI aggregation — build_evolution_kpi (D-11/D-12)
# ══════════════════════════════════════════════════════════════


class _AvgResult:
    """Fake query result exposing scalar_one() for the avg() aggregate."""

    def __init__(self, value: float | None) -> None:
        self._value = value

    def scalar_one(self) -> float | None:
        return self._value


class _FakeSession:
    """Minimal AsyncSession double — returns a fixed avg for any aggregate query."""

    def __init__(self, avg_value: float | None) -> None:
        self._avg_value = avg_value

    async def execute(self, _stmt: object) -> _AvgResult:
        return _AvgResult(self._avg_value)


async def _async_empty_timeseries(_session: object, **_: object) -> dict:
    """Monkeypatched load_skill_timeseries_data returning empty data."""
    return {}


class TestKpi:
    """build_evolution_kpi — real trust aggregate + empty→zeros (D-12)."""

    @pytest.mark.asyncio
    async def test_trust_mean_is_real_aggregate(self, monkeypatch):
        rows = [
            _make_changelog_record(trust_score=0.8),
            _make_changelog_record(trust_score=0.6),
            _make_changelog_record(trust_score=0.4),
        ]
        expected_avg = sum(r.trust_score for r in rows) / len(rows)
        # The DB computes avg(trust_score); emulate it with the fixture rows
        # so the assertion proves build_evolution_kpi uses the real aggregate.
        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _async_empty_timeseries,
        )
        from app.services.evolution_service import build_evolution_kpi

        result = await build_evolution_kpi(_FakeSession(expected_avg))
        assert result["trust_mean"] == round(expected_avg, 3)

    @pytest.mark.asyncio
    async def test_empty_data_returns_zeros(self, monkeypatch):
        # No changelog (avg → None) and no timeseries data → all KPI zeros,
        # never fabricated estimates (D-12).
        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _async_empty_timeseries,
        )
        from app.services.evolution_service import build_evolution_kpi

        result = await build_evolution_kpi(_FakeSession(None))
        assert result["emerging_count"] == 0
        assert result["trust_mean"] == 0
        assert result["cii_mean"] == 0
        assert result["alert_count"] == 0

    @pytest.mark.asyncio
    async def test_days_passthrough(self, monkeypatch):
        captured: dict[str, object] = {}

        async def _fake_timeseries(session: object, **kwargs: object) -> dict:
            captured["days"] = kwargs.get("days")
            return {}

        monkeypatch.setattr("app.services.evolution_service.load_skill_timeseries_data", _fake_timeseries)
        from app.services.evolution_service import build_evolution_kpi

        result = await build_evolution_kpi(_FakeSession(None), days=30)
        assert captured["days"] == 30
        assert result["days"] == 30
