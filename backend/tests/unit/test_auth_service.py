"""Unit tests for auth/JWT business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- _decode_token: JWT decode, signature verification, expiry check
- get_current_user: dev-mode bypass, dev-token acceptance, JWT validation
- require_admin: role-based access control
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dependencies import _decode_token, get_current_user, require_admin


# ── JWT helpers ──


def _encode_payload(payload: dict, secret: str = "test-secret-key") -> str:
    """Create a valid JWT token for testing."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _make_credentials(token: str) -> MagicMock:
    """Mock HTTPAuthorizationCredentials with a given token."""
    creds = MagicMock()
    creds.credentials = token
    return creds


# ══════════════════════════════════════════════════════════════
# _decode_token — JWT decode logic
# ══════════════════════════════════════════════════════════════


class TestDecodeToken:
    """_decode_token — JWT structure, signature, and expiry validation."""

    def test_valid_token_decodes(self):
        payload = {"sub": "user1", "role": "admin", "exp": time.time() + 3600}
        token = _encode_payload(payload)
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            result = _decode_token(token)
        assert result["sub"] == "user1"
        assert result["role"] == "admin"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_token("not.a.valid.jwt.extra")

    def test_two_part_token_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_token("only.two")

    def test_tampered_signature_raises(self):
        payload = {"sub": "user1", "role": "admin"}
        token = _encode_payload(payload) + "tampered"
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            with pytest.raises(ValueError, match="Invalid JWT signature"):
                _decode_token(token)

    def test_wrong_secret_raises(self):
        payload = {"sub": "user1", "role": "admin"}
        token = _encode_payload(payload, secret="wrong-secret")
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            with pytest.raises(ValueError, match="Invalid JWT signature"):
                _decode_token(token)

    def test_expired_token_raises(self):
        payload = {"sub": "user1", "exp": time.time() - 3600}
        token = _encode_payload(payload)
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            with pytest.raises(ValueError, match="expired"):
                _decode_token(token)

    def test_no_exp_is_valid(self):
        payload = {"sub": "user1", "role": "admin"}
        token = _encode_payload(payload)
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            result = _decode_token(token)
        assert result["sub"] == "user1"


# ══════════════════════════════════════════════════════════════
# get_current_user — auth branch logic
# ══════════════════════════════════════════════════════════════


class TestGetCurrentUser:
    """get_current_user — dev-mode bypass, dev-token, JWT validation."""

    async def test_no_credentials_dev_mode_returns_dev_user(self):
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.app_env = "development"
            result = await get_current_user(credentials=None)
        assert result["sub"] == "dev"
        assert result["role"] == "admin"

    async def test_no_credentials_production_raises_401(self):
        from fastapi import HTTPException
        with (
            patch("app.dependencies.settings") as mock_settings,
            patch("app.dependencies.audit_log"),
        ):
            mock_settings.app_env = "production"
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=None)
            assert exc_info.value.status_code == 401

    async def test_dev_token_in_dev_mode_returns_dev_user(self):
        creds = _make_credentials("dev-token")
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.app_env = "development"
            result = await get_current_user(credentials=creds)
        assert result["sub"] == "dev"
        assert result["role"] == "admin"

    async def test_valid_jwt_returns_payload(self):
        payload = {"sub": "user1", "role": "viewer", "exp": time.time() + 3600}
        token = _encode_payload(payload)
        creds = _make_credentials(token)
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.app_env = "production"
            mock_settings.secret_key = "test-secret-key"
            result = await get_current_user(credentials=creds)
        assert result["sub"] == "user1"
        assert result["role"] == "viewer"

    async def test_invalid_jwt_raises_401(self):
        from fastapi import HTTPException
        creds = _make_credentials("invalid.jwt.token")
        with (
            patch("app.dependencies.settings") as mock_settings,
            patch("app.dependencies.audit_log"),
        ):
            mock_settings.app_env = "production"
            mock_settings.secret_key = "test-secret-key"
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=creds)
            assert exc_info.value.status_code == 401


# ══════════════════════════════════════════════════════════════
# require_admin — role-based access
# ══════════════════════════════════════════════════════════════


class TestRequireAdmin:
    """require_admin — admin role check."""

    async def test_admin_user_passes(self):
        user = {"sub": "admin1", "role": "admin"}
        result = await require_admin(user)
        assert result["role"] == "admin"

    async def test_non_admin_raises_403(self):
        from fastapi import HTTPException
        user = {"sub": "viewer1", "role": "viewer"}
        with (
            patch("app.dependencies.audit_log"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await require_admin(user)
        assert exc_info.value.status_code == 403

    async def test_no_role_field_raises_403(self):
        from fastapi import HTTPException
        user = {"sub": "norole"}
        with (
            patch("app.dependencies.audit_log"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await require_admin(user)
        assert exc_info.value.status_code == 403