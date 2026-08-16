"""Coverage boost: services/dev_token.py — dev-token 集中守门 (PLAN-015③).

历史问题: `settings.app_env != "production"` 二元判定把 staging/testing 与
development 等同, 任何中间环境都接受 dev-token (即 admin 凭据).
本测试断言收紧后的环境白名单语义.
"""

from __future__ import annotations

import pytest

from app.services import dev_token
from app.services.dev_token import dev_token_identity, dev_token_role, is_dev_token_allowed


@pytest.fixture
def restore_settings():
    """恢复 app_env/dev_anon_admin 设置, 避免其它测试间污染。"""
    original_env = dev_token.settings.app_env
    original_daa = dev_token.settings.dev_anon_admin
    yield
    dev_token.settings.app_env = original_env
    dev_token.settings.dev_anon_admin = original_daa


class TestIsDevTokenAllowed:
    @pytest.mark.parametrize("env", ["production", "staging", "testing", "ci", "test"])
    def test_hard_reject_in_non_dev_envs(self, restore_settings, env: str) -> None:
        """任何"看起来不像开发"的环境: 永远拒 dev-token."""
        dev_token.settings.app_env = env
        assert is_dev_token_allowed("dev-token") is False

    @pytest.mark.parametrize("env", ["development", "dev", "local"])
    def test_accept_in_dev_envs(self, restore_settings, env: str) -> None:
        dev_token.settings.app_env = env
        assert is_dev_token_allowed("dev-token") is True

    def test_unknown_env_defaults_to_reject(self, restore_settings) -> None:
        """fail-closed: 未识别环境默认拒 (不再默认放行)."""
        dev_token.settings.app_env = "preview"
        assert is_dev_token_allowed("dev-token") is False

    def test_non_dev_token_string_always_rejected(self, restore_settings) -> None:
        """即使环境是 dev, 其它 token 也不走 dev-token 路径."""
        dev_token.settings.app_env = "development"
        assert is_dev_token_allowed("some-jwt") is False
        assert is_dev_token_allowed("") is False


class TestDevTokenRole:
    def test_default_viewer(self, restore_settings) -> None:
        dev_token.settings.dev_anon_admin = False
        assert dev_token_role() == "viewer"

    def test_opt_in_admin(self, restore_settings) -> None:
        dev_token.settings.dev_anon_admin = True
        assert dev_token_role() == "admin"


class TestDevTokenIdentity:
    def test_identity_shape(self, restore_settings) -> None:
        dev_token.settings.dev_anon_admin = False
        assert dev_token_identity() == {"sub": "dev", "role": "viewer", "username": "developer"}

    def test_identity_admin_when_opt_in(self, restore_settings) -> None:
        dev_token.settings.dev_anon_admin = True
        assert dev_token_identity()["role"] == "admin"
        assert dev_token_identity()["sub"] == "dev"


# ═══════════════════════════════════════════════════════════════════════
# CONCERN 1.4 (security audit 2026-08-15): dev-token cannot reach admin
# endpoints when APP_ENV=production.
#
# Plan:
# - Audit commit `3772af2d` tightened the dev-token to viewer-scoped
#   (`require_authenticated` instead of trusting cached role).
# - `services/dev_token.py` line 33-37 already refuses dev-token in
#   production via `_HARD_REJECT_ENVS`.
# - These tests pin BOTH layers:
#     (1) `is_dev_token_allowed('dev-token')` is False in production
#         (so the dev-token never even yields a viewer identity);
#     (2) `get_current_user` itself raises 401 in production when the
#         only presented credential is dev-token (defence in depth).
# ═══════════════════════════════════════════════════════════════════════


class TestDevTokenProductionGuard:
    """CONCERN 1.4: dev-token must NEVER be honored when APP_ENV=production."""

    def test_is_dev_token_rejected_when_production(self, restore_settings: object) -> None:
        """services/dev_token.py line 33-37: _HARD_REJECT_ENVS refuses
        'production'. This is the first guard — if it returns False,
        get_current_user falls through to JWT verification and dev-token
        never reaches require_admin.
        """
        dev_token.settings.app_env = "production"
        assert is_dev_token_allowed("dev-token") is False

    def test_is_dev_token_rejected_when_production_dev_anon_admin_true(
        self, restore_settings: object
    ) -> None:
        """Even if an operator explicitly opts in dev_anon_admin in
        production (which config.py refuses at startup), the dev-token
        path is hard-closed. This is a defence-in-depth check that does
        NOT rely on the config-level guard."""
        dev_token.settings.app_env = "production"
        dev_token.settings.dev_anon_admin = True
        assert is_dev_token_allowed("dev-token") is False

    def test_get_current_user_rejects_dev_token_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even if `is_dev_token_allowed` were bypassed, `get_current_user`
        itself (app/dependencies.py line 108) requires a valid Bearer
        token in production. The dev-token is not a valid JWT, so it
        must raise 401.
        """
        import asyncio

        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        from app.config import settings as app_settings
        from app.dependencies import get_current_user

        monkeypatch.setattr(app_settings, "app_env", "production")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token")

        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_current_user(credentials=creds))
        assert exc.value.status_code == 401

    def test_require_admin_403s_dev_token_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """End-to-end: even if a dev-token were honoured with role=viewer,
        require_admin must reject with 403 — admin endpoints are gated by
        role, not by token type. This pins the chain.
        """
        import asyncio

        from fastapi import HTTPException

        from app.dependencies import require_admin

        # Bypass dev-token rejection to simulate a viewer payload
        monkeypatch.setattr("app.services.dev_token.is_dev_token_allowed", lambda _t: True)

        async def _call() -> None:
            await require_admin(user={"sub": "dev", "role": "viewer", "username": "developer"})

        with pytest.raises(HTTPException) as exc:
            asyncio.run(_call())
        assert exc.value.status_code == 403
        assert "Admin access required" in str(exc.value.detail)
