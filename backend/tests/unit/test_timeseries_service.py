"""Unit tests for timeseries_service.refresh_skill_timeseries.

Tests the aggregation logic with a fake AsyncSession that returns
pre-configured JDExtractionRecord and SkillRecord results.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.timeseries_service import (
    _build_monthly_windows,
    _extract_skill_names,
    refresh_skill_timeseries,
)


# ── Fake ORM objects ──


class FakeExtractionRecord:
    """Mimics JDExtractionRecord with minimal fields."""

    def __init__(
        self,
        job_title: str = "Backend Engineer",
        extracted_skills: dict | list | None = None,
        created_at: datetime | None = None,
        status: str = "completed",
    ):
        self.job_title = job_title
        self.extracted_skills = extracted_skills or {}
        self.created_at = created_at or datetime(2025, 6, 15, tzinfo=UTC)
        self.status = status


class FakeSkillRecord:
    """Mimics SkillRecord."""

    def __init__(self, name: str = "Python", category: str = "programming"):
        self.name = name
        self.category = category


class FakeTimeseriesRecord:
    """Mimics SkillTimeseries for deletion tracking."""

    def __init__(self, skill_name: str = "Python"):
        self.skill_name = skill_name


# ── Fake session ──


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value

    def one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]


class FakeSession:
    """Minimal async session for timeseries_service tests."""

    def __init__(self, extraction_records=None, skill_records=None):
        self._extraction_records = extraction_records or []
        self._skill_records = skill_records or []
        self._added = []
        self._deleted = []
        self._flushed = False

    async def execute(self, stmt):
        # Detect which query by inspecting the string representation
        stmt_str = str(stmt)

        # Date range query (min/max of JDExtractionRecord.created_at)
        if "min" in stmt_str and "max" in stmt_str:
            completed = [r for r in self._extraction_records if r.status == "completed"]
            if not completed:
                return FakeResult((None, None))
            dates = [r.created_at for r in completed]
            return FakeResult((min(dates), max(dates)))

        # SkillRecord category query
        if "skill_records" in stmt_str and "name" in stmt_str:
            return FakeResult([(s.name, s.category) for s in self._skill_records])

        # JDExtractionRecord filtered query (per window)
        # We return all records and let the service filter
        # This is a simplification — the service filters by date range
        return FakeResult(self._extraction_records)

    def add(self, obj):
        self._added.append(obj)

    async def flush(self):
        self._flushed = True

    async def delete(self, model_cls):
        """Track deletions (called for clearing old timeseries per window)."""
        pass


# ── Tests for _build_monthly_windows ──


class TestBuildMonthlyWindows:
    def test_single_month(self):
        start = datetime(2025, 6, 5, tzinfo=UTC)
        end = datetime(2025, 6, 20, tzinfo=UTC)
        windows = _build_monthly_windows(start, end)
        assert len(windows) == 1
        assert windows[0][0] == datetime(2025, 6, 1, tzinfo=UTC)
        assert windows[0][1] == datetime(2025, 7, 1, tzinfo=UTC)

    def test_cross_month(self):
        start = datetime(2025, 5, 15, tzinfo=UTC)
        end = datetime(2025, 7, 10, tzinfo=UTC)
        windows = _build_monthly_windows(start, end)
        assert len(windows) == 3
        # May, June, July
        assert windows[0][0].month == 5
        assert windows[1][0].month == 6
        assert windows[2][0].month == 7

    def test_cross_year(self):
        start = datetime(2024, 12, 15, tzinfo=UTC)
        end = datetime(2025, 1, 10, tzinfo=UTC)
        windows = _build_monthly_windows(start, end)
        assert len(windows) == 2
        assert windows[0][0].year == 2024 and windows[0][0].month == 12
        assert windows[1][0].year == 2025 and windows[1][0].month == 1


# ── Tests for _extract_skill_names ──


class TestExtractSkillNames:
    def test_list_of_dicts(self):
        rec = FakeExtractionRecord(
            extracted_skills=[{"name": "Python"}, {"name": "Go"}],
        )
        names = _extract_skill_names(rec)
        assert names == ["Python", "Go"]

    def test_list_of_strings(self):
        rec = FakeExtractionRecord(
            extracted_skills=["Python", "Go"],
        )
        names = _extract_skill_names(rec)
        assert names == ["Python", "Go"]

    def test_dict_with_required_preferred(self):
        rec = FakeExtractionRecord(
            extracted_skills={
                "required_skills": [{"name": "Python"}],
                "preferred_skills": [{"name": "Docker"}],
            },
        )
        names = _extract_skill_names(rec)
        assert "Python" in names
        assert "Docker" in names

    def test_dict_with_skills_key(self):
        rec = FakeExtractionRecord(
            extracted_skills={"skills": ["Python", "Go"]},
        )
        names = _extract_skill_names(rec)
        assert names == ["Python", "Go"]

    def test_empty(self):
        rec = FakeExtractionRecord(extracted_skills=None)
        names = _extract_skill_names(rec)
        assert names == []

    def test_empty_list(self):
        rec = FakeExtractionRecord(extracted_skills=[])
        names = _extract_skill_names(rec)
        assert names == []


# ── Tests for refresh_skill_timeseries ──


class TestRefreshSkillTimeseries:
    @pytest.mark.asyncio
    async def test_no_records_returns_zero(self):
        session = FakeSession(extraction_records=[])
        result = await refresh_skill_timeseries(session)
        assert result["skills_updated"] == 0
        assert result["windows_created"] == 0

    @pytest.mark.asyncio
    async def test_with_records_creates_windows(self):
        records = [
            FakeExtractionRecord(
                job_title="Backend Engineer",
                extracted_skills=[{"name": "Python"}, {"name": "Go"}],
                created_at=datetime(2025, 6, 15, tzinfo=UTC),
            ),
            FakeExtractionRecord(
                job_title="Frontend Developer",
                extracted_skills=[{"name": "Python"}, {"name": "Vue"}],
                created_at=datetime(2025, 6, 20, tzinfo=UTC),
            ),
        ]
        skills = [
            FakeSkillRecord(name="Python", category="programming"),
            FakeSkillRecord(name="Go", category="programming"),
            FakeSkillRecord(name="Vue", category="framework"),
        ]
        session = FakeSession(extraction_records=records, skill_records=skills)
        result = await refresh_skill_timeseries(session)
        # Should have processed some skills
        assert result["skills_updated"] > 0
        assert result["windows_created"] > 0

    @pytest.mark.asyncio
    async def test_non_completed_records_ignored(self):
        # Only status="completed" records should be counted
        records = [
            FakeExtractionRecord(
                extracted_skills=[{"name": "Python"}],
                created_at=datetime(2025, 6, 15, tzinfo=UTC),
                status="pending",  # not completed
            ),
        ]
        session = FakeSession(extraction_records=records)
        result = await refresh_skill_timeseries(session)
        # The date range query filters by status="completed",
        # so with only pending records, min_date should be None → returns zero
        assert result["skills_updated"] == 0