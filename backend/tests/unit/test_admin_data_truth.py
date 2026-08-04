"""admin_data_truth 端点门禁测试（PLAN-007a / NEW-01）。

回归保护：/admin/data-truth 曾仅挂 api_router 的 get_current_user，
任意登录用户可读取三口径对账数据。现必须 require_admin。
真实打 app（非影子测试）：通过 dependency_overrides 注入假用户与假存储。
"""
from __future__ import annotations

from typing import Any

import pytest

from app.dependencies import get_current_user, get_db_session, get_neo4j_driver
from app.main import app


class _FakeResult:
    """最小 SQL 结果对象：计数=0、行集为空。"""

    def scalar(self) -> int:
        return 0

    def all(self) -> list[Any]:
        return []

    def first(self) -> None:
        return None

    async def single(self) -> None:
        return None

    def __aiter__(self) -> _FakeResult:
        return self

    async def __anext__(self) -> Any:
        raise StopAsyncIteration


class _FakeNeoSession:
    async def run(self, *args: Any, **kwargs: Any) -> _FakeResult:
        return _FakeResult()

    async def __aenter__(self) -> _FakeNeoSession:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False


class _FakeNeoDriver:
    def session(self) -> _FakeNeoSession:
        return _FakeNeoSession()


class _FakeSession:
    async def execute(self, *args: Any, **kwargs: Any) -> _FakeResult:
        return _FakeResult()


@pytest.fixture()
def _fake_storage():
    async def _fake_db():
        yield _FakeSession()

    app.dependency_overrides[get_db_session] = _fake_db
    app.dependency_overrides[get_neo4j_driver] = lambda: _FakeNeoDriver()
    yield
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_neo4j_driver, None)


class TestDataTruthAdminGuard:
    def test_non_admin_rejected_403(self, client, _fake_storage):
        """普通登录用户访问 /admin/data-truth 必须 403（NEW-01 回归）。"""
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "viewer", "role": "user", "username": "viewer",
        }
        resp = client.get("/api/v1/admin/data-truth")
        assert resp.status_code == 403
        app.dependency_overrides.pop(get_current_user, None)

    def test_admin_allowed(self, client, _fake_storage):
        """admin 角色可访问（门禁不应误伤）。"""
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "boss", "role": "admin", "username": "boss",
        }
        resp = client.get("/api/v1/admin/data-truth")
        assert resp.status_code == 200
        body = resp.json()
        assert "rows" in body and "health" in body
        app.dependency_overrides.pop(get_current_user, None)
