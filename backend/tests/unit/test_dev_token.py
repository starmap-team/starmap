"""Coverage boost: core/security/dev_token.py — dev-token 集中守门 (PLAN-015③).

历史问题: `settings.app_env != "production"` 二元判定把 staging/testing 与
development 等同, 任何中间环境都接受 dev-token (即 admin 凭据).
本测试断言收紧后的环境白名单语义.
"""

from __future__ import annotations

import pytest

from app.core.security import dev_token
from app.core.security.dev_token import dev_token_identity, dev_token_role, is_dev_token_allowed


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
