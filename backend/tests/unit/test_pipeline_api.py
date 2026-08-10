"""Unit tests for pipeline API endpoints.

Covers core endpoints from backend/app/api/v1/pipeline/routes.py:
- GET  /status
- GET  /runs, GET /runs/{run_id}
- POST /trigger
- POST /runs/{run_id}/cancel, /retry, /resume
- GET  /stages, /data-quality, /datasources
- GET  /schedules, POST /schedules, PUT /schedules/{id}, DELETE /schedules/{id}
- POST /schedules/{id}/trigger
- GET  /config, PUT /config
- GET  /events-poll

Uses FastAPI TestClient + dependency_overrides (same pattern as test_admin_endpoints.py).
SSE /events endpoint skipped — streaming is hard to test meaningfully with TestClient.

Note: routes.py uses lazy imports (from X import Y inside handler bodies), so
we patch the source modules, not the routes module.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db_session, get_neo4j_driver, require_admin
from app.main import app

# ── Fake DB primitives (reused from test_admin_endpoints.py pattern) ──


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

    async def delete(self, obj):
        pass

    async def rollback(self):
        pass


def _make_db_override(session: FakeAsyncSession):
    async def _override():
        yield session
    return _override


# ── Fake ORM rows ──


class FakePipelineRun:
    """Mimics a PipelineRun ORM instance."""
    def __init__(
        self,
        run_id=None,
        run_type="full",
        status="running",
        started_at=None,
        completed_at=None,
        stages=None,
        total_records=0,
        new_records=0,
        updated_records=0,
        quality_score=0.0,
        error_log=None,
        selected_stages=None,
    ):
        self.id = run_id or uuid.uuid4()
        self.run_type = run_type
        self.status = status
        self.started_at = started_at or datetime.now(UTC)
        self.completed_at = completed_at
        self.stages = stages if stages is not None else []
        self.total_records = total_records
        self.new_records = new_records
        self.updated_records = updated_records
        self.quality_score = quality_score
        self.error_log = error_log
        self.selected_stages = selected_stages


class FakePipelineSchedule:
    """Mimics a PipelineSchedule ORM instance."""
    def __init__(
        self,
        schedule_id=None,
        name="nightly",
        cron_expression="0 2 * * *",
        run_type="incremental",
        selected_stages=None,
        enabled=True,
        last_run_at=None,
        next_run_at=None,
    ):
        self.id = schedule_id or uuid.uuid4()
        self.name = name
        self.cron_expression = cron_expression
        self.run_type = run_type
        self.selected_stages = selected_stages
        self.enabled = enabled
        self.last_run_at = last_run_at
        self.next_run_at = next_run_at
        self.created_at = datetime.now(UTC)


class FakeDataSourceRecord:
    """Mimics a DataSourceRecord ORM instance."""
    def __init__(
        self,
        ds_id=None,
        name="BOSS直聘",
        source_type="crawler",
        authority_score=0.73,
        status="active",
        last_crawl_at=None,
        total_records=100,
        valid_records=90,
        duplicate_rate=0.1,
        avg_quality_score=0.85,
        config=None,
    ):
        self.id = ds_id or uuid.uuid4()
        self.name = name
        self.source_type = source_type
        self.authority_score = authority_score
        self.status = status
        self.last_crawl_at = last_crawl_at
        self.total_records = total_records
        self.valid_records = valid_records
        self.duplicate_rate = duplicate_rate
        self.avg_quality_score = avg_quality_score
        self.config = config or {}


# ── Fixtures ──

_MOCK_STATUS_DATA = {
    "is_running": False,
    "current_run": None,
    "last_run": None,
    "run_counts": {"completed": 5, "failed": 1},
    "active_data_sources": 3,
}

_MOCK_AGGREGATES = {
    "today_crawl_volume": 42,
    "success_rate": 0.83,
    "avg_quality_score": 0.91,
}


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def admin_headers():
    # AUTHZ-05 fix: dev-token 返回 admin 需要 dev_anon_admin=True
    from app.config import settings
    original = settings.dev_anon_admin
    settings.dev_anon_admin = True
    yield {"Authorization": "Bearer dev-token"}
    settings.dev_anon_admin = original


@pytest.fixture
def non_admin_override():
    async def _deny():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    app.dependency_overrides[require_admin] = _deny
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def db_override():
    # Override auth to avoid _get_dev_user hitting the fake session
    _fake_user = {"sub": "test_user", "role": "admin", "username": "test_user", "type": "access"}

    async def _override_current_user():
        return _fake_user

    app.dependency_overrides[get_current_user] = _override_current_user

    def _set(session: FakeAsyncSession | None):
        if session is None:
            app.dependency_overrides.pop(get_db_session, None)
        else:
            app.dependency_overrides[get_db_session] = _make_db_override(session)
    yield _set
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def neo4j_override():
    _sentinel = object()

    def _set(driver):
        if driver is _sentinel:
            app.dependency_overrides.pop(get_neo4j_driver, None)
        else:
            app.dependency_overrides[get_neo4j_driver] = lambda: driver
    yield _set
    app.dependency_overrides.pop(get_neo4j_driver, None)


# ══════════════════════════════════════════════════════════════
# GET /pipeline/status
# ══════════════════════════════════════════════════════════════


class TestGetPipelineStatus:
    def test_status_returns_200(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.services.pipeline_service.get_status", new_callable=AsyncMock, return_value=_MOCK_STATUS_DATA),
            patch(
                "app.services.pipeline_service.read_or_compute_status_aggregates",
                new_callable=AsyncMock,
                return_value=_MOCK_AGGREGATES,
            ),
            patch("app.services.pipeline_service.generate_alerts", new_callable=AsyncMock, return_value=[]),
        ):
            resp = client.get("/api/v1/pipeline/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_running"] is False
        assert body["run_counts"]["completed"] == 5
        assert body["today_crawl_volume"] == 42
        assert body["success_rate"] == 0.83
        assert body["quality_alerts"] == []

    def test_status_with_alerts(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        fake_alert = MagicMock(
            level="error", dimension="completeness", message="Low completeness",
            source="lagou", value=0.3, threshold=0.5, timestamp="2025-01-01T00:00:00Z",
        )
        with (
            patch("app.services.pipeline_service.get_status", new_callable=AsyncMock, return_value=_MOCK_STATUS_DATA),
            patch(
                "app.services.pipeline_service.read_or_compute_status_aggregates",
                new_callable=AsyncMock,
                return_value=_MOCK_AGGREGATES,
            ),
            patch("app.services.pipeline_service.generate_alerts", new_callable=AsyncMock, return_value=[fake_alert]),
        ):
            resp = client.get("/api/v1/pipeline/status")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["quality_alerts"]) == 1
        assert body["quality_alerts"][0]["level"] == "error"

    def test_status_alerts_failure_non_fatal(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.services.pipeline_service.get_status", new_callable=AsyncMock, return_value=_MOCK_STATUS_DATA),
            patch(
                "app.services.pipeline_service.read_or_compute_status_aggregates",
                new_callable=AsyncMock,
                return_value=_MOCK_AGGREGATES,
            ),
            patch("app.services.pipeline_service.generate_alerts", new_callable=AsyncMock, side_effect=Exception("boom")),
        ):
            resp = client.get("/api/v1/pipeline/status")
        assert resp.status_code == 200
        assert resp.json()["quality_alerts"] == []


# ══════════════════════════════════════════════════════════════
# GET /pipeline/runs
# ══════════════════════════════════════════════════════════════


class TestGetPipelineRuns:
    def test_runs_returns_200(self, client, db_override):
        run = FakePipelineRun(status="completed")
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.get_run_history", new_callable=AsyncMock, return_value=[run]):
            resp = client.get("/api/v1/pipeline/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["status"] == "completed"

    def test_runs_empty(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.get_run_history", new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/v1/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_runs_with_status_filter(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.get_run_history", new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/v1/pipeline/runs?status=failed")
        assert resp.status_code == 200

    def test_runs_limit_param(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.get_run_history", new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/v1/pipeline/runs?limit=5&offset=10")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# GET /pipeline/runs/{run_id}
# ══════════════════════════════════════════════════════════════


class TestGetPipelineRun:
    def test_get_run_returns_200(self, client, db_override):
        run_id = uuid.uuid4()
        run = FakePipelineRun(run_id=run_id, status="completed")
        session = FakeAsyncSession([FakeResult(run)])
        db_override(session)
        resp = client.get(f"/api/v1/pipeline/runs/{run_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(run_id)
        assert body["status"] == "completed"

    def test_get_run_not_found_returns_404(self, client, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        run_id = uuid.uuid4()
        resp = client.get(f"/api/v1/pipeline/runs/{run_id}")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# POST /pipeline/trigger
# ══════════════════════════════════════════════════════════════


class TestTriggerPipeline:
    def test_trigger_returns_200(self, client, admin_headers):
        fake_run = FakePipelineRun(run_type="full", status="running")
        with (
            patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock, return_value=fake_run),
            patch("app.services.pipeline_service.invalidate_status_cache", new_callable=AsyncMock),
        ):
            resp = client.post("/api/v1/pipeline/trigger", json={"run_type": "full"}, headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == str(fake_run.id)
        assert body["run_type"] == "full"
        assert body["status"] == "running"
        assert "triggered" in body["message"]

    def test_trigger_with_selected_stages(self, client, admin_headers):
        fake_run = FakePipelineRun(run_type="incremental", status="running")
        with (
            patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock, return_value=fake_run),
            patch("app.services.pipeline_service.invalidate_status_cache", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/pipeline/trigger",
                json={"run_type": "incremental", "selected_stages": ["crawl", "dedup"]},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "crawl" in body["message"] or "incremental" in body["message"]

    def test_trigger_default_run_type(self, client, admin_headers):
        fake_run = FakePipelineRun(run_type="full", status="running")
        with (
            patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock, return_value=fake_run),
            patch("app.services.pipeline_service.invalidate_status_cache", new_callable=AsyncMock),
        ):
            resp = client.post("/api/v1/pipeline/trigger", json={}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["run_type"] == "full"


# ══════════════════════════════════════════════════════════════
# POST /pipeline/runs/{run_id}/cancel
# ══════════════════════════════════════════════════════════════


class TestCancelPipelineRun:
    def test_cancel_returns_200(self, client, db_override):
        run_id = uuid.uuid4()
        cancel_result = MagicMock(
            run_id=run_id,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            stopped_stage_names=["crawl"],
        )
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.cancel_run", new_callable=AsyncMock, return_value=cancel_result):
            resp = client.post(f"/api/v1/pipeline/runs/{run_id}/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == str(run_id)
        assert body["status"] == "cancelled"
        assert "crawl" in body["stopped_stage_names"]


# ══════════════════════════════════════════════════════════════
# POST /pipeline/runs/{run_id}/retry
# ══════════════════════════════════════════════════════════════


class TestRetryStage:
    def test_retry_returns_200(self, client, admin_headers):
        run_id = uuid.uuid4()
        run = FakePipelineRun(run_id=run_id, status="running")
        with patch("app.services.pipeline_service.retry_stage", new_callable=AsyncMock, return_value=run):
            resp = client.post(
                f"/api/v1/pipeline/runs/{run_id}/retry",
                json={"stage_name": "crawl"},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(run_id)

    def test_retry_not_found_returns_404(self, client, admin_headers):
        run_id = uuid.uuid4()
        with patch("app.services.pipeline_service.retry_stage", new_callable=AsyncMock, return_value=None):
            resp = client.post(
                f"/api/v1/pipeline/runs/{run_id}/retry",
                json={"stage_name": "crawl"},
                headers=admin_headers,
            )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# POST /pipeline/runs/{run_id}/resume
# ══════════════════════════════════════════════════════════════


class TestResumeRun:
    def test_resume_returns_200(self, client, admin_headers):
        run_id = uuid.uuid4()
        run = FakePipelineRun(run_id=run_id, status="running")
        with patch("app.services.pipeline_service.resume_run", new_callable=AsyncMock, return_value=run):
            resp = client.post(f"/api/v1/pipeline/runs/{run_id}/resume", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(run_id)

    def test_resume_not_found_returns_404(self, client, admin_headers):
        run_id = uuid.uuid4()
        with patch("app.services.pipeline_service.resume_run", new_callable=AsyncMock, return_value=None):
            resp = client.post(f"/api/v1/pipeline/runs/{run_id}/resume", headers=admin_headers)
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# GET /pipeline/stages
# ══════════════════════════════════════════════════════════════


class TestGetPipelineStages:
    def test_stages_no_runs_returns_skeleton(self, client, db_override):
        """QA B5: no run yet returns the 5-stage pending skeleton, not an empty list."""
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        stages = resp.json()["stages"]
        assert [s["name"] for s in stages] == ["crawl", "extract", "standardize", "ingest", "audit"]
        assert all(s["status"] == "pending" and s["skeleton"] for s in stages)

    def test_stages_with_run_returns_stages(self, client, db_override):
        run = FakePipelineRun(
            stages=[
                {"name": "crawl", "status": "completed", "duration_ms": 5000, "records_processed": 100},
                {"name": "dedup", "status": "running", "duration_ms": 2000, "records_processed": 50},
            ],
        )
        session = FakeAsyncSession([FakeResult(run)])
        db_override(session)
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["stages"]) == 2
        assert body["stages"][0]["name"] == "crawl"
        assert body["stages"][1]["status"] == "running"

    def test_stages_dict_format_normalizes(self, client, db_override):
        # ponytail: legacy rows store stages as {"steps": [...]} — normalize to list
        run = FakePipelineRun(
            stages={"steps": [{"name": "crawl", "status": "completed", "duration_ms": 100}]},
        )
        session = FakeAsyncSession([FakeResult(run)])
        db_override(session)
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["stages"]) == 1
        assert body["stages"][0]["name"] == "crawl"

    def test_stages_non_dict_entries_skipped(self, client, db_override):
        run = FakePipelineRun(stages=["not_a_dict", {"name": "dedup", "status": "completed"}])
        session = FakeAsyncSession([FakeResult(run)])
        db_override(session)
        resp = client.get("/api/v1/pipeline/stages")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["stages"]) == 1
        assert body["stages"][0]["name"] == "dedup"


# ══════════════════════════════════════════════════════════════
# GET /pipeline/data-quality
# ══════════════════════════════════════════════════════════════


class TestGetDataQuality:
    def test_data_quality_returns_200(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch(
                "app.services.pipeline_service.sync_source_quality",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.pipeline_service.get_quality_snapshot",
                new_callable=AsyncMock,
                return_value={"metrics": {"overall_score": 0.9}, "alerts": [], "source_scores": {"lagou": 0.8}},
            ),
            patch(
                "app.services.pipeline_service.compute_data_quality_aggregates",
                new_callable=AsyncMock,
                return_value={"completeness": 0.85},
            ),
        ):
            resp = client.get("/api/v1/pipeline/data-quality")
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["overall_score"] == 0.9
        assert body["source_scores"]["lagou"] == 0.8
        assert body["alert_count"] == 0

    def test_data_quality_with_alerts(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        alert = {"level": "warning", "dimension": "freshness", "message": "Stale data", "timestamp": "2025-01-01"}
        with (
            patch(
                "app.services.pipeline_service.sync_source_quality",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.pipeline_service.get_quality_snapshot",
                new_callable=AsyncMock,
                return_value={"metrics": {}, "alerts": [alert], "source_scores": {}},
            ),
            patch(
                "app.services.pipeline_service.compute_data_quality_aggregates",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            resp = client.get("/api/v1/pipeline/data-quality")
        assert resp.status_code == 200
        body = resp.json()
        assert body["alert_count"] == 1
        assert body["alerts"][0]["level"] == "warning"


# ══════════════════════════════════════════════════════════════
# GET /pipeline/datasources
# ══════════════════════════════════════════════════════════════


class TestGetDataSources:
    def test_datasources_returns_200(self, client, db_override):
        ds = FakeDataSourceRecord(name="BOSS直聘", authority_score=0.73)
        session = FakeAsyncSession([FakeResult([ds])])
        db_override(session)
        resp = client.get("/api/v1/pipeline/datasources")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "BOSS直聘"
        assert body[0]["authority_score"] == 0.73

    def test_datasources_empty(self, client, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        resp = client.get("/api/v1/pipeline/datasources")
        assert resp.status_code == 200
        assert resp.json() == []


# ══════════════════════════════════════════════════════════════
# GET /pipeline/events-poll
# ══════════════════════════════════════════════════════════════


class TestEventsPoll:
    def test_events_poll_no_redis_returns_empty(self, client):
        with patch("app.services.resources.resources") as mock_res:
            mock_res.redis_client = None
            resp = client.get("/api/v1/pipeline/events-poll")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_events_poll_with_events(self, client):
        events = [{"type": "stage_complete", "data": {"stage": "crawl"}}]
        with patch("app.services.resources.resources") as mock_res:
            mock_res.redis_client = MagicMock()
            with patch("app.services.pipeline_service.get_recent_events", new_callable=AsyncMock, return_value=events):
                resp = client.get("/api/v1/pipeline/events-poll?since=0")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ══════════════════════════════════════════════════════════════
# GET /pipeline/schedules
# ══════════════════════════════════════════════════════════════


class TestListSchedules:
    def test_list_schedules_returns_200(self, client, db_override):
        schedule = FakePipelineSchedule(name="nightly", cron_expression="0 2 * * *")
        session = FakeAsyncSession([FakeResult([schedule])])
        db_override(session)
        resp = client.get("/api/v1/pipeline/schedules")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "nightly"

    def test_list_schedules_empty(self, client, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        resp = client.get("/api/v1/pipeline/schedules")
        assert resp.status_code == 200
        assert resp.json() == []


# ══════════════════════════════════════════════════════════════
# POST /pipeline/schedules
# ══════════════════════════════════════════════════════════════


class TestCreateSchedule:
    def test_create_schedule_returns_200(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.compute_next_cron", return_value=datetime.now(UTC)):
            resp = client.post(
                "/api/v1/pipeline/schedules",
                headers=admin_headers,
                json={"name": "daily", "cron_expression": "0 3 * * *", "run_type": "incremental"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "daily"
        assert body["cron_expression"] == "0 3 * * *"
        assert len(session._added) == 1

    def test_create_schedule_cron_compute_failure_still_saves(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.services.pipeline_service.compute_next_cron", side_effect=Exception("bad cron")):
            resp = client.post(
                "/api/v1/pipeline/schedules",
                headers=admin_headers,
                json={"name": "broken", "cron_expression": "invalid"},
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "broken"

    def test_create_schedule_requires_admin(self, client, non_admin_override):
        resp = client.post(
            "/api/v1/pipeline/schedules",
            json={"name": "test", "cron_expression": "0 0 * * *"},
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# PUT /pipeline/schedules/{schedule_id}
# ══════════════════════════════════════════════════════════════


class TestUpdateSchedule:
    def test_update_schedule_returns_200(self, client, admin_headers, db_override):
        schedule = FakePipelineSchedule(name="old", cron_expression="0 2 * * *")
        session = FakeAsyncSession([FakeResult(schedule)])
        db_override(session)
        resp = client.put(
            f"/api/v1/pipeline/schedules/{schedule.id}",
            headers=admin_headers,
            json={"name": "updated", "cron_expression": "0 4 * * *", "run_type": "full"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "updated"
        assert body["cron_expression"] == "0 4 * * *"

    def test_update_schedule_not_found_returns_404(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        schedule_id = uuid.uuid4()
        resp = client.put(
            f"/api/v1/pipeline/schedules/{schedule_id}",
            headers=admin_headers,
            json={"name": "x", "cron_expression": "0 0 * * *"},
        )
        assert resp.status_code == 404

    def test_update_schedule_requires_admin(self, client, non_admin_override):
        schedule_id = uuid.uuid4()
        resp = client.put(
            f"/api/v1/pipeline/schedules/{schedule_id}",
            json={"name": "x", "cron_expression": "0 0 * * *"},
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# DELETE /pipeline/schedules/{schedule_id}
# ══════════════════════════════════════════════════════════════


class TestDeleteSchedule:
    def test_delete_schedule_returns_200(self, client, admin_headers, db_override):
        schedule = FakePipelineSchedule()
        session = FakeAsyncSession([FakeResult(schedule)])
        db_override(session)
        resp = client.delete(f"/api/v1/pipeline/schedules/{schedule.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_schedule_not_found_returns_404(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        schedule_id = uuid.uuid4()
        resp = client.delete(f"/api/v1/pipeline/schedules/{schedule_id}", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_schedule_requires_admin(self, client, non_admin_override):
        schedule_id = uuid.uuid4()
        resp = client.delete(f"/api/v1/pipeline/schedules/{schedule_id}")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# POST /pipeline/schedules/{schedule_id}/trigger
# ══════════════════════════════════════════════════════════════


class TestTriggerSchedule:
    def test_trigger_schedule_returns_200(self, client, admin_headers, db_override):
        schedule = FakePipelineSchedule(name="nightly", run_type="incremental")
        fake_run = FakePipelineRun(run_type="incremental", status="running")
        session = FakeAsyncSession([FakeResult(schedule)])
        db_override(session)
        with (
            patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock, return_value=fake_run),
            patch("app.services.pipeline_service.invalidate_status_cache", new_callable=AsyncMock),
        ):
            resp = client.post(f"/api/v1/pipeline/schedules/{schedule.id}/trigger", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == str(fake_run.id)
        assert "nightly" in body["message"]

    def test_trigger_schedule_not_found_returns_404(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        schedule_id = uuid.uuid4()
        resp = client.post(f"/api/v1/pipeline/schedules/{schedule_id}/trigger", headers=admin_headers)
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# GET /pipeline/config
# ══════════════════════════════════════════════════════════════


class TestGetPipelineConfig:
    def test_config_returns_200(self, client, admin_headers):
        resp = client.get("/api/v1/pipeline/config", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "stage_timeout" in body
        assert "worker_concurrency" in body
        assert "crawl_concurrency" in body
        assert "retry_max" in body
        assert "retry_backoff" in body


# ══════════════════════════════════════════════════════════════
# PUT /pipeline/config
# ══════════════════════════════════════════════════════════════


class TestUpdatePipelineConfig:
    def test_update_config_returns_200(self, client, admin_headers):
        resp = client.put(
            "/api/v1/pipeline/config",
            headers=admin_headers,
            json={"stage_timeout": 3600},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["stage_timeout"] == 3600

    def test_update_config_partial_update(self, client, admin_headers):
        current = client.get("/api/v1/pipeline/config", headers=admin_headers).json()
        resp = client.put(
            "/api/v1/pipeline/config",
            headers=admin_headers,
            json={"retry_max": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["retry_max"] == 5
        assert body["stage_timeout"] == current["stage_timeout"]

    def test_update_config_requires_admin(self, client, non_admin_override):
        resp = client.put(
            "/api/v1/pipeline/config",
            json={"stage_timeout": 999},
        )
        assert resp.status_code == 403

    def test_update_config_empty_body_keeps_defaults(self, client, admin_headers):
        resp = client.put(
            "/api/v1/pipeline/config",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 200
