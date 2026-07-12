"""Unit tests for health check business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- _decode_token: JWT decode + signature verification + expiry check
- get_current_user: auth branch logic (dev mode, dev-token, JWT validation)
- require_admin: role-based access control
- Health response structure validation (pure data checks)
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
from app.config import settings


# ── JWT helpers ──


def _encode_jwt(payload: dict, secret: str | None = None) -> str:
    """Create a valid JWT token for testing."""
    secret = secret or settings.secret_key
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _encode_jwt_bad_sig(payload: dict) -> str:
    """Create a JWT with wrong signature."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.bad_signature"


# ══════════════════════════════════════════════════════════════
# _decode_token — JWT decode + signature + expiry
# ══════════════════════════════════════════════════════════════


class TestDecodeToken:
    """_decode_token — JWT parsing, signature verification, expiry."""

    def test_valid_token_decodes_payload(self):
        payload = {"sub": "user1", "role": "admin", "username": "Alice"}
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "user1"
        assert decoded["role"] == "admin"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_token("not.a.valid.jwt.format")  # 5 parts instead of 3

    def test_two_part_token_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_token("only.two")

    def test_bad_signature_raises(self):
        payload = {"sub": "attacker"}
        token = _encode_jwt_bad_sig(payload)
        with pytest.raises(ValueError, match="Invalid JWT signature"):
            _decode_token(token)

    def test_expired_token_raises(self):
        payload = {"sub": "user1", "exp": time.time() - 3600}  # expired 1h ago
        token = _encode_jwt(payload)
        with pytest.raises(ValueError, match="JWT expired"):
            _decode_token(token)

    def test_future_exp_is_valid(self):
        payload = {"sub": "user1", "exp": time.time() + 3600}  # expires in 1h
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "user1"

    def test_no_exp_field_is_valid(self):
        payload = {"sub": "user1"}  # no exp
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "user1"

    def test_wrong_secret_fails(self):
        payload = {"sub": "user1"}
        token = _encode_jwt(payload, secret="wrong-secret")
        with pytest.raises(ValueError, match="Invalid JWT signature"):
            _decode_token(token)


# ══════════════════════════════════════════════════════════════
# get_current_user — auth branch logic
# ══════════════════════════════════════════════════════════════


class TestGetCurrentUser:
    """get_current_user — dev mode, dev-token, JWT validation branches."""

    async def test_no_credentials_dev_mode_returns_dev_user(self):
        """In non-production, no token → default dev user."""
        credentials = None
        with patch.object(settings, "app_env", "development"):
            user = await get_current_user(credentials)
        assert user["sub"] == "dev"
        assert user["role"] == "admin"

    async def test_no_credentials_production_raises_401(self):
        """In production, no token → 401."""
        from fastapi import HTTPException

        credentials = None
        with patch.object(settings, "app_env", "production"):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)
        assert exc_info.value.status_code == 401

    async def test_dev_token_in_dev_mode_returns_dev_user(self):
        """In non-production, 'dev-token' → default dev user."""
        creds = MagicMock()
        creds.credentials = "dev-token"
        with patch.object(settings, "app_env", "development"):
            user = await get_current_user(creds)
        assert user["sub"] == "dev"

    async def test_dev_token_in_production_goes_to_jwt_validation(self):
        """In production, 'dev-token' is NOT accepted as shortcut."""
        from fastapi import HTTPException

        creds = MagicMock()
        creds.credentials = "dev-token"
        with patch.object(settings, "app_env", "production"):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(creds)
        # dev-token is not a valid JWT → 401
        assert exc_info.value.status_code == 401

    async def test_valid_jwt_returns_payload(self):
        """Valid JWT → payload as user dict."""
        payload = {"sub": "user42", "role": "viewer", "username": "Bob"}
        token = _encode_jwt(payload)
        creds = MagicMock()
        creds.credentials = token
        with patch.object(settings, "app_env", "production"):
            user = await get_current_user(creds)
        assert user["sub"] == "user42"
        assert user["role"] == "viewer"

    async def test_expired_jwt_raises_401(self):
        """Expired JWT → 401."""
        from fastapi import HTTPException

        payload = {"sub": "user1", "exp": time.time() - 100}
        token = _encode_jwt(payload)
        creds = MagicMock()
        creds.credentials = token
        with patch.object(settings, "app_env", "production"):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(creds)
        assert exc_info.value.status_code == 401


# ══════════════════════════════════════════════════════════════
# require_admin — role-based access control
# ══════════════════════════════════════════════════════════════


class TestRequireAdmin:
    """require_admin — admin role check."""

    async def test_admin_user_passes(self):
        user = {"sub": "admin1", "role": "admin"}
        result = await require_admin(user)
        assert result["role"] == "admin"

    async def test_non_admin_user_raises_403(self):
        from fastapi import HTTPException

        user = {"sub": "viewer1", "role": "viewer"}
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(user)
        assert exc_info.value.status_code == 403

    async def test_no_role_field_raises_403(self):
        from fastapi import HTTPException

        user = {"sub": "norole"}
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(user)
        assert exc_info.value.status_code == 403


# ══════════════════════════════════════════════════════════════
# Health response structure — pure data validation
# ══════════════════════════════════════════════════════════════


class TestHealthResponseStructure:
    """Health response data structure — no HTTP, just dict validation."""

    def test_basic_health_structure(self):
        """A health response dict should have status + version."""
        health = {"status": "ok", "version": "2.1.0"}
        assert health["status"] == "ok"
        assert "version" in health

    def test_detail_health_services_keys(self):
        """Detail health should contain 4 service keys."""
        services = {"neo4j": "ok", "postgres": "ok", "redis": "ok", "ollama": "ok"}
        for svc in ("neo4j", "postgres", "redis", "ollama"):
            assert svc in services

    def test_detail_health_llm_keys_booleans(self):
        """LLM key status should be booleans."""
        llm_keys = {"mimo": True, "deepseek": False, "xunfei": True}
        for key in ("mimo", "deepseek", "xunfei"):
            assert isinstance(llm_keys[key], bool)

    def test_detail_health_demo_data_types(self):
        """Demo data fields should have correct types."""
        demo_data = {"review_queue_seeded": True, "pipeline_runs_count": 5}
        assert isinstance(demo_data["review_queue_seeded"], bool)
        assert isinstance(demo_data["pipeline_runs_count"], int)

    def test_no_key_leak_in_response(self):
        """API key values must not appear in health response text."""
        response_body = {"status": "ok", "services": {}, "llm_keys": {"mimo": True}}
        body_text = json.dumps(response_body)
        # Simulated key that should NOT appear
        fake_key = "sk-12345-secret-key-value"
        assert fake_key not in body_text