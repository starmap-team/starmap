"""Tests for SEC-01 (PyJWT), SEC-02 (bcrypt), SEC-03 (JWT claims)."""
from __future__ import annotations

import time
import uuid

import bcrypt
import jwt
import pytest

from app.api.v1.auth import _encode_jwt, _verify_password
from app.config import settings
from app.dependencies import _decode_token


# ── SEC-01: PyJWT encode/decode ──


class TestPyJWTEncodeDecode:
    """SEC-01: Replace hand-written HMAC+base64 with PyJWT."""

    def test_encode_decode_roundtrip(self) -> None:
        """Encode a payload, decode it, verify all fields match."""
        payload = {
            "sub": "testuser",
            "role": "admin",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"

    def test_old_token_compatibility(self) -> None:
        """Manually construct a hand-rolled-style token (no padding) and verify PyJWT decodes it."""
        import base64
        import hashlib
        import hmac
        import json

        payload = {
            "sub": "legacy_user",
            "role": "user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode()
        signing_input = f"{header}.{payload_b64}".encode()
        sig = hmac.new(
            settings.secret_key.encode(), signing_input, hashlib.sha256
        ).digest()
        signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        old_token = f"{header}.{payload_b64}.{signature}"

        decoded = _decode_token(old_token)
        assert decoded["sub"] == "legacy_user"

    def test_expired_token_raises_valueerror(self) -> None:
        """Encode with past exp, verify ValueError('JWT expired') is raised."""
        payload = {
            "sub": "expired_user",
            "exp": int(time.time()) - 100,  # expired 100s ago
            "iat": int(time.time()) - 200,
        }
        token = _encode_jwt(payload)
        with pytest.raises(ValueError, match="JWT expired"):
            _decode_token(token)

    def test_invalid_signature_raises_valueerror(self) -> None:
        """Tamper with a token, verify ValueError is raised."""
        payload = {
            "sub": "tampered",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = _encode_jwt(payload)
        # Tamper: change one character in the middle
        parts = token.split(".")
        tampered_payload = parts[1][:-2] + "XX"
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        with pytest.raises(ValueError, match="Invalid JWT"):
            _decode_token(tampered_token)


# ── SEC-02: bcrypt password verification ──


class TestBcryptPasswordVerification:
    """SEC-02: Replace plaintext password comparison with bcrypt.checkpw()."""

    def test_bcrypt_verification(self) -> None:
        """Test _verify_password with a known bcrypt hash."""
        plain = "mysecretpassword"
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=4)).decode()
        assert _verify_password(plain, hashed) is True

    def test_plaintext_fallback(self) -> None:
        """Test _verify_password with a plaintext stored password."""
        assert _verify_password("starmap2024", "starmap2024") is True
        assert _verify_password("wrongpassword", "starmap2024") is False

    def test_wrong_password_bcrypt(self) -> None:
        """Test _verify_password returns False for wrong password against bcrypt hash."""
        plain = "correctpassword"
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=4)).decode()
        assert _verify_password("wrongpassword", hashed) is False

    def test_bcrypt_2a_prefix(self) -> None:
        """Test _verify_password with $2a$ prefix (alternative bcrypt version)."""
        plain = "testpassword"
        # Generate $2b$ hash and manually replace prefix to $2a$
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=4)).decode()
        hashed_2a = "$2a$" + hashed[4:]
        assert _verify_password(plain, hashed_2a) is True


# ── SEC-03: JWT claims (aud/iss/nbf/jti) ──


class TestJWTClaims:
    """SEC-03: Add aud/iss/nbf/jti claims to token issuance."""

    def test_new_claims_present(self) -> None:
        """Encode a token with new claims, decode it, verify aud/iss/nbf/jti are present."""
        now = time.time()
        payload = {
            "sub": "claimuser",
            "role": "admin",
            "username": "claimuser",
            "exp": now + settings.token_expire_hours * 3600,
            "iat": now,
            "nbf": now,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "jti": str(uuid.uuid4()),
        }
        token = _encode_jwt(payload)
        decoded = _decode_token(token)
        assert decoded["aud"] == "starmap-api"
        assert decoded["iss"] == "starmap"
        assert "nbf" in decoded
        assert "jti" in decoded

    def test_leeway_allows_slight_clock_skew(self) -> None:
        """Encode a token with exp slightly in the past (within leeway), verify it still decodes."""
        now = time.time()
        # exp is 10 seconds in the past, but leeway is 30 seconds
        payload = {
            "sub": "leeway_user",
            "exp": now - 10,
            "iat": now - 100,
        }
        token = _encode_jwt(payload)
        # Should NOT raise because 10s < 30s leeway
        decoded = _decode_token(token)
        assert decoded["sub"] == "leeway_user"

    def test_phase_a_backward_compat(self) -> None:
        """Decode a token without aud/iss/nbf claims, verify it succeeds (Phase A)."""
        now = time.time()
        payload = {
            "sub": "oldformat_user",
            "exp": now + 3600,
            "iat": now,
        }
        token = _encode_jwt(payload)
        # Phase A: only requires exp, iat, sub — no aud/iss/nbf
        decoded = _decode_token(token)
        assert decoded["sub"] == "oldformat_user"
        assert "aud" not in decoded
        assert "iss" not in decoded
