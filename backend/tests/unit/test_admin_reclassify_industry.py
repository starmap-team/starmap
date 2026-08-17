"""Phase 3 Admin reclassify-industry 端点测试 (2026-08-17)。

锁定 POST /admin/positions/{id}/reclassify-industry 端点：
1. industry 必须是 industry_taxonomy canonical 桶（不允许「未分类」/模糊词）
2. reason ≥ 5 字
3. PG position_records.industry 字段被改写
4. Neo4j Position 节点 industry 属性同步
5. ReviewAuditLog 写入
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db_session, get_neo4j_driver
from app.main import app


class _FakeSession:
    """最小化 session fake：覆盖 position lookup + commit + refresh。"""

    def __init__(self, row) -> None:
        self._row = row
        self.commit_called = False
        self.refresh_called = False

    async def execute(self, stmt, *args, **kwargs):
        return SimpleNamespace(scalar_one_or_none=lambda: self._row)

    async def commit(self):
        self.commit_called = True

    async def refresh(self, obj):
        self.refresh_called = True
        return obj

    def add(self, obj):
        # 模拟 SQLAlchemy — 给对象一个 id 属性用于 audit log
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 42


class _FakeNeo4jDriver:
    """最小化 Neo4j driver fake — 验证 Cypher 是否被调用。"""

    def __init__(self):
        self.calls = []

    def session(self):
        return _FakeNeo4jSession(self)


class _FakeNeo4jSession:
    def __init__(self, driver):
        self.driver = driver
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *args):
        pass

    async def run(self, query, **params):
        self.driver.calls.append({"query": query, "params": params})
        return SimpleNamespace(single=lambda: {"r": 0})


def _install_overrides(row, driver=None):
    async def _override_session():
        yield _FakeSession(row)
    async def _override_user():
        return {"sub": "admin-user-id", "role": "admin", "username": "admin"}

    def _override_driver():
        return driver

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_neo4j_driver] = _override_driver


def _cleanup():
    app.dependency_overrides.clear()


def _make_row(industry: str | None, *, review_status: str = "approved"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=f"Test Position {uuid.uuid4()}",
        name_cn="",
        industry=industry,
        description="",
        created_at=None,
        review_status=review_status,
    )


def _call_endpoint(position_id, body):
    row = _make_row(body.pop("__initial_industry", "未分类"))
    driver = _FakeNeo4jDriver()
    _install_overrides(row, driver)
    try:
        client = TestClient(app)
        return client.post(f"/api/v1/admin/positions/{position_id}/reclassify-industry", json=body), row, driver
    finally:
        _cleanup()


class TestReclassifyIndustrySuccess:
    """正常路径：industry 是 canonical 桶，写 PG/Neo4j/audit。"""

    def test_canonical_industry_accepted(self):
        response, row, driver = _call_endpoint(
            uuid.uuid4(),
            {"industry": "互联网/IT", "reason": "运营修正：原本错分到「互联网/IT」，实际是 SaaS 类", "__initial_industry": "未分类"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["industry"] == "互联网/IT"
        assert data["neo4j_synced"] is True
        assert data["audit_log_id"] is not None
        # PG 字段被改写
        assert row.industry == "互联网/IT"
        # Neo4j sync 调用 1 次
        assert len(driver.calls) == 1
        # Audit log id 是 42（fake 分配）
        assert data["audit_log_id"] == 42

    def test_alias_industry_normalized(self):
        """输入 alias（信息技术/互联网）应被 normalize 到 canonical（互联网/IT）。"""
        response, row, _ = _call_endpoint(
            uuid.uuid4(),
            {"industry": "信息技术/互联网", "reason": "alias test", "__initial_industry": "未分类"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["industry"] == "互联网/IT"
        assert row.industry == "互联网/IT"

    def test_neo4j_query_params_correct(self):
        """Neo4j Cypher 必须传 canonical_id + industry。"""
        # 创建一个 row 并用 row.id 作为 URL position_id
        row = _make_row("未分类")
        driver = _FakeNeo4jDriver()
        _install_overrides(row, driver)
        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/admin/positions/{row.id}/reclassify-industry",
                json={"industry": "金融科技", "reason": "运营修正此岗位行业分类"},
            )
            assert response.status_code == 200, response.text
            assert len(driver.calls) == 1
            call = driver.calls[0]
            assert call["params"]["cid"] == str(row.id)
            assert call["params"]["industry"] == "金融科技"
            assert "MATCH (n:Position {canonical_id: $cid})" in call["query"]
        finally:
            _cleanup()


class TestReclassifyIndustryValidation:
    """输入校验：422 拒绝 invalid industry。"""

    def test_reject_unclassified_literal(self):
        """「未分类」字面量被拒绝（用户应填真实行业）。"""
        response, _, _ = _call_endpoint(
            uuid.uuid4(),
            {"industry": "未分类", "reason": "想保持空类别为未分类", "__initial_industry": "未分类"},
        )
        assert response.status_code == 422
        # HTTPException 直接抛 detail 字符串在 ErrorResponse envelope 里
        detail = response.json().get("detail", "")
        assert "未分类" in detail or "canonical" in detail.lower()

    def test_reject_generic_token(self):
        """模糊词（通用/综合/其他）被拒绝。"""
        for tok in ["通用", "综合", "其他", "misc", "other"]:
            response, _, _ = _call_endpoint(
                uuid.uuid4(),
                {"industry": tok, "reason": f"测试模糊词 {tok}", "__initial_industry": "未分类"},
            )
            assert response.status_code == 422, f"Generic token {tok!r} should be rejected"

    def test_reject_unknown_industry(self):
        """不在 canonical 桶中的 industry 被拒绝（防污染）。"""
        response, _, _ = _call_endpoint(
            uuid.uuid4(),
            {"industry": "外星科技", "reason": "测试未登记行业", "__initial_industry": "未分类"},
        )
        assert response.status_code == 422
        assert "canonical" in response.json()["detail"].lower() or "不在" in response.json()["detail"]

    def test_reject_short_reason(self):
        """reason < 5 字被 Pydantic 422 拒绝。"""
        response, _, _ = _call_endpoint(
            uuid.uuid4(),
            {"industry": "互联网/IT", "reason": "fix", "__initial_industry": "未分类"},
        )
        assert response.status_code == 422

    def test_position_not_found_404(self):
        """PositionRecord 不存在 → 404。"""
        from app.dependencies import get_current_user, get_db_session, get_neo4j_driver

        class _EmptySession:
            async def execute(self, *a, **kw):
                return SimpleNamespace(scalar_one_or_none=lambda: None)

        async def _override_session():
            yield _EmptySession()
        async def _override_user():
            return {"sub": "admin", "role": "admin"}
        def _override_driver():
            return None

        app.dependency_overrides[get_db_session] = _override_session
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_neo4j_driver] = _override_driver
        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/admin/positions/{uuid.uuid4()}/reclassify-industry",
                json={"industry": "互联网/IT", "reason": "测试 position 不存在"},
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestReclassifyIndustryNeo4jFailure:
    """Neo4j 不可用时不阻断 PG 写入，但响应标识 neo4j_synced=False。"""

    def test_neo4j_failure_does_not_break_pg_write(self):
        """Neo4j driver 抛异常时，PG 仍写入成功，响应标识 neo4j_synced=False。"""
        row = _make_row("未分类")

        class _FailingDriver:
            def session(self):
                raise RuntimeError("Neo4j down")

        async def _override_session():
            yield _FakeSession(row)
        async def _override_user():
            return {"sub": "admin", "role": "admin"}
        def _override_driver():
            return _FailingDriver()

        app.dependency_overrides[get_db_session] = _override_session
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_neo4j_driver] = _override_driver
        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/admin/positions/{row.id}/reclassify-industry",
                json={"industry": "互联网/IT", "reason": "Neo4j down test"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["neo4j_synced"] is False
            assert data["industry"] == "互联网/IT"
            # PG 字段被改写
            assert row.industry == "互联网/IT"
        finally:
            app.dependency_overrides.clear()


class TestReclassifyIndustryPermission:
    """鉴权：require_admin 装饰器强制 admin role。"""

    def test_non_admin_forbidden(self):
        """非 admin 用户被 403 拒绝。"""
        async def _override_session():
            yield _FakeSession(_make_row("未分类"))
        async def _override_user():
            return {"sub": "user-1", "role": "user"}  # 非 admin
        def _override_driver():
            return None

        app.dependency_overrides[get_db_session] = _override_session
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_neo4j_driver] = _override_driver
        try:
            client = TestClient(app)
            response = client.post(
                f"/api/v1/admin/positions/{uuid.uuid4()}/reclassify-industry",
                json={"industry": "互联网/IT", "reason": "权限测试"},
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
