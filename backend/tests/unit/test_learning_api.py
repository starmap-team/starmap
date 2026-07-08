"""Unit tests for learning API endpoints and learning_service.

Covers:
- GET  /api/v1/learning/plans
- POST /api/v1/learning/plan
- GET  /api/v1/learning/plan/{plan_id}
- PUT  /api/v1/learning/plan/{plan_id}/progress
- POST /api/v1/learning/plan/{plan_id}/skills
- GET  /api/v1/learning/recommendations
- learning_service.create_plan_from_match
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db_session
from app.main import app

# ── Fake DB primitives ──


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        v = self.value
        if isinstance(v, (list, tuple)) and len(v) == 1:
            return v[0]
        return v

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def first(self):
        return self.value


class FakePlanRow:
    """Mimics a LearningPlan ORM instance."""

    def __init__(
        self,
        plan_id=None,
        user_id="dev",
        position="数据分析师",
        skills=None,
        status="active",
        match_score_at_creation=0.5,
        estimated_hours=60.0,
    ):
        self.id = plan_id or uuid.uuid4()
        self.user_id = user_id
        self.position = position
        # ponytail: explicit sentinel to distinguish "passed []" from "not passed"
        self.skills = (
            skills
            if skills is not None
            else [
                {
                    "skill": "Python",
                    "importance": "required",
                    "gap_level": "完全缺失",
                    "learning_path": [],
                    "estimated_hours": 40.0,
                },
            ]
        )
        self.status = status
        self.match_score_at_creation = match_score_at_creation
        self.estimated_hours = estimated_hours
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class FakeProgressRow:
    """Mimics a LearningProgress ORM instance."""

    def __init__(
        self,
        plan_id=None,
        skill_name="Python",
        status="not_started",
        progress_pct=0.0,
        importance="required",
        estimated_hours=40.0,
        notes=None,
    ):
        self.id = uuid.uuid4()
        self.plan_id = plan_id or uuid.uuid4()
        self.skill_name = skill_name
        self.status = status
        self.progress_pct = progress_pct
        self.importance = importance
        self.estimated_hours = estimated_hours
        self.notes = notes
        self.started_at = None
        self.completed_at = None
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class FakeAsyncSession:
    """Minimal async session that returns pre-configured results per execute call."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self._idx = 0
        self._added = []
        self._committed = False

    async def execute(self, _stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult(None)

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


def _make_db_override(session: FakeAsyncSession):
    async def _override():
        yield session

    return _override


# ── Shared mock data ──

_MOCK_USER = {"sub": "dev", "role": "admin", "username": "developer"}

_MOCK_LEARNING_PATH = type(
    "LearningPath",
    (),
    {
        "skills": [type("SkillNode", (), {"name": "Python", "estimated_hours": 40.0})()],
        "total_hours": 40.0,
        "total_weeks": 4,
        "weekly_hours": 10.0,
        "phase_count": 1,
        "phases": [{"phase": 1, "skills": ["Python"], "estimated_hours": 40.0, "estimated_weeks": 4.0}],
    },
)()

_MOCK_PROGRESS_DATA = {
    "overall_pct": 0.0,
    "skills": [
        {
            "skill_name": "Python",
            "status": "not_started",
            "progress_pct": 0.0,
            "importance": "required",
            "estimated_hours": 40.0,
            "started_at": None,
            "completed_at": None,
            "notes": None,
        },
    ],
    "stats": {
        "total_skills": 1,
        "mastered": 0,
        "in_progress": 0,
        "not_started": 1,
        "required_total": 1,
        "required_mastered": 0,
        "estimated_hours_total": 40.0,
    },
}


# ── Fixtures ──


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token"}


@pytest.fixture
def db_override():
    """Override get_db_session. Returns a setter function."""

    def _set(session: FakeAsyncSession | None):
        if session is None:
            app.dependency_overrides.pop(get_db_session, None)
        else:
            app.dependency_overrides[get_db_session] = _make_db_override(session)

    yield _set
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture(autouse=True)
def _override_user():
    """Override get_current_user to return dev user (dev-mode bypass)."""
    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ══════════════════════════════════════════════════════════════
# GET /api/v1/learning/plans
# ══════════════════════════════════════════════════════════════


class TestListPlans:
    def test_empty_plans_returns_200(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)):
            resp = client.get("/api/v1/learning/plans", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_plans_with_data_returns_200(self, client, auth_headers, db_override):
        plan = FakePlanRow()
        session = FakeAsyncSession([FakeResult([plan])])
        db_override(session)
        with (
            patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)),
            patch("app.api.v1.learning.generate_learning_path", new=AsyncMock(return_value=_MOCK_LEARNING_PATH)),
        ):
            resp = client.get("/api/v1/learning/plans", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["position"] == "数据分析师"
        assert body[0]["plan_id"] == str(plan.id)

    def test_plans_with_empty_skills_uses_fallback(self, client, auth_headers, db_override):
        plan = FakePlanRow(skills=[])
        session = FakeAsyncSession([FakeResult([plan])])
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)):
            resp = client.get("/api/v1/learning/plans", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["total_hours"] == plan.estimated_hours
        assert body[0]["phases"] == []

    def test_plans_generate_path_error_uses_fallback(self, client, auth_headers, db_override):
        plan = FakePlanRow()
        session = FakeAsyncSession([FakeResult([plan])])
        db_override(session)
        with (
            patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)),
            patch("app.api.v1.learning.generate_learning_path", new=AsyncMock(side_effect=Exception("path error"))),
        ):
            resp = client.get("/api/v1/learning/plans", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["total_hours"] == plan.estimated_hours

    def test_plans_limit_param(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)):
            resp = client.get("/api/v1/learning/plans?limit=5", headers=auth_headers)
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# POST /api/v1/learning/plan
# ══════════════════════════════════════════════════════════════


