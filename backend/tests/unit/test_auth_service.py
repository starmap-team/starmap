"""Unit tests for auth/JWT business logic — service/core layer only.

Directly tests auth_service functions — no TestClient, no HTTP layer.
Covers:
- decode_token: JWT decode, signature verification, expiry check
- hash_password / verify_password: bcrypt hashing
- create_access_token: token issuance with proper claims
"""
from __future__ import annotations

import time

import jwt
import pytest

from app.config import settings
from app.models.user import User
from app.services.auth_service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

# ══════════════════════════════════════════════════════════════
# decode_token — JWT decode logic
# ══════════════════════════════════════════════════════════════


class TestDecodeToken:
    """decode_token — JWT structure, signature, and expiry validation."""

    def test_valid_token_decodes(self):
        user = User(username="user1", password_hash=hash_password("testX123"), role="admin")
        token = create_access_token(user)
        result = decode_token(token)
        assert result["sub"] == "user1"
        assert result["role"] == "admin"

    def test_tampered_signature_raises(self):
        payload = {"sub": "user1", "role": "admin", "exp": time.time() + 3600}
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_token(tampered)

    def test_wrong_secret_raises(self):
        payload = {"sub": "user1", "role": "admin", "exp": time.time() + 3600}
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_token(token)

    def test_expired_token_raises(self):
        payload = {"sub": "user1", "aud": settings.jwt_audience, "iss": settings.jwt_issuer, "exp": time.time() - 3600, "iat": time.time() - 4000}
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        with pytest.raises(ValueError, match="expired|Invalid"):
            decode_token(token)


# ══════════════════════════════════════════════════════════════
# hash_password / verify_password — bcrypt hashing
# ══════════════════════════════════════════════════════════════


class TestPasswordHashing:
    """hash_password / verify_password — bcrypt-only, no plaintext fallback."""

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_is_bcrypt_format(self):
        hashed = hash_password("testX123")
        assert hashed.startswith(("$2b$", "$2a$"))

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2  # Different salts

    def test_cost_factor_12(self):
        hashed = hash_password("testX123")
        assert "$12$" in hashed


# ══════════════════════════════════════════════════════════════
# create_access_token — token issuance
# ══════════════════════════════════════════════════════════════


class TestCreateAccessToken:
    """create_access_token — proper claims and format."""

    def test_token_contains_required_claims(self):
        user = User(username="testuser", password_hash=hash_password("testX123"), role="admin")
        token = create_access_token(user)
        decoded = decode_token(token)
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert decoded["type"] == "access"
        assert "jti" in decoded
        assert "iss" in decoded
        assert "aud" in decoded
        assert "exp" in decoded
        assert "iat" in decoded

    def test_token_expiry_is_15_minutes(self):
        user = User(username="testuser", password_hash=hash_password("testX123"), role="user")
        token = create_access_token(user)
        decoded = decode_token(token)
        # exp - iat should be ~900 seconds (15 min)
        assert abs((decoded["exp"] - decoded["iat"]) - 900) < 5

    def test_token_contains_kid_header(self):
        """Phase 20 D-02: JOSE header carries `kid` for rotation keyring lookup."""
        import jwt as _jwt

        user = User(username="kiduser", password_hash=hash_password("testX123"), role="user")
        token = create_access_token(user)
        header = _jwt.get_unverified_header(token)
        assert header["kid"] == settings.jwt_kid
        assert header["alg"] == "HS256"


# ══════════════════════════════════════════════════════════════
# Phase 20 D-02: JWT rotation — kid keyring
# ══════════════════════════════════════════════════════════════


class TestJWTKeyring:
    """JWT kid + keyring rotation — Phase 20 D-02.

    Backward-compatible fallback: when jwt_secret_keyring is empty,
    `{jwt_kid: secret_key}` is used. When set explicitly, multiple kids
    may coexist (rotation transition).
    """

    def test_default_keyring_uses_active_kid(self, monkeypatch):
        """Empty keyring → {jwt_kid: secret_key}; tokens verify normally."""
        monkeypatch.setattr(settings, "jwt_secret_keyring", {})
        user = User(username="k1", password_hash=hash_password("testX123"), role="user")
        token = create_access_token(user)
        # decode_token should pick up the kid from the JOSE header and use secret_key
        decoded = decode_token(token)
        assert decoded["sub"] == "k1"

    def test_decode_with_unknown_kid_rejected(self, monkeypatch):
        """Token signed by a kid not in keyring + secret mismatch → InvalidTokenError.

        public-deploy-preflight 2026-08-20 (P0): The verifier falls back to
        ``settings.secret_key`` when ``kid`` is missing from the keyring
        (backward-compat with legacy tokens that pre-date the keyring).
        A rogue token signed by a different secret is therefore rejected
        on signature mismatch, not on kid lookup.
        """
        from app.services.auth_service import InvalidTokenError

        unknown_secret = "x" * 64
        unknown_token = jwt.encode(
            {"sub": "rogue", "role": "admin", "exp": time.time() + 60, "iat": time.time()},
            unknown_secret,
            algorithm="HS256",
            headers={"kid": "v999-does-not-exist"},
        )
        monkeypatch.setattr(settings, "jwt_secret_keyring", {})
        with pytest.raises(InvalidTokenError, match="Invalid JWT"):
            decode_token(unknown_token)

    def test_keyring_supports_multiple_kids(self, monkeypatch):
        """Multi-kid keyring accepts tokens signed by any of them (rotation transition)."""
        legacy_secret = "a" * 64
        new_secret = "b" * 64
        monkeypatch.setattr(
            settings,
            "jwt_secret_keyring",
            {"v1": legacy_secret, "v2": new_secret},
        )
        # Sign with v1 (legacy) — must carry iss/aud to match decode_token's verify
        legacy_token = jwt.encode(
            {
                "sub": "legacy",
                "role": "user",
                "iat": time.time(),
                "exp": time.time() + 60,
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
            },
            legacy_secret,
            algorithm="HS256",
            headers={"kid": "v1"},
        )
        new_token = jwt.encode(
            {
                "sub": "new",
                "role": "user",
                "iat": time.time(),
                "exp": time.time() + 60,
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
            },
            new_secret,
            algorithm="HS256",
            headers={"kid": "v2"},
        )
        assert decode_token(legacy_token)["sub"] == "legacy"
        assert decode_token(new_token)["sub"] == "new"


# ══════════════════════════════════════════════════════════════
# require_admin — role-based access (still in dependencies)
# ══════════════════════════════════════════════════════════════


class TestRequireAdmin:
    """require_admin — admin role check."""

    async def test_admin_user_passes(self):
        from app.dependencies import require_admin
        user = {"sub": "admin1", "role": "admin"}
        result = await require_admin(user)
        assert result["role"] == "admin"

    async def test_non_admin_raises_403(self):
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.dependencies import require_admin
        user = {"sub": "viewer1", "role": "viewer"}
        with (
            patch("app.dependencies.audit_log"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await require_admin(user)
        assert exc_info.value.status_code == 403

    async def test_no_role_field_raises_403(self):
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.dependencies import require_admin
        user = {"sub": "norole"}
        with (
            patch("app.dependencies.audit_log"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await require_admin(user)
        assert exc_info.value.status_code == 403
