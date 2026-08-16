"""Unit tests for datasource API endpoints.

Covers all 5 endpoints:
  GET  /api/v1/datasources            — list
  GET  /api/v1/datasources/{id}       — detail
  PUT  /api/v1/datasources/{id}       — update
  GET  /api/v1/datasources/{id}/stats — stats
  POST /api/v1/datasources/{id}/sync  — trigger sync

Uses FastAPI TestClient + dependency_overrides (same pattern as test_admin_endpoints.py).
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

    def scalar_one(self):
        if self.value is None:
            raise Exception("No result found")
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def fetchall(self):
        """E20 stats endpoint reads raw rows via `runs_result.fetchall()`."""
        return self.value if isinstance(self.value, list) else [self.value]


_SENTINEL = object()


class FakeDataSourceRecord:
    """Mimics a DataSourceRecord ORM instance."""

    def __init__(
        self,
        id=None,
        name="BOSS直聘",
        source_type="crawler",
        authority_score=0.8,
        status="active",
        last_crawl_at=_SENTINEL,
        total_records=1000,
        valid_records=950,
        duplicate_rate=0.05,
        avg_quality_score=0.85,
        config=None,
    ):
        self.id = id or uuid.uuid4()
        self.name = name
        self.source_type = source_type
        self.authority_score = authority_score
        self.status = status
        # ponytail: sentinel to distinguish None from "not passed"
        self.last_crawl_at = datetime.now(UTC) if last_crawl_at is _SENTINEL else last_crawl_at
        self.total_records = total_records
        self.valid_records = valid_records
        self.duplicate_rate = duplicate_rate
        self.avg_quality_score = avg_quality_score
        self.config = config or {"url": "https://example.com", "platform": "v2ex"}


def _crawl_stages(sub_breakdown: dict[str, int] | None = None) -> list[dict]:
    """Build the PipelineRun.stages JSON for a crawl stage with sub_breakdown."""
    return [{"name": "crawl", "sub_breakdown": sub_breakdown or {}}]


def _run_row(
    started_at: datetime | None = None,
    status: str = "completed",
    total_records: int = 100,
    quality_score: float = 0.9,
    sub_breakdown: dict[str, int] | None = None,
) -> tuple:
    """Raw row for the E20 stats query: (id, started_at, status, total_records, quality_score, stages)."""
    return (
        uuid.uuid4(),
        started_at or datetime.now(UTC),
        status,
        total_records,
        quality_score,
        _crawl_stages(sub_breakdown),
    )


class FakeAsyncSession:
    """Minimal async session that returns pre-configured results per execute call."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self._idx = 0
        self._added = []
        self._committed = False

    async def execute(self, _stmt, _params=None):
        # E20 fix: stats endpoint calls `session.execute(text(...), {"cutoff": ...})`
        # with a second positional params arg — accept and ignore it.
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


# ── Fixtures ──

