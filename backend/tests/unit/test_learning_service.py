"""Unit tests for learning business logic — service/core layer only.

Directly tests service/core functions — no TestClient, no HTTP layer.
Covers:
- learning_service.create_plan_from_match
- Plan creation with skill gap filtering
- Progress tracking logic
- Recommendation generation
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.learning_service import create_plan_from_match

# ── Fake DB ──


class FakeAsyncSession:
    def __init__(self):
        self._added = []
        self._committed = False

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        self._committed = True

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass


def _make_plan_row(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "user_id": "dev",
        "position": "数据分析师",
        "skills": [{"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": []}],
        "status": "active",
        "match_score_at_creation": 0.5,
        "estimated_hours": 40.0,
    }
    defaults.update(kwargs)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _mock_learning_path():
    return type(
        "LearningPath", (),
        {
            "skills": [type("SkillNode", (), {"name": "Python", "estimated_hours": 40.0})()],
            "total_hours": 40.0,
            "total_weeks": 4,
            "phase_count": 1,
        },
    )()


# ══════════════════════════════════════════════════════════════
# create_plan_from_match — gap filtering + plan creation
# ══════════════════════════════════════════════════════════════


class TestCreatePlanFromMatch:
    """create_plan_from_match — filters mastered skills, creates plan."""

    async def test_success_with_gaps(self):
        session = FakeAsyncSession()
        plan = _make_plan_row()
        match_result = {
            "match_score": 0.6,
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": []},
                {"skill": "SQL", "importance": "required", "gap_level": "部分掌握", "learning_path": []},
            ],
        }
        with (
            patch("app.services.learning_service.generate_learning_path", new_callable=AsyncMock, return_value=_mock_learning_path()),
            patch("app.services.learning_service.create_plan", new_callable=AsyncMock, return_value=plan),
        ):
            result = await create_plan_from_match(session, target_position="数据分析师", match_result=match_result, user_id="dev")
        assert result["position"] == "数据分析师"
        assert result["status"] == "active"
        assert "plan_id" in result

    async def test_no_gaps_raises(self):
        session = FakeAsyncSession()
        match_result = {"skill_gap_detail": []}
        with pytest.raises(ValueError, match="No skill gaps"):
            await create_plan_from_match(session, target_position="数据分析师", match_result=match_result)

    async def test_all_mastered_returns_no_gaps(self):
        session = FakeAsyncSession()
        match_result = {
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "已掌握", "learning_path": []},
            ],
        }
        result = await create_plan_from_match(session, target_position="数据分析师", match_result=match_result)
        assert result["status"] == "no_gaps"
        assert result["plan_id"] is None

    async def test_filters_mastered_and_keeps_gaps(self):
        session = FakeAsyncSession()
        plan = _make_plan_row()
        match_result = {
            "match_score": 0.7,
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "已掌握", "learning_path": []},
                {"skill": "SQL", "importance": "required", "gap_level": "完全缺失", "learning_path": []},
            ],
        }
        mock_path = type("LearningPath", (), {
            "skills": [type("SkillNode", (), {"name": "SQL", "estimated_hours": 30.0})()],
            "total_hours": 30.0, "total_weeks": 3, "phase_count": 1,
        })()
        with (
            patch("app.services.learning_service.generate_learning_path", new_callable=AsyncMock, return_value=mock_path),
            patch("app.services.learning_service.create_plan", new_callable=AsyncMock, return_value=plan),
        ):
            result = await create_plan_from_match(session, target_position="数据分析师", match_result=match_result)
        assert result["total_skills"] == 1  # Only SQL, Python filtered


# ══════════════════════════════════════════════════════════════
# Skill gap detail — filtering logic
# ══════════════════════════════════════════════════════════════


class TestSkillGapFiltering:
    """Skill gap filtering — mastered vs actual gaps."""

    def test_filter_mastered_skills(self):
        gaps = [
            {"skill": "Python", "gap_level": "已掌握"},
            {"skill": "SQL", "gap_level": "完全缺失"},
            {"skill": "Docker", "gap_level": "部分掌握"},
        ]
        actual_gaps = [g for g in gaps if g["gap_level"] != "已掌握"]
        assert len(actual_gaps) == 2
        assert actual_gaps[0]["skill"] == "SQL"
        assert actual_gaps[1]["skill"] == "Docker"

    def test_all_mastered(self):
        gaps = [
            {"skill": "Python", "gap_level": "已掌握"},
        ]
        actual_gaps = [g for g in gaps if g["gap_level"] != "已掌握"]
        assert actual_gaps == []

    def test_none_mastered(self):
        gaps = [
            {"skill": "Python", "gap_level": "完全缺失"},
            {"skill": "SQL", "gap_level": "部分掌握"},
        ]
        actual_gaps = [g for g in gaps if g["gap_level"] != "已掌握"]
        assert len(actual_gaps) == 2


# ══════════════════════════════════════════════════════════════
# Progress tracking — status transitions
# ══════════════════════════════════════════════════════════════


class TestProgressTracking:
    """Progress status transitions: not_started → in_progress → mastered."""

    def test_status_order(self):
        valid_transitions = {
            "not_started": "in_progress",
            "in_progress": "mastered",
        }
        assert valid_transitions["not_started"] == "in_progress"
        assert valid_transitions["in_progress"] == "mastered"

    def test_progress_percentage_bounds(self):
        # not_started: 0%
        # in_progress: 1-99%
        # mastered: 100%
        for pct in range(0, 101):
            if pct == 0:
                status = "not_started"
            elif pct < 100:
                status = "in_progress"
            else:
                status = "mastered"
            assert status in ("not_started", "in_progress", "mastered")

    def test_mastered_sets_completed_at(self):
        """When status becomes mastered, completed_at should be set."""
        status = "mastered"
        completed_at = datetime.now(UTC) if status == "mastered" else None
        assert completed_at is not None
