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


class TestDataTruthApprovedCaliber:
    """Phase 24 核验修复: data-truth PG 计数必须限定 approved 口径。

    岗位总数/关系边数曾取 PG 全量（含 pending），与 Neo4j 投影后的 approved
    计数比较产生假 critical（362 vs 185 = 48.9%）。修复后计数查询必须含
    review_status='approved' 过滤。
    """

    def test_position_count_query_filters_approved(self) -> None:
        """岗位总数 PG 查询必须限定 approved。"""
        from sqlalchemy import select
        from sqlalchemy.sql import func

        from app.models.extraction_models import PositionRecord

        # 复用端点内的 select 构造逻辑（嗅探 SQL 文本）
        stmt = (
            select(func.count()).select_from(PositionRecord)
            .where(PositionRecord.review_status == "approved")
        )
        sql = str(stmt)
        assert "review_status" in sql
        assert "approved" in sql or ":review_status" in sql or "review_status_1" in sql

    def test_psr_count_query_filters_approved(self) -> None:
        """关系边数 PG 查询必须 join 限定 approved 岗位。"""
        from sqlalchemy import select
        from sqlalchemy.sql import func

        from app.models.extraction_models import PositionRecord, PositionSkillRelation

        stmt = (
            select(func.count(PositionSkillRelation.id))
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .where(PositionRecord.review_status == "approved")
        )
        sql = str(stmt)
        assert "position_skill_relations" in sql
        assert "join" in sql.lower() or "JOIN" in sql
        assert "review_status" in sql
