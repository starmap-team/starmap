"""Tests for learning progress tracker."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.learning.progress_tracker import (
    create_plan,
    get_plan_progress_list,
    get_progress,
    update_progress,
)
from app.models.learning_models import LearningPlan, LearningProgress


# ---------------------------------------------------------------------------
# Fake session infrastructure
# ---------------------------------------------------------------------------

class FakeScalarResult:
    def __init__(self, items: list):
        self._items = items

    def all(self) -> list:
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def one_or_none(self):
        return self._items[0] if self._items else None


class FakeResult:
    def __init__(self, items: list):
        self._scalars = FakeScalarResult(items)

    def scalars(self) -> FakeScalarResult:
        return self._scalars

    def scalar_one_or_none(self):
        return self._scalars._items[0] if self._scalars._items else None


class FakeAsyncSession:
    """Fake async session that tracks adds/commits and returns configurable query results."""

    def __init__(self, query_results: list | None = None):
        self._query_results = query_results or []
        self._added: list = []
        self._committed = False

    async def execute(self, stmt):
        return FakeResult(self._query_results)

    def add(self, obj):
        self._added.append(obj)

    async def flush(self):
        pass  # simulate ID assignment

    async def commit(self):
        self._committed = True

    async def refresh(self, obj):
        pass  # no-op; object already has fields set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(
    plan_id: uuid.UUID | None = None,
    position: str = "Backend Engineer",
    skills: list | None = None,
    status: str = "active",
    match_score: float = 0.5,
    estimated_hours: float = 100.0,
) -> LearningPlan:
    pid = plan_id or uuid.uuid4()
    now = datetime.now(UTC)
    plan = LearningPlan(
        id=pid,
        user_id="anonymous",
        position=position,
        skills=skills or [],
        status=status,
        match_score_at_creation=match_score,
        estimated_hours=estimated_hours,
        created_at=now,
        updated_at=now,
    )
    return plan


def _make_progress(
    plan_id: uuid.UUID,
    skill_name: str = "Python",
    status: str = "not_started",
    progress_pct: float = 0.0,
    importance: str = "required",
    estimated_hours: float = 20.0,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> LearningProgress:
    return LearningProgress(
        plan_id=plan_id,
        skill_name=skill_name,
        status=status,
        progress_pct=progress_pct,
        importance=importance,
        estimated_hours=estimated_hours,
        started_at=started_at,
        completed_at=completed_at,
    )


# ---------------------------------------------------------------------------
# create_plan
# ---------------------------------------------------------------------------
class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_creates_plan_with_skills(self):
        skills = [
            {"skill": "Python", "gap_level": "完全缺失", "importance": "required"},
            {"skill": "Docker", "gap_level": "部分掌握", "importance": "bonus"},
        ]
        session = FakeAsyncSession()
        plan = await create_plan(
            session,
            position="DevOps",
            skills=skills,
            user_id="user1",
            match_score=0.6,
            estimated_hours=80.0,
        )
        assert plan.position == "DevOps"
        assert plan.user_id == "user1"
        assert plan.status == "active"
        assert plan.match_score_at_creation == 0.6
        assert plan.estimated_hours == 80.0
        # 1 plan + 2 progress records added
        assert len(session._added) == 3
        assert isinstance(session._added[0], LearningPlan)
        assert isinstance(session._added[1], LearningProgress)
        assert isinstance(session._added[2], LearningProgress)

    @pytest.mark.asyncio
    async def test_mastered_skill_gets_100_pct(self):
        skills = [{"skill": "SQL", "gap_level": "已掌握", "importance": "required"}]
        session = FakeAsyncSession()
        plan = await create_plan(session, position="DBA", skills=skills)
        progress = session._added[1]
        assert progress.status == "mastered"
        assert progress.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_partial_gap_starts_not_started(self):
        skills = [{"skill": "Go", "gap_level": "部分掌握", "importance": "bonus"}]
        session = FakeAsyncSession()
        plan = await create_plan(session, position="SRE", skills=skills)
        progress = session._added[1]
        assert progress.status == "not_started"
        assert progress.progress_pct == 0.0

    @pytest.mark.asyncio
    async def test_empty_skill_name_skipped(self):
        skills = [{"skill": "", "gap_level": "完全缺失"}, {"skill": "Rust", "gap_level": "完全缺失"}]
        session = FakeAsyncSession()
        plan = await create_plan(session, position="Systems", skills=skills)
        # Only 1 plan + 1 progress (empty name skipped)
        assert len(session._added) == 2

    @pytest.mark.asyncio
    async def test_missing_skill_key_skipped(self):
        skills = [{"gap_level": "完全缺失"}, {"skill": "Rust", "gap_level": "完全缺失"}]
        session = FakeAsyncSession()
        plan = await create_plan(session, position="Systems", skills=skills)
        assert len(session._added) == 2  # plan + 1 progress

    @pytest.mark.asyncio
    async def test_default_values(self):
        skills = [{"skill": "Python", "gap_level": "完全缺失"}]
        session = FakeAsyncSession()
        plan = await create_plan(session, position="Eng", skills=skills)
        assert plan.user_id == "anonymous"
        assert plan.match_score_at_creation == 0.0
        assert plan.estimated_hours == 0.0
        progress = session._added[1]
        assert progress.estimated_hours == 0.0
        assert progress.importance == "required"  # default from skill_data.get


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------
class TestUpdateProgress:
    @pytest.mark.asyncio
    async def test_update_status_to_in_progress(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="Python", status="not_started", started_at=None)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="Python", status="in_progress")
        assert result.status == "in_progress"
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_mastered(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="Python", status="in_progress")
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="Python", status="mastered")
        assert result.status == "mastered"
        assert result.completed_at is not None
        assert result.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_update_progress_pct_auto_status(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="Go", status="not_started", progress_pct=0.0)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="Go", progress_pct=50.0)
        assert result.status == "in_progress"
        assert result.started_at is not None
        assert result.progress_pct == 50.0

    @pytest.mark.asyncio
    async def test_progress_pct_100_auto_mastered(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="Go", status="in_progress", progress_pct=50.0)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="Go", progress_pct=100.0)
        assert result.status == "mastered"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_progress_pct_clamped(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="X", progress_pct=50.0)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="X", progress_pct=150.0)
        assert result.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_progress_pct_negative_clamped(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="X", progress_pct=50.0)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="X", progress_pct=-10.0)
        assert result.progress_pct == 0.0

    @pytest.mark.asyncio
    async def test_update_notes(self):
        pid = uuid.uuid4()
        prog = _make_progress(plan_id=pid, skill_name="X")
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="X", notes="Studying")
        assert result.notes == "Studying"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        pid = uuid.uuid4()
        session = FakeAsyncSession(query_results=[])
        result = await update_progress(session, plan_id=pid, skill_name="Missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_complete_plan_when_all_mastered(self):
        pid = uuid.uuid4()
        prog1 = _make_progress(plan_id=pid, skill_name="A", status="mastered", progress_pct=100.0)
        prog2 = _make_progress(plan_id=pid, skill_name="B", status="in_progress", progress_pct=80.0)
        plan = _make_plan(plan_id=pid, status="active")

        # First call returns the progress record being updated,
        # get_plan_progress_list returns both records,
        # then plan query returns the plan
        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First query: find the progress record for skill B
                    return FakeResult([prog2])
                elif call_count[0] == 2:
                    # get_plan_progress_list query
                    return FakeResult([prog1, prog2])
                else:
                    # Plan query
                    return FakeResult([plan])

        # Update skill B to mastered → all mastered → auto-complete plan
        session = MultiQuerySession()
        prog2.status = "mastered"
        prog2.progress_pct = 100.0
        result = await update_progress(session, plan_id=pid, skill_name="B", status="mastered")
        assert plan.status == "completed"

    @pytest.mark.asyncio
    async def test_in_progress_does_not_overwrite_started_at(self):
        pid = uuid.uuid4()
        existing_time = datetime(2025, 1, 1, tzinfo=UTC)
        prog = _make_progress(plan_id=pid, skill_name="X", status="in_progress", started_at=existing_time)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="X", status="in_progress")
        # started_at should remain unchanged (already set)
        assert result.started_at == existing_time

    @pytest.mark.asyncio
    async def test_mastered_does_not_overwrite_completed_at(self):
        pid = uuid.uuid4()
        existing_time = datetime(2025, 1, 1, tzinfo=UTC)
        prog = _make_progress(plan_id=pid, skill_name="X", status="mastered", completed_at=existing_time)
        session = FakeAsyncSession(query_results=[prog])
        result = await update_progress(session, plan_id=pid, skill_name="X", status="mastered")
        assert result.completed_at == existing_time


# ---------------------------------------------------------------------------
# get_plan_progress_list
# ---------------------------------------------------------------------------
class TestGetPlanProgressList:
    @pytest.mark.asyncio
    async def test_returns_progress_list(self):
        pid = uuid.uuid4()
        p1 = _make_progress(plan_id=pid, skill_name="A")
        p2 = _make_progress(plan_id=pid, skill_name="B")
        session = FakeAsyncSession(query_results=[p1, p2])
        result = await get_plan_progress_list(session, plan_id=pid)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_plan(self):
        session = FakeAsyncSession(query_results=[])
        result = await get_plan_progress_list(session, plan_id=uuid.uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# get_progress (aggregated)
# ---------------------------------------------------------------------------
class TestGetProgress:
    @pytest.mark.asyncio
    async def test_plan_not_found(self):
        session = FakeAsyncSession(query_results=[])
        result = await get_progress(session, plan_id=uuid.uuid4())
        assert result == {"error": "Plan not found"}

    @pytest.mark.asyncio
    async def test_aggregated_progress(self):
        pid = uuid.uuid4()
        plan = _make_plan(plan_id=pid, position="Full Stack", match_score=0.7, estimated_hours=60.0)
        p1 = _make_progress(plan_id=pid, skill_name="Python", status="mastered", progress_pct=100.0, importance="required")
        p2 = _make_progress(plan_id=pid, skill_name="Docker", status="in_progress", progress_pct=50.0, importance="bonus")

        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeResult([plan])
                else:
                    return FakeResult([p1, p2])

        session = MultiQuerySession()
        result = await get_progress(session, plan_id=pid)
        assert result["plan_id"] == str(pid)
        assert result["position"] == "Full Stack"
        assert result["status"] == "active"
        assert result["match_score_at_creation"] == 0.7
        assert len(result["skills"]) == 2
        # weighted: required(2)*100 + bonus(1)*50 = 250, total_weight=3, pct=83.3
        assert result["overall_pct"] == 83.3

    @pytest.mark.asyncio
    async def test_stats_fields(self):
        pid = uuid.uuid4()
        plan = _make_plan(plan_id=pid)
        p1 = _make_progress(plan_id=pid, skill_name="A", status="mastered", importance="required")
        p2 = _make_progress(plan_id=pid, skill_name="B", status="in_progress", importance="required")
        p3 = _make_progress(plan_id=pid, skill_name="C", status="not_started", importance="bonus")

        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeResult([plan])
                else:
                    return FakeResult([p1, p2, p3])

        session = MultiQuerySession()
        result = await get_progress(session, plan_id=pid)
        stats = result["stats"]
        assert stats["total_skills"] == 3
        assert stats["mastered"] == 1
        assert stats["in_progress"] == 1
        assert stats["not_started"] == 1
        assert stats["required_total"] == 2
        assert stats["required_mastered"] == 1

    @pytest.mark.asyncio
    async def test_zero_weight_overall_pct(self):
        """Empty progress list → overall_pct = 0.0."""
        pid = uuid.uuid4()
        plan = _make_plan(plan_id=pid)

        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeResult([plan])
                else:
                    return FakeResult([])

        session = MultiQuerySession()
        result = await get_progress(session, plan_id=pid)
        assert result["overall_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_skill_dates_serialized(self):
        pid = uuid.uuid4()
        plan = _make_plan(plan_id=pid)
        started = datetime(2025, 6, 1, tzinfo=UTC)
        completed = datetime(2025, 6, 15, tzinfo=UTC)
        p1 = _make_progress(plan_id=pid, skill_name="X", started_at=started, completed_at=completed)

        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeResult([plan])
                else:
                    return FakeResult([p1])

        session = MultiQuerySession()
        result = await get_progress(session, plan_id=pid)
        skill = result["skills"][0]
        assert skill["started_at"] == started.isoformat()
        assert skill["completed_at"] == completed.isoformat()

    @pytest.mark.asyncio
    async def test_notes_in_skill_data(self):
        pid = uuid.uuid4()
        plan = _make_plan(plan_id=pid)
        p1 = _make_progress(plan_id=pid, skill_name="X")
        p1.notes = "review chapter 3"

        call_count = [0]

        class MultiQuerySession(FakeAsyncSession):
            async def execute(self, stmt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeResult([plan])
                else:
                    return FakeResult([p1])

        session = MultiQuerySession()
        result = await get_progress(session, plan_id=pid)
        assert result["skills"][0]["notes"] == "review chapter 3"
