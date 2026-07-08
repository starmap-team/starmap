"""Unit tests for admin API endpoints.

Covers all 26 endpoints across:
- admin.py (10 endpoints)
- admin_prompts.py (10 endpoints)
- admin_graph_nodes.py (6 endpoints)

Uses FastAPI TestClient with dependency_overrides for db session and neo4j driver.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
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

    def fetchall(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def single(self):
        return self.value

    def one(self):
        if isinstance(self.value, (list, tuple)):
            if len(self.value) == 1:
                return self.value[0]
            return self.value
        return self.value


class FakeReviewQueueRow:
    """Mimics a ReviewQueue ORM instance."""

    def __init__(self, id=1, entity_type="skill", entity_name="Python", status="pending", payload=None):
        self.id = id
        self.entity_type = entity_type
        self.entity_name = entity_name
        self.status = status
        self.payload = payload or {"trust": 75}


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
        # Default: return a zero scalar for any unconfigured query.
        # For .one() calls that unpack multiple values, return a tuple of zeros.
        return FakeResult((0.0, 0.0, 0.0))

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        self._committed = True


def _make_db_override(session: FakeAsyncSession):
    """Create an async generator that yields the given session (for dependency_overrides)."""
    async def _override():
        yield session
    return _override


# ── Fixtures ──


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def admin_headers():
    """Dev-mode admin auth header."""
    return {"Authorization": "Bearer dev-token"}


@pytest.fixture
def non_admin_override():
    """Override require_admin to raise 403."""
    async def _deny():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[require_admin] = _deny
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def db_override():
    """Override get_db_session, yielding control to the test via the returned setter.

    Usage:  set_session = db_override(); set_session(my_session); ...; set_session(None)
    """
    def _set(session: FakeAsyncSession | None):
        if session is None:
            app.dependency_overrides.pop(get_db_session, None)
        else:
            app.dependency_overrides[get_db_session] = _make_db_override(session)

    yield _set
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def neo4j_override():
    """Override get_neo4j_driver. Returns a setter function."""
    def _set(driver):
        if driver is _SENTINEL:
            app.dependency_overrides.pop(get_neo4j_driver, None)
        else:
            app.dependency_overrides[get_neo4j_driver] = lambda: driver

    yield _set
    app.dependency_overrides.pop(get_neo4j_driver, None)


_SENTINEL = object()


@pytest.fixture(autouse=True)
def _reset_prompt_state():
    """Reset in-memory prompt/A/B state between tests to avoid cross-contamination."""
    from app.core.extraction.prompt import _AB_TESTS, _ACTIVE_VERSIONS, _PROMPT_VERSIONS
    orig_versions = dict(_PROMPT_VERSIONS)
    orig_active = dict(_ACTIVE_VERSIONS)
    orig_ab = dict(_AB_TESTS)
    yield
    _PROMPT_VERSIONS.clear()
    _PROMPT_VERSIONS.update(orig_versions)
    _ACTIVE_VERSIONS.clear()
    _ACTIVE_VERSIONS.update(orig_active)
    _AB_TESTS.clear()
    _AB_TESTS.update(orig_ab)


@pytest.fixture(autouse=True)
def _reset_ab_results():
    """Clear in-memory A/B results between tests."""
    from app.api.v1.admin_prompts import _ab_results
    _ab_results.clear()
    yield


# ══════════════════════════════════════════════════════════════
# admin.py — 10 endpoints
# ══════════════════════════════════════════════════════════════


class TestAdminStats:
    """GET /api/v1/admin/stats"""

    def test_stats_returns_200(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        dashboard_mock = MagicMock(
            hallucination_rate=0.05,
            report=MagicMock(precision=0.9, recall=0.8, f1=0.85, warning_level="green", details=[]),
        )
        with patch("app.api.v1.admin._build_quality_dashboard", new_callable=AsyncMock, return_value=dashboard_mock):
            resp = client.get("/api/v1/admin/stats", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "total_nodes" in body
        assert "hallucination_rate" in body

    def test_stats_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/stats")
        assert resp.status_code == 403


class TestAdminSources:
    """GET /api/v1/admin/sources"""

    def test_sources_returns_200(self, client, admin_headers, db_override):
        rows = [("lagou", 100)]
        session = FakeAsyncSession([FakeResult(rows)])
        db_override(session)
        resp = client.get("/api/v1/admin/sources", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body

    def test_sources_empty_on_db_error(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        session.execute = AsyncMock(side_effect=Exception("db down"))
        db_override(session)
        resp = client.get("/api/v1/admin/sources", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_sources_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/sources")
        assert resp.status_code == 403


class TestAdminReviewQueue:
    """GET /api/v1/admin/review-queue and /api/v1/admin/audit-queue"""

    def test_review_queue_returns_200(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=1, entity_type="skill", entity_name="Python", status="pending", payload={"trust": 80})
        session = FakeAsyncSession([
            FakeResult(0),          # total_count
            FakeResult([row]),      # pending rows
        ])
        db_override(session)
        resp = client.get("/api/v1/admin/review-queue", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body

    def test_audit_queue_alias(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(0), FakeResult([])])
        db_override(session)
        resp = client.get("/api/v1/admin/audit-queue", headers=admin_headers)
        assert resp.status_code == 200

    def test_review_queue_auto_seeds_when_empty(self, client, admin_headers, db_override):
        session = FakeAsyncSession([
            FakeResult(0),      # total_count == 0 triggers auto-seed
            FakeResult([]),     # pending rows after seed
        ])
        db_override(session)
        resp = client.get("/api/v1/admin/review-queue", headers=admin_headers)
        assert resp.status_code == 200
        assert len(session._added) == 4  # _DEMO_REVIEW_SEED has 4 items

    def test_review_queue_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/review-queue")
        assert resp.status_code == 403


class TestAdminAuditApprove:
    """POST /api/v1/admin/audit/{id}/approve"""

    def test_approve_returns_200(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=5, entity_type="skill", entity_name="Go", status="pending", payload={"trust": 60})
        session = FakeAsyncSession([FakeResult(row)])
        db_override(session)
        resp = client.post("/api/v1/admin/audit/5/approve", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["id"] == 5

    def test_approve_404_when_not_found(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.post("/api/v1/admin/audit/999/approve", headers=admin_headers)
        assert resp.status_code == 404

    def test_approve_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/audit/1/approve")
        assert resp.status_code == 403


class TestAdminAuditReject:
    """POST /api/v1/admin/audit/{id}/reject"""

    def test_reject_returns_200(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=3, entity_type="position", entity_name="Engineer", status="pending", payload={"trust": 40})
        session = FakeAsyncSession([FakeResult(row)])
        db_override(session)
        resp = client.post("/api/v1/admin/audit/3/reject", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_404_when_not_found(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.post("/api/v1/admin/audit/999/reject", headers=admin_headers)
        assert resp.status_code == 404

    def test_reject_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/audit/1/reject")
        assert resp.status_code == 403


class TestAdminUpdateReviewQueue:
    """PUT/PATCH /api/v1/admin/review-queue/{id}"""

    def test_update_name_returns_200(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=2, entity_name="Old Name", payload={"trust": 50})
        session = FakeAsyncSession([FakeResult(row)])
        db_override(session)
        resp = client.put("/api/v1/admin/review-queue/2", headers=admin_headers, json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_trust_returns_200(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=2, entity_name="Python", payload={"trust": 50})
        session = FakeAsyncSession([FakeResult(row)])
        db_override(session)
        resp = client.put("/api/v1/admin/review-queue/2", headers=admin_headers, json={"trust": 90})
        assert resp.status_code == 200
        assert resp.json()["trust"] == 90

    def test_update_404_when_not_found(self, client, admin_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.put("/api/v1/admin/review-queue/999", headers=admin_headers, json={"name": "X"})
        assert resp.status_code == 404

    def test_patch_alias_works(self, client, admin_headers, db_override):
        row = FakeReviewQueueRow(id=2, entity_name="Python", payload={"trust": 50})
        session = FakeAsyncSession([FakeResult(row)])
        db_override(session)
        resp = client.patch("/api/v1/admin/review-queue/2", headers=admin_headers, json={"trust": 70})
        assert resp.status_code == 200

    def test_update_requires_admin(self, client, non_admin_override):
        resp = client.put("/api/v1/admin/review-queue/1", json={"name": "X"})
        assert resp.status_code == 403


class TestAdminResetDemo:
    """POST /api/v1/admin/seed/reset and /api/v1/admin/reset-demo"""

    def test_reset_demo_returns_200(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post("/api/v1/admin/seed/reset", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["review_items"] == 4

    def test_reset_demo_alias(self, client, admin_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post("/api/v1/admin/reset-demo", headers=admin_headers)
        assert resp.status_code == 200

    def test_reset_demo_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/seed/reset")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# admin_prompts.py — 10 endpoints
# ══════════════════════════════════════════════════════════════


class TestListPrompts:
    """GET /api/v1/admin/prompts"""

    def test_list_prompts_returns_200(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "jd_extraction" in body

    def test_list_prompts_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/prompts")
        assert resp.status_code == 403


class TestGetPromptInfo:
    """GET /api/v1/admin/prompts/{name}"""

    def test_get_prompt_info_returns_200(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/jd_extraction", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "jd_extraction"
        assert "versions" in body

    def test_get_prompt_info_404_for_unknown(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/nonexistent_prompt", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_prompt_info_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/prompts/jd_extraction")
        assert resp.status_code == 403


class TestGetPromptTemplate:
    """GET /api/v1/admin/prompts/{name}/template"""

    def test_get_template_returns_200(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/template", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "template" in body
        assert "$jd_content" in body["template"]

    def test_get_template_404_for_unknown(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/nonexistent/template", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_template_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/template")
        assert resp.status_code == 403


class TestCreatePromptVersion:
    """POST /api/v1/admin/prompts/{name}/versions"""

    def test_create_version_returns_200(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/versions",
            headers=admin_headers,
            json={"template": "Test template $jd_content", "version": "v_test", "activate": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["registered_version"] == "v_test"
        assert body["prompt"] == "jd_extraction"

    def test_create_version_auto_increment(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/versions",
            headers=admin_headers,
            json={"template": "Auto version template $jd_content"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # jd_extraction starts with v1-v4, auto increments from there
        assert body["registered_version"].startswith("v")

    def test_create_version_with_activate(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/versions",
            headers=admin_headers,
            json={"template": "Activated template $jd_content", "version": "v_act", "activate": True},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] == "v_act"

    def test_create_version_requires_admin(self, client, non_admin_override):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/versions",
            json={"template": "test"},
        )
        assert resp.status_code == 403


class TestChangeActiveVersion:
    """PUT /api/v1/admin/prompts/{name}/active"""

    def test_change_active_returns_200(self, client, admin_headers):
        resp = client.put(
            "/api/v1/admin/prompts/jd_extraction/active",
            headers=admin_headers,
            json={"version": "v2"},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] == "v2"

    def test_change_active_invalid_version_raises(self, client, admin_headers):
        resp = client.put(
            "/api/v1/admin/prompts/jd_extraction/active",
            headers=admin_headers,
            json={"version": "v_nonexistent"},
        )
        assert resp.status_code == 400

    def test_change_active_requires_admin(self, client, non_admin_override):
        resp = client.put(
            "/api/v1/admin/prompts/jd_extraction/active",
            json={"version": "v1"},
        )
        assert resp.status_code == 403


class TestStartABTest:
    """POST /api/v1/admin/prompts/{name}/ab-test"""

    def test_start_ab_test_returns_200(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-test",
            headers=admin_headers,
            json={"canary_version": "v2", "traffic_fraction": 0.2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ab_test"]["canary_version"] == "v2"
        assert body["ab_test"]["traffic_fraction"] == 0.2

    def test_start_ab_test_default_traffic(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-test",
            headers=admin_headers,
            json={"canary_version": "v3"},
        )
        assert resp.status_code == 200
        assert resp.json()["ab_test"]["traffic_fraction"] == 0.1

    def test_start_ab_test_invalid_traffic(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-test",
            headers=admin_headers,
            json={"canary_version": "v2", "traffic_fraction": 0.9},
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_start_ab_test_requires_admin(self, client, non_admin_override):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-test",
            json={"canary_version": "v2"},
        )
        assert resp.status_code == 403


class TestDeleteABTest:
    """DELETE /api/v1/admin/prompts/{name}/ab-test"""

    def test_delete_ab_test_returns_200(self, client, admin_headers):
        from app.core.extraction.prompt import set_ab_test
        set_ab_test("jd_extraction", "v2", 0.1)
        resp = client.delete("/api/v1/admin/prompts/jd_extraction/ab-test", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ab_test"] is None

    def test_delete_ab_test_idempotent(self, client, admin_headers):
        resp = client.delete("/api/v1/admin/prompts/jd_extraction/ab-test", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_ab_test_requires_admin(self, client, non_admin_override):
        resp = client.delete("/api/v1/admin/prompts/jd_extraction/ab-test")
        assert resp.status_code == 403


class TestGetABTestConfig:
    """GET /api/v1/admin/prompts/{name}/ab-test"""

    def test_get_ab_test_config_none(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-test", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ab_test"] is None

    def test_get_ab_test_config_active(self, client, admin_headers):
        from app.core.extraction.prompt import set_ab_test
        set_ab_test("jd_extraction", "v2", 0.15)
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-test", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ab_test"]["canary_version"] == "v2"

    def test_get_ab_test_config_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-test")
        assert resp.status_code == 403


class TestRecordABResult:
    """POST /api/v1/admin/prompts/{name}/ab-results"""

    def test_record_ab_result_returns_200(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-results",
            headers=admin_headers,
            json={"version": "v1", "success": True, "f1": 0.85, "latency_ms": 120.0},
        )
        assert resp.status_code == 200
        assert resp.json()["recorded"] is True

    def test_record_ab_result_minimal(self, client, admin_headers):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-results",
            headers=admin_headers,
            json={"version": "v2"},
        )
        assert resp.status_code == 200

    def test_record_ab_result_requires_admin(self, client, non_admin_override):
        resp = client.post(
            "/api/v1/admin/prompts/jd_extraction/ab-results",
            json={"version": "v1"},
        )
        assert resp.status_code == 403


class TestGetABResults:
    """GET /api/v1/admin/prompts/{name}/ab-results"""

    def test_get_ab_results_empty(self, client, admin_headers):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-results", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["versions"] == {}

    def test_get_ab_results_with_data(self, client, admin_headers):
        from app.api.v1.admin_prompts import _ab_results
        _ab_results["jd_extraction"] = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0, "timestamp": 1.0},
            {"version": "v1", "success": False, "f1": 0.6, "latency_ms": 150.0, "timestamp": 2.0},
            {"version": "v2", "success": True, "f1": 0.9, "latency_ms": 90.0, "timestamp": 3.0},
        ]
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-results", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert "v1" in body["versions"]
        assert "v2" in body["versions"]
        assert body["versions"]["v1"]["success_rate"] == 0.5
        assert body["versions"]["v2"]["success_rate"] == 1.0

    def test_get_ab_results_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/prompts/jd_extraction/ab-results")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# admin_graph_nodes.py — 6 endpoints
# ══════════════════════════════════════════════════════════════


def _make_neo4j_driver(run_return=None, run_side_effect=None):
    """Build a fake neo4j driver with a session that returns run_return or raises run_side_effect."""
    fake_result = AsyncMock()
    if run_side_effect:
        fake_result.single = AsyncMock(side_effect=run_side_effect)
    else:
        fake_result.single = AsyncMock(return_value=run_return)

    fake_session = AsyncMock()
    if run_side_effect and not run_return:
        fake_session.run = AsyncMock(side_effect=run_side_effect)
    else:
        fake_session.run = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_driver = MagicMock()
    fake_driver.session = MagicMock(return_value=fake_session)
    return fake_driver


class TestListGraphNodes:
    """GET /api/v1/admin/graph/nodes"""

    def test_list_nodes_no_driver_returns_empty(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.get("/api/v1/admin/graph/nodes", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_list_nodes_with_driver_returns_200(self, client, admin_headers, neo4j_override):
        fake_node = MagicMock()
        fake_node.labels = ["Skill"]
        fake_node.element_id = "4:abc"
        # dict(node) must work
        fake_node_dict = {"name": "Python"}
        fake_node.__iter__ = lambda s: iter(fake_node_dict.items())

        record = {"n": fake_node}
        fake_result = AsyncMock()
        fake_result.__aiter__ = lambda s: iter([record])

        fake_session = AsyncMock()
        fake_session.run = AsyncMock(return_value=fake_result)
        fake_session.__aenter__ = AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = AsyncMock(return_value=False)

        fake_driver = MagicMock()
        fake_driver.session = MagicMock(return_value=fake_session)

        neo4j_override(fake_driver)
        resp = client.get("/api/v1/admin/graph/nodes", headers=admin_headers)
        assert resp.status_code == 200

    def test_list_nodes_requires_admin(self, client, non_admin_override):
        resp = client.get("/api/v1/admin/graph/nodes")
        assert resp.status_code == 403


class TestCreateGraphNode:
    """POST /api/v1/admin/graph/nodes"""

    def test_create_node_no_driver_returns_503(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.post(
            "/api/v1/admin/graph/nodes",
            headers=admin_headers,
            json={"type": "Skill", "name": "Python"},
        )
        assert resp.status_code == 503

    def test_create_node_invalid_label_returns_400(self, client, admin_headers, neo4j_override):
        neo4j_override(MagicMock())
        resp = client.post(
            "/api/v1/admin/graph/nodes",
            headers=admin_headers,
            json={"type": "HackerLabel", "name": "Evil"},
        )
        assert resp.status_code == 400
        assert "Invalid label" in resp.json()["detail"]

    def test_create_node_success(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"eid": "4:new123"})
        neo4j_override(driver)
        resp = client.post(
            "/api/v1/admin/graph/nodes",
            headers=admin_headers,
            json={"type": "Skill", "name": "Rust", "properties": {"category": "hard_skill"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "Skill"
        assert body["name"] == "Rust"
        assert body["status"] == "pending"

    def test_create_node_db_error_returns_500(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_side_effect=Exception("neo4j down"))
        neo4j_override(driver)
        resp = client.post(
            "/api/v1/admin/graph/nodes",
            headers=admin_headers,
            json={"type": "Skill", "name": "Fail"},
        )
        assert resp.status_code == 500

    def test_create_node_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/graph/nodes", json={"type": "Skill", "name": "X"})
        assert resp.status_code == 403


class TestUpdateGraphNode:
    """PUT /api/v1/admin/graph/nodes/{id}"""

    def test_update_node_no_driver_returns_503(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.put(
            "/api/v1/admin/graph/nodes/4:abc",
            headers=admin_headers,
            json={"type": "Skill", "name": "Updated"},
        )
        assert resp.status_code == 503

    def test_update_node_invalid_label_returns_400(self, client, admin_headers, neo4j_override):
        neo4j_override(MagicMock())
        resp = client.put(
            "/api/v1/admin/graph/nodes/4:abc",
            headers=admin_headers,
            json={"type": "BadLabel", "name": "X"},
        )
        assert resp.status_code == 400

    def test_update_node_success(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"n": MagicMock()})
        neo4j_override(driver)
        resp = client.put(
            "/api/v1/admin/graph/nodes/4:abc",
            headers=admin_headers,
            json={"type": "Skill", "name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_node_not_found_returns_404(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return=None)
        neo4j_override(driver)
        resp = client.put(
            "/api/v1/admin/graph/nodes/4:missing",
            headers=admin_headers,
            json={"type": "Skill", "name": "X"},
        )
        assert resp.status_code == 404

    def test_update_node_requires_admin(self, client, non_admin_override):
        resp = client.put("/api/v1/admin/graph/nodes/1", json={"type": "Skill", "name": "X"})
        assert resp.status_code == 403


class TestDeleteGraphNode:
    """DELETE /api/v1/admin/graph/nodes/{id}"""

    def test_delete_node_no_driver_returns_503(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.delete("/api/v1/admin/graph/nodes/4:abc", headers=admin_headers)
        assert resp.status_code == 503

    def test_delete_node_success(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"deleted": 1})
        neo4j_override(driver)
        resp = client.delete("/api/v1/admin/graph/nodes/4:abc", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_node_not_found_returns_404(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"deleted": 0})
        neo4j_override(driver)
        resp = client.delete("/api/v1/admin/graph/nodes/4:missing", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_node_requires_admin(self, client, non_admin_override):
        resp = client.delete("/api/v1/admin/graph/nodes/1")
        assert resp.status_code == 403


class TestApproveGraphNode:
    """POST /api/v1/admin/graph/nodes/{id}/approve"""

    def test_approve_node_no_driver_returns_503(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.post("/api/v1/admin/graph/nodes/4:abc/approve", headers=admin_headers)
        assert resp.status_code == 503

    def test_approve_node_success(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"n": MagicMock()})
        neo4j_override(driver)
        resp = client.post("/api/v1/admin/graph/nodes/4:abc/approve", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_node_not_found_returns_404(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return=None)
        neo4j_override(driver)
        resp = client.post("/api/v1/admin/graph/nodes/4:missing/approve", headers=admin_headers)
        assert resp.status_code == 404

    def test_approve_node_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/graph/nodes/1/approve")
        assert resp.status_code == 403


class TestRejectGraphNode:
    """POST /api/v1/admin/graph/nodes/{id}/reject"""

    def test_reject_node_no_driver_returns_503(self, client, admin_headers, neo4j_override):
        neo4j_override(None)
        resp = client.post("/api/v1/admin/graph/nodes/4:abc/reject", headers=admin_headers)
        assert resp.status_code == 503

    def test_reject_node_success(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return={"n": MagicMock()})
        neo4j_override(driver)
        resp = client.post("/api/v1/admin/graph/nodes/4:abc/reject", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_node_not_found_returns_404(self, client, admin_headers, neo4j_override):
        driver = _make_neo4j_driver(run_return=None)
        neo4j_override(driver)
        resp = client.post("/api/v1/admin/graph/nodes/4:missing/reject", headers=admin_headers)
        assert resp.status_code == 404

    def test_reject_node_requires_admin(self, client, non_admin_override):
        resp = client.post("/api/v1/admin/graph/nodes/1/reject")
        assert resp.status_code == 403
