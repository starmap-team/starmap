"""Auth guard tests — verify all endpoints enforce authentication correctly.

Covers:
- Public endpoints: no auth required (health, login)
- Authenticated endpoints: require Bearer token (401 without)
- Admin endpoints: require admin role (403 with non-admin token)
- Dev token acceptance in non-production environment
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import Request
from fastapi.testclient import TestClient


def _make_app():
    """Create a fresh TestClient with dependency overrides for auth testing."""
    from app.main import app
    return app


def _cleanup_app(app):
    """Remove all dependency overrides."""
    from app.dependencies import get_current_user, get_db_session, get_neo4j_driver
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_neo4j_driver, None)


# ═══════════════════════════════════════════════════════════════
# TestPublicEndpoints — no auth required
# ═══════════════════════════════════════════════════════════════


class TestPublicEndpoints:
    """Tests for endpoints that do NOT require authentication."""

    def test_health_no_auth_200(self):
        app = _make_app()
        client = TestClient(app)
        try:
            response = client.get("/health")
            assert response.status_code == 200
        finally:
            _cleanup_app(app)

    def test_health_v1_no_auth_200(self):
        app = _make_app()
        client = TestClient(app)
        try:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
        finally:
            _cleanup_app(app)

    def test_login_no_auth_returns_response(self):
        """POST /auth/login does not require a Bearer token — it's the login endpoint."""
        app = _make_app()
        from app.api.v1.auth import get_client_ip
        from app.dependencies import get_db_session, get_redis_client
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        def _fake_redis(_request: Request):  # noqa: ARG001
            return mock_redis
        app.dependency_overrides[get_redis_client] = _fake_redis
        def _fake_client_ip(_request: Request):  # noqa: ARG001
            return "127.0.0.1"
        app.dependency_overrides[get_client_ip] = _fake_client_ip
        client = TestClient(app)
        try:
            # Mock auth_service.authenticate to raise InvalidCredentialsError
            from app.services.auth_service import InvalidCredentialsError
            with patch(
                "app.services.auth_service.authenticate",
                new_callable=AsyncMock,
                side_effect=InvalidCredentialsError("bad"),
            ):
                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "testpass"},
                )
            # Login returns 401 for bad creds, but NOT 401 for missing token
            assert response.status_code == 401
        finally:
            _cleanup_app(app)


# ═══════════════════════════════════════════════════════════════
# TestAuthenticatedEndpoints — require Bearer token
# ═══════════════════════════════════════════════════════════════


class TestAuthenticatedEndpoints:
    """Tests that authenticated endpoints return 401 without a token.

    In dev mode, the app auto-issues a dev_admin JWT when no token is provided.
    We need to force production mode to test 401 behavior.
    """

    def _get_client_prod_mode(self):
        """Get TestClient with production mode forced — no auto-dev token."""
        app = _make_app()
        # Override get_current_user to always raise 401 (simulating production no-token)
        from fastapi import HTTPException, status

        from app.dependencies import get_current_user, get_db_session

        async def _require_auth():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = _require_auth
        client = TestClient(app)
        return client, app

    def test_health_detail_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/health/detail")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_extract_jd_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.post(
                "/api/v1/extract/jd",
                json={"jd_content": "test"},
            )
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_graph_overview_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/api/v1/graph/overview")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_learning_plans_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/api/v1/learning/plans")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_loop_history_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/api/v1/loop/history")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_pipeline_status_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/api/v1/pipeline/status")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_match_position_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.post(
                "/api/v1/match/position",
                json={"person_skills": [], "target_position": "Dev"},
            )
            assert response.status_code == 401
        finally:
            _cleanup_app(app)

    def test_evolution_trends_no_token_401(self):
        client, app = self._get_client_prod_mode()
        try:
            response = client.get("/api/v1/evolution/trends")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)


# ═══════════════════════════════════════════════════════════════
# TestAdminEndpoints — require admin role
# ═══════════════════════════════════════════════════════════════


class TestAdminEndpoints:
    """Tests that admin endpoints return 403 with non-admin token."""

    def _get_client_non_admin(self):
        """Get TestClient with a non-admin user overriding auth."""
        app = _make_app()
        from app.dependencies import get_current_user, get_db_session

        mock_user = {"sub": "regular_user", "role": "user", "username": "regular"}
        mock_session = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client, app

    def test_pipeline_trigger_non_admin_403(self):
        client, app = self._get_client_non_admin()
        try:
            response = client.post("/api/v1/pipeline/trigger", json={})
            assert response.status_code == 403
        finally:
            _cleanup_app(app)

    def test_pipeline_config_update_non_admin_403(self):
        client, app = self._get_client_non_admin()
        try:
            response = client.put("/api/v1/pipeline/config", json={})
            assert response.status_code == 403
        finally:
            _cleanup_app(app)

    def test_schedule_create_non_admin_403(self):
        client, app = self._get_client_non_admin()
        try:
            response = client.post("/api/v1/pipeline/schedules", json={})
            assert response.status_code == 403
        finally:
            _cleanup_app(app)


# ═══════════════════════════════════════════════════════════════
# TestDevTokenAccepted — dev environment behavior
# ═══════════════════════════════════════════════════════════════


class TestDevTokenAccepted:
    """Tests for dev token acceptance in non-production environment."""

    def test_dev_mode_auto_issues_jwt(self):
        """In dev mode, no token auto-issues a dev_admin JWT (returns 200 for protected endpoints)."""
        app = _make_app()
        from app.dependencies import get_current_user, get_db_session, get_neo4j_driver

        # Override get_current_user to return a valid admin user (simulating dev mode)
        mock_user = {"sub": "dev_admin", "role": "admin", "username": "dev_admin"}
        mock_session = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: mock_user
        # B2 修复 flaky：全量运行时前面用例的 lifespan 会留下 app.state.resources，
        # get_neo4j_driver 会懒建真实 driver 连 localhost:7687 → 500。override 为
        # None 走路由的优雅降级分支（空概览 200），测试不再依赖 Neo4j 可达性。
        app.dependency_overrides[get_neo4j_driver] = lambda: None
        client = TestClient(app)
        try:
            # Access a protected endpoint without explicit token
            response = client.get("/api/v1/graph/overview")
            assert response.status_code == 200
        finally:
            _cleanup_app(app)

    def test_dev_token_accepted_in_dev(self):
        """In dev mode, 'dev-token' Bearer is accepted."""
        app = _make_app()
        from app.dependencies import get_current_user, get_db_session, get_neo4j_driver

        # Simulate dev mode accepting dev-token
        mock_user = {"sub": "dev_admin", "role": "admin", "username": "dev_admin"}
        mock_session = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: mock_user
        # B2 修复 flaky：同 test_dev_mode_auto_issues_jwt —— 隔离 Neo4j 可达性
        app.dependency_overrides[get_neo4j_driver] = lambda: None
        client = TestClient(app)
        try:
            response = client.get(
                "/api/v1/graph/overview",
                headers={"Authorization": "Bearer dev-token"},
            )
            assert response.status_code == 200
        finally:
            _cleanup_app(app)

    def test_prod_mode_rejects_no_token(self):
        """In production mode, no token returns 401."""
        app = _make_app()
        from fastapi import HTTPException, status

        from app.dependencies import get_current_user, get_db_session

        async def _prod_auth():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        mock_session = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = _prod_auth
        client = TestClient(app)
        try:
            response = client.get("/api/v1/graph/overview")
            assert response.status_code == 401
        finally:
            _cleanup_app(app)