_MOCK_USER = {"sub": "test-user-dev", "role": "admin", "username": "developer"}


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Auth headers — rely on _override_user fixture; no hardcoded tokens needed."""
    return {}


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
    """Override get_current_user to return dev user."""
    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ══════════════════════════════════════════════════════════════
# GET /api/v1/datasources — list
# ══════════════════════════════════════════════════════════════


class TestListDatasources:
    # D4 fix (2026-08-12): GET /datasources 现先跑 sync_source_quality（D3 聚合回写）
    # 数据刷新副作用 —— 本类测试断言的是列表序列化，patch 掉该副作用避免依赖 Fake session
    @pytest.fixture(autouse=True)
    def _patch_sync_source_quality(self):
        with patch("app.services.pipeline_service.sync_source_quality", new=AsyncMock(return_value={})):
            yield

    def test_list_returns_200_with_data(self, client, auth_headers, db_override):
        ds1 = FakeDataSourceRecord(name="BOSS直聘", authority_score=0.9)
        ds2 = FakeDataSourceRecord(name="拉勾网", authority_score=0.7)
        session = FakeAsyncSession([FakeResult([ds1, ds2])])
        db_override(session)
        resp = client.get("/api/v1/datasources", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["name"] == "BOSS直聘"
        assert body[1]["name"] == "拉勾网"

    def test_list_empty_returns_200(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        resp = client.get("/api/v1/datasources", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_serializes_fields(self, client, auth_headers, db_override):
        ds = FakeDataSourceRecord(
            name="GitHub",
            source_type="api",
            authority_score=0.95,
            status="active",
            total_records=500,
            valid_records=480,
            duplicate_rate=0.04,
            avg_quality_score=0.92,
            config={"rate_limit": 100},
        )
        session = FakeAsyncSession([FakeResult([ds])])
        db_override(session)
        resp = client.get("/api/v1/datasources", headers=auth_headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["name"] == "GitHub"
        assert item["source_type"] == "api"
        assert item["authority_score"] == 0.95
        assert item["status"] == "active"
        assert item["total_records"] == 500
        assert item["valid_records"] == 480
        assert item["duplicate_rate"] == 0.04
        assert item["avg_quality_score"] == 0.92
        assert item["config"] == {"rate_limit": 100}
        assert item["last_crawl_at"] is not None

    def test_list_null_last_crawl_at(self, client, auth_headers, db_override):
        ds = FakeDataSourceRecord(last_crawl_at=None)
        session = FakeAsyncSession([FakeResult([ds])])
        db_override(session)
        resp = client.get("/api/v1/datasources", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()[0]["last_crawl_at"] is None


# ══════════════════════════════════════════════════════════════
# GET /api/v1/datasources/{source_id} — detail
# ══════════════════════════════════════════════════════════════


class TestGetDatasource:
    def test_get_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, name="ESCO")
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(ds_id)
        assert body["name"] == "ESCO"

    def test_get_not_found_returns_404(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}", headers=auth_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_invalid_uuid_returns_422(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.get("/api/v1/datasources/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# PUT /api/v1/datasources/{source_id} — update
# ══════════════════════════════════════════════════════════════


class TestUpdateDatasource:
    def test_update_authority_score_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, authority_score=0.5)
        # 1st execute: select → returns ds
        # 2nd execute: update → FakeResult (ignored)
        # 3rd execute: re-fetch select → returns updated ds
        updated_ds = FakeDataSourceRecord(id=ds_id, authority_score=0.9)
        session = FakeAsyncSession([FakeResult(ds), FakeResult(None), FakeResult(updated_ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"authority_score": 0.9},
        )
        assert resp.status_code == 200
        assert resp.json()["authority_score"] == 0.9

    def test_update_status_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, status="active")
        updated_ds = FakeDataSourceRecord(id=ds_id, status="paused")
        session = FakeAsyncSession([FakeResult(ds), FakeResult(None), FakeResult(updated_ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"status": "paused"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_update_config_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, config={"old": True})
        updated_ds = FakeDataSourceRecord(id=ds_id, config={"new": True})
        session = FakeAsyncSession([FakeResult(ds), FakeResult(None), FakeResult(updated_ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"config": {"new": True}},
        )
        assert resp.status_code == 200
        assert resp.json()["config"] == {"new": True}

    def test_update_invalid_status_returns_422(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"status": "invalid_status"},
        )
        # Literal type validation rejects at Pydantic layer (422)
        assert resp.status_code == 422

    def test_update_status_inactive_returns_200(self, client, auth_headers, db_override):
        """Phase 23 Task 8 (DC-04): PATCH status='inactive' 被接受（替代 DELETE 独占软删）。"""
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, status="active")
        updated_ds = FakeDataSourceRecord(id=ds_id, status="inactive")
        session = FakeAsyncSession([FakeResult(ds), FakeResult(None), FakeResult(updated_ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"status": "inactive"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    def test_update_not_found_returns_404(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"authority_score": 0.5},
        )
        assert resp.status_code == 404

    def test_update_authority_score_out_of_range_returns_422(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"authority_score": 2.0},
        )
        assert resp.status_code == 422

    def test_update_negative_authority_score_returns_422(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession()
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={"authority_score": -0.1},
        )
        assert resp.status_code == 422

    def test_update_no_fields_returns_unchanged(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, authority_score=0.5)
        # No values to update → no update/flush/re-fetch, just returns _serialize(ds)
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        resp = client.put(
            f"/api/v1/datasources/{ds_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["authority_score"] == 0.5

    def test_update_invalid_uuid_returns_422(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.put(
            "/api/v1/datasources/not-a-uuid",
            headers=auth_headers,
            json={"authority_score": 0.5},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# GET /api/v1/datasources/{source_id}/stats — stats
# ══════════════════════════════════════════════════════════════


class TestGetDatasourceStats:
    def test_stats_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, name="BOSS直聘")
        # E20: stats reads raw rows (id, started_at, status, total_records, quality_score, stages);
        # the crawl sub_breakdown attributes 50 records to BOSS直聘.
        run = _run_row(status="completed", total_records=50, quality_score=0.8, sub_breakdown={"BOSS直聘": 50})
        session = FakeAsyncSession([FakeResult(ds), FakeResult([run])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_id"] == str(ds_id)
        assert body["source_name"] == "BOSS直聘"
        assert body["total_runs"] == 1
        assert body["successful_runs"] == 1
        assert body["failed_runs"] == 0
        assert len(body["crawl_volume"]) == 30  # default period=30d
        assert len(body["quality_trend"]) == 30
        # The attributed volume lands on today's crawl_volume entry
        assert body["crawl_volume"][-1]["count"] == 50

    def test_stats_7d_period(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        session = FakeAsyncSession([FakeResult(ds), FakeResult([])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats?period=7d", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["crawl_volume"]) == 7
        assert len(body["quality_trend"]) == 7

    def test_stats_90d_period(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        session = FakeAsyncSession([FakeResult(ds), FakeResult([])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats?period=90d", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["crawl_volume"]) == 90

    def test_stats_invalid_period_returns_422(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        session = FakeAsyncSession([FakeResult(ds), FakeResult([])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats?period=1y", headers=auth_headers)
        # Literal type validation rejects at Pydantic layer (422)
        assert resp.status_code == 422

    def test_stats_not_found_returns_404(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats", headers=auth_headers)
        assert resp.status_code == 404

    def test_stats_with_failed_runs(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        completed = _run_row(status="completed", total_records=100, quality_score=0.9, sub_breakdown={"BOSS直聘": 100})
        failed = _run_row(status="failed", total_records=0, quality_score=0.0, sub_breakdown={})
        session = FakeAsyncSession([FakeResult(ds), FakeResult([completed, failed])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_runs"] == 2
        assert body["successful_runs"] == 1
        assert body["failed_runs"] == 1

    def test_stats_does_not_misattribute_other_sources(self, client, auth_headers, db_override):
        """E20: runs whose sub_breakdown does not mention this source must not
        count toward successful_runs / crawl_volume (previously every completed
        run in the window was attributed to every source)."""
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, name="ESCO")
        # This run belongs to BOSS直聘, not ESCO → should not be attributed.
        foreign = _run_row(status="completed", total_records=83000, quality_score=0.9, sub_breakdown={"BOSS直聘": 83000})
        session = FakeAsyncSession([FakeResult(ds), FakeResult([foreign])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_runs"] == 1
        assert body["successful_runs"] == 0
        assert body["failed_runs"] == 0
        assert all(entry["count"] == 0 for entry in body["crawl_volume"])

    def test_stats_no_runs_zero_avg(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id)
        session = FakeAsyncSession([FakeResult(ds), FakeResult([])])
        db_override(session)
        resp = client.get(f"/api/v1/datasources/{ds_id}/stats", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["avg_records_per_run"] == 0.0
        assert body["total_runs"] == 0


# ══════════════════════════════════════════════════════════════
# POST /api/v1/datasources/{source_id}/sync — trigger sync
# ══════════════════════════════════════════════════════════════


class TestTriggerSourceSync:
    def test_sync_returns_200(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, name="拉勾网")
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        with patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock) as mock_trigger:
            from app.models.pipeline_models import PipelineRun
            mock_run = MagicMock(spec=PipelineRun)
            mock_run.id = uuid.uuid4()
            mock_run.status = "running"
            mock_trigger.return_value = mock_run

            resp = client.post(f"/api/v1/datasources/{ds_id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["source_name"] == "拉勾网"
        assert body["status"] == "running"
        assert "run_id" in body

    def test_sync_not_found_returns_404(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.post(f"/api/v1/datasources/{ds_id}/sync", headers=auth_headers)
        assert resp.status_code == 404

    def test_sync_invalid_uuid_returns_422(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post("/api/v1/datasources/not-a-uuid/sync", headers=auth_headers)
        assert resp.status_code == 422

    def test_sync_triggers_pipeline(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, name="51Job")
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        with patch("app.services.pipeline_service.trigger_and_start", new_callable=AsyncMock) as mock_trigger:
            from app.models.pipeline_models import PipelineRun
            mock_run = MagicMock(spec=PipelineRun)
            mock_run.id = uuid.uuid4()
            mock_run.status = "running"
            mock_trigger.return_value = mock_run

            resp = client.post(f"/api/v1/datasources/{ds_id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        # E19 fix: single-source sync is mapped to "incremental" because
        # trigger_and_start only accepts full/incremental (DB constraint).
        # P1-7 fix (functional-review 2026-08-13): 单源同步必须透传 selected_sources，
        # 否则新 run selected_sources=None → crawl 爬全部 active 源（单源语义失效）。
        mock_trigger.assert_awaited_once_with(
            run_type="incremental", selected_sources=["51Job"],
        )


# ══════════════════════════════════════════════════════════════
# GET /api/v1/datasources/health — health check
# ══════════════════════════════════════════════════════════════


class TestDatasourcesHealth:
    def test_health_returns_200(self, client, auth_headers, db_override):
        ds1 = FakeDataSourceRecord(name="BOSS直聘", status="active")
        ds2 = FakeDataSourceRecord(name="拉勾网", status="error")
        # execute 1: select DataSourceRecord → [ds1, ds2]
        # execute 2: select PipelineRun for ds1 → None
        # execute 3: select PipelineRun for ds2 → None
        session = FakeAsyncSession([
            FakeResult([ds1, ds2]),
            FakeResult(None),  # no recent run for ds1
            FakeResult(None),  # no recent run for ds2
        ])
        db_override(session)
        resp = client.get("/api/v1/datasources/health", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_sources"] == 2
        assert body["active_sources"] == 1
        assert body["error_sources"] == 1
        assert len(body["sources"]) == 2

    def test_health_empty_returns_200(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        resp = client.get("/api/v1/datasources/health", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_sources"] == 0
        assert body["sources"] == []


class TestCreateDatasource:
    """POST /api/v1/admin/datasources — 管理员注册新数据源。"""

    def test_create_rejects_inactive_422(self, client, auth_headers, db_override):
        """Phase 23 Task 8 (DC-04): 新源不能直接建为停用 → Literal 拒绝 (422)。"""
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/admin/datasources",
            headers=auth_headers,
            json={"name": "NewSource", "status": "inactive"},
        )
        assert resp.status_code == 422

    def test_create_rejects_invalid_status_422(self, client, auth_headers, db_override):
        session = FakeAsyncSession()
        db_override(session)
        resp = client.post(
            "/api/v1/admin/datasources",
            headers=auth_headers,
            json={"name": "NewSource", "status": "bogus"},
        )
        assert resp.status_code == 422


class TestDataSourceStatusEnum:
    """Phase 23 Task 8 (DC-04): 共享 DataSourceStatus 覆盖 'inactive' 且被 schema 引用。"""

    def test_shared_enum_covers_inactive(self):
        from app.core.constants import DataSourceStatus

        assert DataSourceStatus.INACTIVE == "inactive"
        assert {s.value for s in DataSourceStatus} == {"active", "paused", "error", "inactive"}

    def test_schema_references_shared_enum(self):
        """update schema 引用 DataSourceStatus（含 inactive），create 保持不含。"""
        from typing import get_args

        from app.core.constants import DataSourceStatus
        from app.schemas.datasource import DataSourceCreateRequest, DataSourceUpdateRequest

        # update 字段类型引用共享枚举（DataSourceStatus | None）
        ann = DataSourceUpdateRequest.model_fields["status"].annotation
        assert DataSourceStatus in get_args(ann)
        assert type(None) in get_args(ann)
        # create 不含 inactive（新源不能直接建为停用）
        create_annotation = str(DataSourceCreateRequest.model_fields["status"].annotation)
        assert "inactive" not in create_annotation
        assert "active" in create_annotation


class TestDeleteDatasource:
    """D5: 软删除（status → inactive），保留采集历史。"""

    def test_delete_deactivates_source(self, client, auth_headers, db_override):
        ds_id = uuid.uuid4()
        ds = FakeDataSourceRecord(id=ds_id, status="active")
        session = FakeAsyncSession([FakeResult(ds)])
        db_override(session)
        resp = client.delete(f"/api/v1/datasources/{ds_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["source_id"] == str(ds_id)
        # 软删除语义: 不删行, 仅 status → inactive
        assert ds.status == "inactive"

    def test_delete_missing_returns_404(self, client, auth_headers, db_override):
        session = FakeAsyncSession([FakeResult(None)])
        db_override(session)
        resp = client.delete(f"/api/v1/datasources/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404
