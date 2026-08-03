"""SnapshotManager unit tests — pure-logic paths (no DB)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.evolution.snapshot_manager import (
    MIN_MENTIONS_PER_SKILL,
    SnapshotManager,
)


@pytest.fixture
def mgr():
    return SnapshotManager()


class TestMonthWindow:
    def test_january_wraps_to_next_year(self, mgr):
        start, end = mgr._month_window(datetime(2026, 1, 15, tzinfo=UTC))
        assert start == datetime(2026, 1, 1, tzinfo=UTC)
        assert end == datetime(2026, 2, 1, tzinfo=UTC)

    def test_december_advances_year(self, mgr):
        start, end = mgr._month_window(datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
        assert start == datetime(2026, 12, 1, tzinfo=UTC)
        assert end == datetime(2027, 1, 1, tzinfo=UTC)

    def test_naive_datetime_treated_as_utc(self, mgr):
        start, _ = mgr._month_window(datetime(2026, 7, 4))
        assert start.tzinfo == UTC


class TestNormalizeSkillEntries:
    def test_dict_entries(self, mgr):
        out = mgr._normalize_skill_entries([
            {"name": "Python", "category": "hard_skill"},
            {"name": "  Go  ", "category": "hard_skill"},
        ])
        assert {s["name"] for s in out} == {"Python", "Go"}

    def test_bare_strings(self, mgr):
        out = mgr._normalize_skill_entries(["Python", "Go", ""])
        assert len(out) == 2
        assert all(s["category"] == "general" for s in out)

    def test_empty_or_none(self, mgr):
        assert mgr._normalize_skill_entries(None) == []
        assert mgr._normalize_skill_entries([]) == []
        assert mgr._normalize_skill_entries([{}, {"name": ""}]) == []


class TestTopSkills:
    def test_filter_below_min_mentions(self, mgr):
        counts = {"Python": 5, "Go": 1, "Rust": MIN_MENTIONS_PER_SKILL}
        cat = {"Python": "hard", "Go": "hard", "Rust": "hard"}
        out = mgr._top_skills(counts, cat, MIN_MENTIONS_PER_SKILL)
        names = [s["name"] for s in out]
        assert "Python" in names
        assert "Rust" in names
        assert "Go" not in names  # 1 mention < MIN_MENTIONS_PER_SKILL=2

    def test_sorted_by_mention_count_desc(self, mgr):
        counts = {"A": 3, "B": 10, "C": 5}
        cat = {"A": "x", "B": "x", "C": "x"}
        out = mgr._top_skills(counts, cat, min_mentions=1)
        assert [s["name"] for s in out] == ["B", "C", "A"]
        assert out[0]["mention_count"] == 10