class TestCreatePlan:
    def test_create_plan_returns_200(self, client, auth_headers, db_override):
        plan = FakePlanRow()
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.learning.generate_learning_path", new=AsyncMock(return_value=_MOCK_LEARNING_PATH)),
            patch("app.api.v1.learning.create_plan", new=AsyncMock(return_value=plan)),
            patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)),
        ):
            resp = client.post(
                "/api/v1/learning/plan",
                headers=auth_headers,
                json={
                    "position": "数据分析师",
                    "match_score": 0.5,
                    "skills": [{"skill": "Python", "importance": "required", "gap_level": "完全缺失"}],
                    "available_hours_per_week": 10.0,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["position"] == "数据分析师"
        assert "plan_id" in body
        assert body["total_hours"] == 40.0

    def test_create_plan_empty_skills_returns_422(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/learning/plan",
            headers=auth_headers,
            json={
                "position": "数据分析师",
                "skills": [],
            },
        )
        assert resp.status_code == 422

    def test_create_plan_empty_position_required(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/learning/plan",
            headers=auth_headers,
            json={
                "skills": [{"skill": "Python"}],
            },
        )
        assert resp.status_code == 422

    def test_match_score_out_of_range(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/learning/plan",
            headers=auth_headers,
            json={
                "position": "数据分析师",
                "match_score": 2.0,
                "skills": [{"skill": "Python"}],
            },
        )
        assert resp.status_code == 422

    def test_available_hours_out_of_range(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/learning/plan",
            headers=auth_headers,
            json={
                "position": "数据分析师",
                "skills": [{"skill": "Python"}],
                "available_hours_per_week": 0.5,
            },
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# GET /api/v1/learning/plan/{plan_id}
# ══════════════════════════════════════════════════════════════


class TestGetPlan:
    def test_get_plan_returns_200(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        plan = FakePlanRow(plan_id=plan_id, user_id="dev")
        session = FakeAsyncSession([FakeResult(plan)])
        db_override(session)
        with (
            patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)),
            patch("app.api.v1.learning.generate_learning_path", new=AsyncMock(return_value=_MOCK_LEARNING_PATH)),
        ):
            resp = client.get(f"/api/v1/learning/plan/{plan_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_id"] == str(plan_id)
        assert body["position"] == "数据分析师"

    def test_get_plan_invalid_uuid_returns_400(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.get("/api/v1/learning/plan/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 400
        assert "Invalid plan_id format" in resp.json()["detail"]

    def test_get_plan_not_found_returns_404(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value={"error": "Plan not found"})):
            resp = client.get(f"/api/v1/learning/plan/{plan_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_plan_wrong_user_returns_403(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        plan = FakePlanRow(plan_id=plan_id, user_id="other-user")
        session = FakeAsyncSession([FakeResult(plan)])
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)):
            resp = client.get(f"/api/v1/learning/plan/{plan_id}", headers=auth_headers)
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    def test_get_plan_db_plan_not_found_returns_404(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        with patch("app.api.v1.learning.get_progress", new=AsyncMock(return_value=_MOCK_PROGRESS_DATA)):
            resp = client.get(f"/api/v1/learning/plan/{plan_id}", headers=auth_headers)
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# PUT /api/v1/learning/plan/{plan_id}/progress
# ══════════════════════════════════════════════════════════════


class TestUpdateProgress:
    def test_update_progress_returns_200(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        progress = FakeProgressRow(plan_id=plan_id, skill_name="Python", status="in_progress", progress_pct=50.0)
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.learning.update_progress", new=AsyncMock(return_value=progress)):
            resp = client.put(
                f"/api/v1/learning/plan/{plan_id}/progress",
                headers=auth_headers,
                json={"skill_name": "Python", "status": "in_progress", "progress_pct": 50.0},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill_name"] == "Python"
        assert body["status"] == "in_progress"
        assert body["progress_pct"] == 50.0

    def test_update_progress_invalid_uuid_returns_400(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.put(
            "/api/v1/learning/plan/bad-uuid/progress",
            headers=auth_headers,
            json={"skill_name": "Python", "status": "in_progress"},
        )
        assert resp.status_code == 400

    def test_update_progress_skill_not_found_returns_404(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.learning.update_progress", new=AsyncMock(return_value=None)):
            resp = client.put(
                f"/api/v1/learning/plan/{plan_id}/progress",
                headers=auth_headers,
                json={"skill_name": "NonexistentSkill", "status": "in_progress"},
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_update_progress_with_notes(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        progress = FakeProgressRow(
            plan_id=plan_id, skill_name="Python", status="in_progress", progress_pct=30.0, notes="studying"
        )
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.learning.update_progress", new=AsyncMock(return_value=progress)):
            resp = client.put(
                f"/api/v1/learning/plan/{plan_id}/progress",
                headers=auth_headers,
                json={"skill_name": "Python", "progress_pct": 30.0, "notes": "studying"},
            )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "studying"

    def test_update_progress_mastered_skill(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        progress = FakeProgressRow(plan_id=plan_id, skill_name="Python", status="mastered", progress_pct=100.0)
        progress.completed_at = datetime.now(UTC)
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.learning.update_progress", new=AsyncMock(return_value=progress)):
            resp = client.put(
                f"/api/v1/learning/plan/{plan_id}/progress",
                headers=auth_headers,
                json={"skill_name": "Python", "status": "mastered"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "mastered"
        assert body["completed_at"] is not None

    def test_update_progress_pct_out_of_range_returns_422(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        resp = client.put(
            f"/api/v1/learning/plan/{plan_id}/progress",
            headers=auth_headers,
            json={"skill_name": "Python", "progress_pct": 150.0},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# POST /api/v1/learning/plan/{plan_id}/skills
# ══════════════════════════════════════════════════════════════


class TestAddSkillToPlan:
    def test_add_skill_returns_200(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        plan = FakePlanRow(plan_id=plan_id, skills=[])
        session = FakeAsyncSession([FakeResult(plan), FakeResult(None)])
        db_override(session)
        resp = client.post(
            f"/api/v1/learning/plan/{plan_id}/skills",
            headers=auth_headers,
            json={"skill_name": "Docker", "importance": "bonus", "estimated_hours": 20.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill_name"] == "Docker"
        assert body["status"] == "not_started"
        assert body["progress_pct"] == 0.0

    def test_add_skill_invalid_uuid_returns_400(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/learning/plan/bad-uuid/skills",
            headers=auth_headers,
            json={"skill_name": "Docker"},
        )
        assert resp.status_code == 400

    def test_add_skill_plan_not_found_returns_404(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.post(
            f"/api/v1/learning/plan/{plan_id}/skills",
            headers=auth_headers,
            json={"skill_name": "Docker"},
        )
        assert resp.status_code == 404

    def test_add_skill_already_exists_returns_existing(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        plan = FakePlanRow(plan_id=plan_id)
        existing = FakeProgressRow(plan_id=plan_id, skill_name="Python", status="in_progress", progress_pct=50.0)
        session = FakeAsyncSession([FakeResult(plan), FakeResult(existing)])
        db_override(session)
        resp = client.post(
            f"/api/v1/learning/plan/{plan_id}/skills",
            headers=auth_headers,
            json={"skill_name": "Python"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill_name"] == "Python"
        assert body["status"] == "in_progress"

    def test_add_skill_empty_name_returns_422(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            f"/api/v1/learning/plan/{plan_id}/skills",
            headers=auth_headers,
            json={"skill_name": ""},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# GET /api/v1/learning/recommendations
# ══════════════════════════════════════════════════════════════


class TestGetRecommendations:
    def test_recommendations_no_params_returns_200(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        with patch("app.api.v1.learning.SkillRecord", create=True):
            resp = client.get("/api/v1/learning/recommendations", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total_items" in body

    def test_recommendations_with_plan_id_returns_200(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        progress = FakeProgressRow(
            plan_id=plan_id, skill_name="Python", status="not_started", progress_pct=0.0, importance="required"
        )
        session = FakeAsyncSession([FakeResult([progress])])
        db_override(session)
        with patch("app.api.v1.learning.PREREQUISITE_MAP", {"Python": ["基础编程"]}):
            resp = client.get(f"/api/v1/learning/recommendations?plan_id={plan_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_items"] >= 1
        assert body["items"][0]["skill"] == "Python"
        assert "必备技能" in body["items"][0]["reason"]

    def test_recommendations_invalid_plan_id_returns_400(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.get("/api/v1/learning/recommendations?plan_id=bad-uuid", headers=auth_headers)
        assert resp.status_code == 400

    def test_recommendations_with_position_no_graph_returns_empty(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.services.graph_service.fetch_position_graph", new=AsyncMock(side_effect=Exception("no graph"))),
            patch("app.services.resources.resources") as mock_res,
        ):
            mock_res.neo4j_driver = None
            resp = client.get("/api/v1/learning/recommendations?position=数据分析师", headers=auth_headers)
        # ponytail: position path needs neo4j; without it returns empty
        assert resp.status_code == 200
        assert resp.json()["total_items"] == 0

    def test_recommendations_with_position_and_graph(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch(
                "app.services.graph_service.fetch_position_graph",
                new=AsyncMock(
                    return_value={
                        "skills": [
                            {"name": "Python", "properties": {"importance": "required"}},
                            {"name": "Docker", "properties": {"importance": "bonus"}},
                        ],
                    }
                ),
            ),
            patch("app.services.resources.resources") as mock_res,
        ):
            mock_res.neo4j_driver = MagicMock()
            resp = client.get("/api/v1/learning/recommendations?position=后端开发工程师", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_items"] == 2
        skills = [i["skill"] for i in body["items"]]
        assert "Python" in skills
        assert "Docker" in skills

    def test_recommendations_plan_id_filters_mastered(self, client, auth_headers, db_override):
        plan_id = uuid.uuid4()
        not_started = FakeProgressRow(plan_id=plan_id, skill_name="Python", status="not_started", progress_pct=0.0)
        session = FakeAsyncSession([FakeResult([not_started])])
        db_override(session)
        with patch("app.api.v1.learning.PREREQUISITE_MAP", {}):
            resp = client.get(f"/api/v1/learning/recommendations?plan_id={plan_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        skill_names = [i["skill"] for i in body["items"]]
        assert "SQL" not in skill_names


# ══════════════════════════════════════════════════════════════
# learning_service.create_plan_from_match
# ══════════════════════════════════════════════════════════════


class TestCreatePlanFromMatch:
    @pytest.mark.asyncio
    async def test_create_plan_from_match_success(self):
        from app.services.learning_service import create_plan_from_match

        session = FakeAsyncSession()
        plan = FakePlanRow()
        match_result = {
            "match_score": 0.6,
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": []},
                {"skill": "SQL", "importance": "required", "gap_level": "部分掌握", "learning_path": []},
            ],
        }
        with (
            patch(
                "app.services.learning_service.generate_learning_path", new=AsyncMock(return_value=_MOCK_LEARNING_PATH)
            ),
            patch("app.services.learning_service.create_plan", new=AsyncMock(return_value=plan)),
        ):
            result = await create_plan_from_match(
                session,
                target_position="数据分析师",
                match_result=match_result,
                user_id="dev",
            )
        assert result["position"] == "数据分析师"
        assert result["status"] == "active"
        assert "plan_id" in result

    @pytest.mark.asyncio
    async def test_create_plan_from_match_no_gaps_raises(self):
        from app.services.learning_service import create_plan_from_match

        session = FakeAsyncSession()
        match_result = {"skill_gap_detail": []}
        with pytest.raises(ValueError, match="No skill gaps"):
            await create_plan_from_match(
                session,
                target_position="数据分析师",
                match_result=match_result,
            )

    @pytest.mark.asyncio
    async def test_create_plan_from_match_all_mastered_returns_no_gaps(self):
        from app.services.learning_service import create_plan_from_match

        session = FakeAsyncSession()
        match_result = {
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "已掌握", "learning_path": []},
            ],
        }
        result = await create_plan_from_match(
            session,
            target_position="数据分析师",
            match_result=match_result,
        )
        assert result["status"] == "no_gaps"
        assert result["plan_id"] is None

    @pytest.mark.asyncio
    async def test_create_plan_from_match_filters_mastered(self):
        from app.services.learning_service import create_plan_from_match

        session = FakeAsyncSession()
        plan = FakePlanRow()
        match_result = {
            "match_score": 0.7,
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "已掌握", "learning_path": []},
                {"skill": "SQL", "importance": "required", "gap_level": "完全缺失", "learning_path": []},
            ],
        }
        mock_path = type(
            "LearningPath",
            (),
            {
                "skills": [type("SkillNode", (), {"name": "SQL", "estimated_hours": 30.0})()],
                "total_hours": 30.0,
                "total_weeks": 3,
                "phase_count": 1,
            },
        )()
        with (
            patch("app.services.learning_service.generate_learning_path", new=AsyncMock(return_value=mock_path)),
            patch("app.services.learning_service.create_plan", new=AsyncMock(return_value=plan)),
        ):
            result = await create_plan_from_match(
                session,
                target_position="数据分析师",
                match_result=match_result,
            )
        assert result["total_skills"] == 1
