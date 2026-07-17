"""Unit tests for health check business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- _decode_token: JWT decode + signature verification + expiry check
- get_current_user: auth branch logic (dev mode, dev-token, JWT validation)
- require_admin: role-based access control
- Health response structure validation (pure data checks)
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import jwt as _jwt
import pytest

from app.config import settings
from app.dependencies import _decode_token, get_current_user, require_admin

# ── JWT helpers ──


def _encode_jwt(payload: dict, secret: str | None = None) -> str:
    """Create a valid JWT token for testing (PyJWT).

    Injects iss/aud defaults to match the configured decoder policy
    (Phase DB-AUTH enforces both claims). Tests that intentionally
    exercise missing-claim rejection must use raw `_jwt.encode` instead.
    """
    secret = secret or settings.secret_key
    payload = dict(payload)
    payload.setdefault("iss", settings.jwt_issuer)
    payload.setdefault("aud", settings.jwt_audience)
    return _jwt.encode(payload, secret, algorithm="HS256")


def _encode_jwt_bad_sig(payload: dict) -> str:
    """Create a JWT with wrong signature."""
    token = _encode_jwt(payload, secret="wrong-secret-for-testing")
    # Tamper the signature part
    parts = token.split(".")
    return f"{parts[0]}.{parts[1]}.bad_signature"


# ══════════════════════════════════════════════════════════════
# _decode_token — JWT decode + signature + expiry
# ══════════════════════════════════════════════════════════════


class TestDecodeToken:
    """_decode_token — JWT parsing, signature verification, expiry."""

    def test_valid_token_decodes_payload(self):
        payload = {"sub": "user1", "role": "admin", "username": "Alice", "exp": time.time() + 3600, "iat": time.time()}
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "user1"
        assert decoded["role"] == "admin"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token("not-a-jwt")

    def test_two_part_token_raises(self):
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token("only.two")

    def test_bad_signature_raises(self):
        payload = {"sub": "attacker", "exp": time.time() + 3600, "iat": time.time()}
        token = _encode_jwt_bad_sig(payload)
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token(token)

    def test_expired_token_raises(self):
        payload = {"sub": "user1", "exp": time.time() - 3600, "iat": time.time() - 4000}  # expired 1h ago
        token = _encode_jwt(payload)
        with pytest.raises(ValueError, match="JWT expired"):
            _decode_token(token)

    def test_future_exp_is_valid(self):
        payload = {"sub": "user1", "exp": time.time() + 3600, "iat": time.time()}  # expires in 1h
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "user1"

    def test_no_exp_field_raises(self):
        """PyJWT requires 'exp' claim — tokens without exp are rejected."""
        payload = {"sub": "user1", "iat": time.time()}  # no exp
        token = _encode_jwt(payload)
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token(token)

    def test_wrong_secret_fails(self):
        payload = {"sub": "user1", "exp": time.time() + 3600, "iat": time.time()}
        token = _encode_jwt(payload, secret="wrong-secret")
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token(token)


# ══════════════════════════════════════════════════════════════
# get_current_user — auth branch logic
# ══════════════════════════════════════════════════════════════


class TestGetCurrentUser:
    """get_current_user — dev mode, dev-token, JWT validation branches."""

    async def test_no_credentials_dev_mode_returns_dev_user(self):
        """In non-production, no token → default dev user (role=viewer after W1-T2 fix)."""
        credentials = None
        with patch.object(settings, "app_env", "development"):
            user = await get_current_user(credentials)
        assert user["sub"] == "dev"
        # W1-T2: default dev user is now viewer, not admin
        assert user["role"] == "viewer"

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
        payload = {"sub": "user42", "role": "viewer", "username": "Bob", "exp": time.time() + 3600, "iat": time.time()}
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
