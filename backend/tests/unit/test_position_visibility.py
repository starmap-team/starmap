"""P1-9 (functional-review 2026-08-13): 岗位可见性策略 —— 非 admin 无法查看未发布岗位。

list_positions 此前只读 query 参数、无角色校验：任何登录用户传
?status=pending_review 或 include_all=true 即可看到未发布/已驳回岗位。
修复后非 admin 强制锁定 status=approved 并忽略 include_all。
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db_session
from app.main import app


class FakePositionRow:
    """模拟 PositionRecord 行（仅含路由用到的字段）。"""

    def __init__(self, name: str, review_status: str) -> None:
        self.id = uuid.uuid4()
        self.name = name
        self.name_cn = ""
        self.industry = "IT"
        self.description = ""
        self.created_at = None
        self.review_status = review_status


class FakeScalars:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    """统一 fake result：同时支持 scalar/scalars/all，避免 SQL 文本分支误判。"""

    def __init__(self, rows, scalar_value=None) -> None:
        self._rows = rows
        self._scalar_value = scalar_value if scalar_value is not None else (len(rows) if rows else 0)

    def scalar(self):
        return self._scalar_value

    def scalars(self):
        return FakeScalars(self._rows)

    def all(self):
        return self._rows


class FakeAsyncSession:
    """按 SQL 文本特征分流：count → 数字；列表 → 行；技能关系 → 空。"""

    def __init__(self, all_rows) -> None:
        self._all_rows = all_rows
        # 记录执行过的 SQL，供断言可见性过滤
        self.executed_sql: list[str] = []

    async def execute(self, stmt):
        text = str(stmt)
        self.executed_sql.append(text)
        lowered = text.lower()
        # review_status 会出现在 SELECT 列中（position_records.review_status），
        # 判定过滤必须要求 WHERE 子句也引用它（WHERE ... review_status = $1）。
        has_status_filter = "where" in lowered and "review_status" in lowered
        if "count(" in lowered:
            if has_status_filter:
                return FakeResult([], scalar_value=len([r for r in self._all_rows if r.review_status == "approved"]))
            return FakeResult([], scalar_value=len(self._all_rows))
        if "skill_records" in lowered:
            # 技能批量查询返回 (SkillRecord, PositionSkillRelation) 对 → 空即可
            return FakeResult([])
        if has_status_filter:
            return FakeResult([r for r in self._all_rows if r.review_status == "approved"])
        return FakeResult(self._all_rows)


def _make_client(user_role: str, rows) -> tuple[TestClient, FakeAsyncSession]:
    session = FakeAsyncSession(rows)

    def _override_user():
        return {"sub": "test-user", "role": user_role, "username": "tester"}

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db_session] = lambda: session
    client = TestClient(app)
    return client, session


def _cleanup():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db_session, None)


def test_non_admin_forced_approved():
    approved = FakePositionRow("后端工程师", "approved")
    pending = FakePositionRow("未发布岗位", "pending_review")
    client, session = _make_client("user", [approved, pending])
    try:
        # 非 admin 传 status=pending_review + include_all=true
        resp = client.get(
            "/api/v1/positions?status=pending_review&include_all=true",
            headers={"Authorization": "Bearer dev"},
        )
        assert resp.status_code == 200
        body = resp.json()
        names = [item.get("name") for item in body.get("items", [])]
        assert "未发布岗位" not in names
        assert "后端工程师" in names
        # include_all 被忽略：查询 SQL 必须含 review_status = 'approved' 过滤
        assert any(
            "where" in sql.lower() and "review_status" in sql.lower()
            for sql in session.executed_sql
        )
    finally:
        _cleanup()


def test_admin_can_see_pending_with_include_all():
    approved = FakePositionRow("后端工程师", "approved")
    pending = FakePositionRow("未发布岗位", "pending_review")
    client, session = _make_client("admin", [approved, pending])
    try:
        resp = client.get(
            "/api/v1/positions?include_all=true",
            headers={"Authorization": "Bearer dev"},
        )
        assert resp.status_code == 200
        body = resp.json()
        names = [item.get("name") for item in body.get("items", [])]
        # admin + include_all=true → 可见全部状态
        assert "未发布岗位" in names
    finally:
        _cleanup()


def test_non_admin_default_approved_only():
    approved = FakePositionRow("后端工程师", "approved")
    pending = FakePositionRow("未发布岗位", "pending_review")
    client, session = _make_client("user", [approved, pending])
    try:
        # 不带任何参数 → 非 admin 也只看 approved
        resp = client.get("/api/v1/positions", headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200
        names = [item.get("name") for item in resp.json().get("items", [])]
        assert "未发布岗位" not in names
        assert any(
            "where" in sql.lower() and "review_status" in sql.lower()
            for sql in session.executed_sql
        )
    finally:
        _cleanup()
