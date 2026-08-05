"""Coverage boost: api/v1/auth.py — forgot-password 通道决策 (PLAN-015②)。

settings.forgot_password_delivery 决定是否回 token:
- out_of_band (默认): 仅写 Redis, 响应不回 token
- dev_return_token: 仅 dev 环境回 token (其他环境即使配了也仅回 submitted)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import auth as auth_router


@pytest.fixture
def fake_redis():
    """MagicMock 充当 Redis, 绕过 503 守门"""
    return MagicMock()


def _body(email: str = "u@x.com"):
    """轻量级请求体替身: ForgotPasswordRequest 字段仅校验 email"""
    return type("B", (), {"email": email})()


class TestForgotPasswordDelivery:
    @pytest.mark.asyncio
    @patch("app.api.v1.auth.auth_service")
    @patch("app.api.v1.auth.settings")
    async def test_out_of_band_default_never_returns_token(
        self, mock_settings, mock_svc, fake_redis
    ) -> None:
        """默认 out_of_band (生产安全): 即便 service 给了 token, 也不回."""
        mock_settings.forgot_password_delivery = "out_of_band"
        mock_settings.app_env = "development"
        mock_svc.forgot_password_request = AsyncMock(return_value="secret-token-xyz")

        result = await auth_router.forgot_password(
            body=_body(), session=None, redis=fake_redis,
        )
        assert result == {"submitted": True, "delivery": "out_of_band"}
        assert "token" not in result

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.auth_service")
    @patch("app.api.v1.auth.settings")
    async def test_dev_return_token_in_dev_env(
        self, mock_settings, mock_svc, fake_redis
    ) -> None:
        mock_settings.forgot_password_delivery = "dev_return_token"
        mock_settings.app_env = "development"
        mock_svc.forgot_password_request = AsyncMock(return_value="tok-abc")

        result = await auth_router.forgot_password(
            body=_body(), session=None, redis=fake_redis,
        )
        assert result["token"] == "tok-abc"
        assert result["delivery"] == "dev_return_token"

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.auth_service")
    @patch("app.api.v1.auth.settings")
    async def test_dev_return_token_suppressed_in_production(
        self, mock_settings, mock_svc, fake_redis
    ) -> None:
        """生产环境即便误配 dev_return_token, 也不回 token (fail-closed)."""
        mock_settings.forgot_password_delivery = "dev_return_token"
        mock_settings.app_env = "production"
        mock_svc.forgot_password_request = AsyncMock(return_value="tok-abc")

        result = await auth_router.forgot_password(
            body=_body(), session=None, redis=fake_redis,
        )
        assert "token" not in result
        assert result["submitted"] is True

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.auth_service")
    @patch("app.api.v1.auth.settings")
    async def test_dev_return_token_with_unknown_email_returns_none(
        self, mock_settings, mock_svc, fake_redis
    ) -> None:
        """service 对未注册邮箱回 None (反枚举保护), 路由层不应回 token."""
        mock_settings.forgot_password_delivery = "dev_return_token"
        mock_settings.app_env = "development"
        mock_svc.forgot_password_request = AsyncMock(return_value=None)

        result = await auth_router.forgot_password(
            body=_body("ghost@x.com"), session=None, redis=fake_redis,
        )
        assert "token" not in result
