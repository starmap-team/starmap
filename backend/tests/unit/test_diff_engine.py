"""DiffEngine unit tests — all 6 ChangeType branches + cold-start."""
from __future__ import annotations

from typing import Any

import pytest

from app.core.evolution.diff_engine import ChangeType, DiffEngine


class _FakeSnap:
    """Minimal stand-in for EvolutionSnapshot — only fields DiffEngine reads."""

    def __init__(self, required: list[dict], preferred: list[dict]) -> None:
        self.required_skills = required
        self.preferred_skills = preferred


@pytest.fixture
def engine():
    return DiffEngine()


def _skill(name: str, bucket: str = "required", count: int = 5) -> dict[str, Any]:
    """Build a snapshot skill dict in the format SnapshotManager writes."""
    return {"name": name, "category": "hard_skill", "mention_count": count, "proficiency": "熟悉"}


class TestColdStart:
    def test_old_none_classifies_all_as_added(self, engine):
        new = _FakeSnap(
            required=[_skill("Python"), _skill("Go")],
            preferred=[_skill("K8s")],
        )
        changes = engine.diff(None, new)
        types = {c.change_type for c in changes}
        assert types == {ChangeType.ADDED_REQUIRED, ChangeType.ADDED_PREFERRED}
        added_req = [c for c in changes if c.change_type == ChangeType.ADDED_REQUIRED]
        assert {c.skill_name for c in added_req} == {"Python", "Go"}
        assert all(c.old_requirement is None for c in changes)


class TestSixChangeTypes:
    def test_added_required(self, engine):
        old = _FakeSnap([], [])
        new = _FakeSnap([_skill("Python")], [])
        changes = engine.diff(old, new)
        assert any(
            c.change_type == ChangeType.ADDED_REQUIRED and c.skill_name == "Python"
            for c in changes
        )

    def test_added_preferred(self, engine):
        old = _FakeSnap([], [])
        new = _FakeSnap([], [_skill("Docker")])
        changes = engine.diff(old, new)
        added_pref = [c for c in changes if c.change_type == ChangeType.ADDED_PREFERRED]
        assert len(added_pref) == 1
        assert added_pref[0].skill_name == "Docker"

    def test_removed(self, engine):
        old = _FakeSnap([_skill("Python")], [])
        new = _FakeSnap([], [])
        changes = engine.diff(old, new)
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].skill_name == "Python"
        assert removed[0].old_requirement == "required"
        assert removed[0].new_requirement is None

    def test_promoted(self, engine):
        old = _FakeSnap([], [_skill("Rust")])
        new = _FakeSnap([_skill("Rust")], [])
        changes = engine.diff(old, new)
        promoted = [c for c in changes if c.change_type == ChangeType.PROMOTED]
        assert len(promoted) == 1
        assert promoted[0].old_requirement == "preferred"
        assert promoted[0].new_requirement == "required"

    def test_demoted(self, engine):
        old = _FakeSnap([_skill("Java")], [])
        new = _FakeSnap([], [_skill("Java")])
        changes = engine.diff(old, new)
        demoted = [c for c in changes if c.change_type == ChangeType.DEMOTED]
        assert len(demoted) == 1
        assert demoted[0].old_requirement == "required"
        assert demoted[0].new_requirement == "preferred"

    def test_retained(self, engine):
        old = _FakeSnap([_skill("Python")], [_skill("Docker")])
        new = _FakeSnap([_skill("Python")], [_skill("Docker")])
        changes = engine.diff(old, new)
        retained = [c for c in changes if c.change_type == ChangeType.RETAINED]
        assert len(retained) == 2
        retained_names = {c.skill_name for c in retained}
        assert retained_names == {"Python", "Docker"}


class TestNoOp:
    def test_both_empty(self, engine):
        changes = engine.diff(_FakeSnap([], []), _FakeSnap([], []))
        assert changes == []
