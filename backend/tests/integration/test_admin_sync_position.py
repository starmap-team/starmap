"""Integration tests for POST /api/v1/admin/sync/all-positions-to-neo4j (Phase 02 D-02).

C-1 SSOT 修复：PG position_records 全量幂等 MERGE 到 Neo4j Position 节点。
沿 Phase 18 测试协议：只 mock Neo4j driver 与 session_factory，不起真实图库。
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_neo4j_driver
from app.main import app

ENDPOINT = "/api/v1/admin/sync/all-positions-to-neo4j"

_ADMIN_USER = {"sub": "dev", "role": "admin", "username": "developer"}
_VIEWER_USER = {"sub": "viewer", "role": "viewer", "username": "viewer"}


class _FakeRow(tuple):
    """PG row stand-in: (id, name, industry, review_status)."""


def _make_rows(n: int) -> list[tuple[Any, str, str, str]]:
    return [
        (uuid.uuid4(), f"岗位-{i}", "信息技术", "approved")
        for i in range(n)
    ]


def _make_session_factory(rows: list[tuple[Any, str, str, str]]) -> Any:
    """Build an async session_factory whose execute() returns the given rows."""
    result = AsyncMock()
    result.all = lambda: rows

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _factory_cm() -> Any:
        yield session

    def _factory() -> Any:
        return _factory_cm()

    return _factory


def _make_driver(*, fail_on: set[str] | None = None, pruned: int = 0) -> Any:
    """Neo4j driver stand-in. `fail_on` holds canonical_ids whose MERGE raises."""
    fail_on = fail_on or set()

    class _Session:
        async def run(self, query: str, **params: Any) -> Any:
            if "DETACH DELETE" in query:
                single_result = AsyncMock()
                single_result.single = AsyncMock(return_value={"deleted": pruned})
                return single_result
            cid = params.get("cid")
            if cid in fail_on:
                raise RuntimeError(f"neo4j write failed for {cid}")
            return AsyncMock()

    class _Driver:
        def session(self) -> Any:
            @asynccontextmanager
            async def _cm() -> Any:
                yield _Session()

            return _cm()

    return _Driver()


@pytest.fixture
def client() -> Any:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _admin_user() -> Any:
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


class TestSyncAllPositionsEndpoint:
    def test_full_backfill_success(self, client: TestClient) -> None:
        """全量补齐成功：synced == PG 行数，failed 为空。"""
        rows = _make_rows(4)
        app.dependency_overrides[get_neo4j_driver] = lambda: _make_driver()
        try:
            with patch(
                "app.db.session.get_session_factory",
                return_value=_make_session_factory(rows),
            ):
                resp = client.post(ENDPOINT)
        finally:
            app.dependency_overrides.pop(get_neo4j_driver, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["synced"] == 4
        assert body["total"] == 4
        assert body["failed"] == []
        assert body["pruned"] == 0
        assert body["started_at"] and body["finished_at"]

    def test_single_record_failure_is_listed(self, client: TestClient) -> None:
        """单条写 Neo4j 失败：其余记录照常 synced，失败明细进 failed 列表（不阻断）。"""
        rows = _make_rows(3)
        bad_cid = str(rows[1][0])
        app.dependency_overrides[get_neo4j_driver] = lambda: _make_driver(fail_on={bad_cid})
        try:
            with patch(
                "app.db.session.get_session_factory",
                return_value=_make_session_factory(rows),
            ):
                resp = client.post(ENDPOINT)
        finally:
            app.dependency_overrides.pop(get_neo4j_driver, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["synced"] == 2
        assert body["total"] == 3
        assert len(body["failed"]) == 1
        assert body["failed"][0]["canonical_id"] == bad_cid
        assert "neo4j write failed" in body["failed"][0]["error"]

    def test_prune_legacy_reports_pruned_count(self, client: TestClient) -> None:
        """prune_legacy=true：剪枝无 canonical_id 的遗留节点并回报 pruned 数。"""
        rows = _make_rows(2)
        app.dependency_overrides[get_neo4j_driver] = lambda: _make_driver(pruned=6)
        try:
            with patch(
                "app.db.session.get_session_factory",
                return_value=_make_session_factory(rows),
            ):
                resp = client.post(f"{ENDPOINT}?prune_legacy=true")
        finally:
            app.dependency_overrides.pop(get_neo4j_driver, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["synced"] == 2
        assert body["pruned"] == 6

    def test_non_admin_forbidden(self, client: TestClient) -> None:
        """非 admin 角色被 require_admin 拦截（403）。"""
        app.dependency_overrides[get_current_user] = lambda: _VIEWER_USER
        app.dependency_overrides[get_neo4j_driver] = lambda: _make_driver()
        try:
            resp = client.post(ENDPOINT)
        finally:
            app.dependency_overrides.pop(get_neo4j_driver, None)

        assert resp.status_code == 403
        assert "Admin" in resp.json()["detail"]

    def test_driver_unavailable_returns_zero(self, client: TestClient) -> None:
        """Neo4j 不可用（driver=None）：返回 0 同步结果而非 500。"""
        app.dependency_overrides[get_neo4j_driver] = lambda: None
        try:
            with patch(
                "app.db.session.get_session_factory",
                return_value=_make_session_factory(_make_rows(3)),
            ):
                resp = client.post(ENDPOINT)
        finally:
            app.dependency_overrides.pop(get_neo4j_driver, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["synced"] == 0
        assert body["total"] == 0
