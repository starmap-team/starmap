"""Unit tests for the auth/admin DB-lifecycle service layer.

Direct tests of auth_service functions (no HTTP / TestClient indirection) —
the existing HTTP-layer test infrastructure (test_auth_service.py,
test_auth_guard.py) already covers the HTTP shape. These tests focus on the
business logic added by Phase DB-AUTH:

- authenticate() lockout counter + AccountLockedError
- authenticate() disabled-account + AccountDisabledError
- authenticate() unknown-user (no enumeration leak)
- authenticate() updates last_login_at/ip on success
- create_user / update_user / delete_user / reset_password / unlock_user
- forgot_password_request / reset_password_with_token
- /me scenario: get_user_by_username round-trip
- hash_password policy + verify_password strictness
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import auth_service
from app.services.auth_service import (
    MAX_FAILED_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    AccountDisabledError,
    AccountLockedError,
    InvalidCredentialsError,
    PasswordPolicyError,
    UsernameTakenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# ═══════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════


def _make_session(return_user=None) -> AsyncSession:
    """Build a minimal AsyncMock that mimics session.execute(...) → scalar_one_or_none()."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=return_user))
    )
    session.commit = AsyncMock(return_value=None)
    return session


def _make_user(**overrides):
    """Build a User fixture with safe defaults.

    Accepts an optional `password=` kwarg; converted to a bcrypt password_hash.
    """
    from app.models.user import User

    password = overrides.pop("password", "correct_horse")
    defaults = {
        "id": uuid.uuid4(),
        "username": "alice",
        "password_hash": hash_password(password),
        "role": "admin",
        "is_active": True,
        "disabled_at": None,
        "disabled_by": None,
        "disabled_reason": None,
        "locked_until": None,
        "failed_login_attempts": 0,
    }
    defaults.update(overrides)
    return User(**defaults)


# ═══════════════════════════════════════════════════════════════
# Password utilities & policy
# ═══════════════════════════════════════════════════════════════


class TestPasswordPolicy:
    def test_hash_minimum_length_required(self):
        with pytest.raises(PasswordPolicyError):
            hash_password("a" * (MIN_PASSWORD_LENGTH - 1))

    def test_hash_maximum_length_required(self):
        with pytest.raises(PasswordPolicyError):
            hash_password("a" * 200)

    def test_verify_bcrypt_hash_succeeds(self):
        h = hash_password("mypass1234")
        assert verify_password("mypass1234", h) is True
        assert verify_password("wrong", h) is False

    def test_verify_strict_bcrypt_no_plaintext_fallback(self):
        # Legacy plaintext fallback has been removed
        assert verify_password("plaintext_user", "plaintext_user") is False
        # Non-bcrypt strings fall through cleanly to False instead of crashing
        assert verify_password("anything", "not_a_bcrypt_hash") is False


# ═══════════════════════════════════════════════════════════════
# authenticate() — happy path
# ═══════════════════════════════════════════════════════════════


class TestAuthenticateSuccess:
    @pytest.mark.asyncio
    async def test_returns_user_and_writes_login_metadata(self):
        user = _make_user(username="alice", password="hunter2hunter")
        session = _make_session(return_user=user)

        result = await auth_service.authenticate(
            "alice", "hunter2hunter", session, client_ip="10.0.0.1"
        )

        assert result.username == "alice"
        assert user.last_login_at is not None
        assert user.last_login_ip == "10.0.0.1"
        assert user.failed_login_attempts == 0
        session.commit.assert_awaited()


# ═══════════════════════════════════════════════════════════════
# authenticate() — failure paths & lockout
# ═══════════════════════════════════════════════════════════════


class TestAuthenticateFailures:
    @pytest.mark.asyncio
    async def test_unknown_user_raises_invalid_credentials(self):
        session = _make_session(return_user=None)
        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("ghost", "any", session)

    @pytest.mark.asyncio
    async def test_bad_password_increments_failure_counter(self):
        user = _make_user(username="bob")
        # Override password_hash to one that won't match
        user.password_hash = hash_password("real_password")
        session = _make_session(return_user=user)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("bob", "wrong_password", session)

        assert user.failed_login_attempts == 1
        assert user.locked_until is None

    @pytest.mark.asyncio
    async def test_lockout_after_max_failures(self):
        # Pre-set counter to MAX-1 to trigger lockout on this attempt.
        user = _make_user(
            username="charlie",
            failed_login_attempts=MAX_FAILED_LOGIN_ATTEMPTS - 1,
        )
        user.password_hash = hash_password("real_password")
        session = _make_session(return_user=user)

        with pytest.raises(AccountLockedError) as exc_info:
            await auth_service.authenticate("charlie", "wrong_password", session)

        assert user.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS
        assert user.locked_until is not None
        assert exc_info.value.locked_until > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_locked_user_cannot_login_even_with_correct_password(self):
        future = datetime.now(UTC) + timedelta(minutes=10)
        user = _make_user(
            username="diana",
            password="the_right_one",
            locked_until=future,
        )
        session = _make_session(return_user=user)

        with pytest.raises(AccountLockedError):
            await auth_service.authenticate("diana", "the_right_one", session)

    @pytest.mark.asyncio
    async def test_disabled_account_raises_disabled(self):
        user = _make_user(
            username="evan",
            password="whatever",
            is_active=False,
            disabled_at=datetime.now(UTC),
            disabled_reason="test",
        )
        session = _make_session(return_user=user)

        with pytest.raises(AccountDisabledError):
            await auth_service.authenticate("evan", "whatever", session)


# ═══════════════════════════════════════════════════════════════
# change_password / forgot_password / reset_password
# ═══════════════════════════════════════════════════════════════


class TestPasswordManagement:
    @pytest.mark.asyncio
    async def test_change_password_with_correct_old(self):
        user = _make_user(username="fiona", password="oldpass1234")
        session = _make_session(return_user=user)

        ok = await auth_service.change_password(
            user, "oldpass1234", "newpass1234", session, actor="fiona"
        )
        assert ok is True
        assert user.password_changed_at is not None
        assert user.must_change_password is False
        assert verify_password("newpass1234", user.password_hash)

    @pytest.mark.asyncio
    async def test_change_password_with_wrong_old(self):
        user = _make_user(username="george", password="real_old")
        session = _make_session(return_user=user)
        ok = await auth_service.change_password(
            user, "wrong_old", "newpass1234", session
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_change_password_too_short_raises(self):
        user = _make_user(username="henry", password="real_password")
        session = _make_session(return_user=user)
        with pytest.raises(PasswordPolicyError):
            await auth_service.change_password(
                user, "real_password", "short", session
            )

    @pytest.mark.asyncio
    async def test_forgot_password_unknown_email_returns_none(self):
        session = _make_session(return_user=None)
        redis = MagicMock()
        redis.set = AsyncMock(return_value=True)
        token = await auth_service.forgot_password_request(
            "nobody@example.com", redis, session
        )
        assert token is None

    @pytest.mark.asyncio
    async def test_forgot_password_known_email_returns_token(self):
        user = _make_user(username="ivy")
        user.email = "ivy@example.com"
        session = _make_session(return_user=user)
        redis = MagicMock()
        redis.set = AsyncMock(return_value=True)
        token = await auth_service.forgot_password_request(
            "ivy@example.com", redis, session
        )
        assert token is not None
        assert len(token) >= 32

    @pytest.mark.asyncio
    async def test_reset_password_with_invalid_token_raises(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)  # not found
        session = _make_session(return_user=None)
        with pytest.raises(auth_service.InvalidTokenError):
            await auth_service.reset_password_with_token(
                "bogus-token", "newpass1234", redis, session
            )

    @pytest.mark.asyncio
    async def test_reset_password_with_valid_token_succeeds(self):
        user = _make_user(username="jack")
        raw_token = "valid_token_abc"
        redis = MagicMock()
        redis.get = AsyncMock(return_value=str(user.id).encode())
        redis.delete = AsyncMock(return_value=1)

        # reset_password_with_token re-queries the user by id
        def execute_side_effect(*args, **kwargs):
            m = MagicMock()
            m.scalar_one_or_none = MagicMock(return_value=user)
            return m

        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=execute_side_effect)
        session.commit = AsyncMock(return_value=None)

        result = await auth_service.reset_password_with_token(
            raw_token, "newpass1234", redis, session
        )
        assert result.username == "jack"
        assert verify_password("newpass1234", result.password_hash)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


# ═══════════════════════════════════════════════════════════════
# User CRUD (admin)
# ═══════════════════════════════════════════════════════════════


class TestUserCRUD:
    @pytest.mark.asyncio
    async def test_create_user_success(self):
        # No existing user with this name
        async def execute_side(*args, **kwargs):
            return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=execute_side)
        session.commit = AsyncMock(return_value=None)
        session.refresh = AsyncMock()

        user = await auth_service.create_user(
            username="new_user",
            password="newpass1234",
            role="user",
            session=session,
            actor="admin",
        )
        assert user.username == "new_user"
        assert user.role == "user"
        assert verify_password("newpass1234", user.password_hash)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_raises(self):
        existing = _make_user(username="taken")
        session = _make_session(return_user=existing)

        with pytest.raises(UsernameTakenError):
            await auth_service.create_user(
                username="taken", password="newpass1234", role="user", session=session
            )

    @pytest.mark.asyncio
    async def test_create_user_short_password_raises(self):
        session = _make_session(return_user=None)
        with pytest.raises(PasswordPolicyError):
            await auth_service.create_user(
                username="u1", password="x", role="user", session=session
            )

    @pytest.mark.asyncio
    async def test_create_user_invalid_role_raises(self):
        session = _make_session(return_user=None)
        with pytest.raises(PasswordPolicyError):
            await auth_service.create_user(
                username="u2", password="newpass1234", role="guest", session=session
            )

    @pytest.mark.asyncio
    async def test_unlock_user_clears_lockout(self):
        user = _make_user(
            username="locked",
            failed_login_attempts=5,
            locked_until=datetime.now(UTC) + timedelta(minutes=10),
        )
        session = _make_session(return_user=user)

        result = await auth_service.unlock_user(str(user.id), session, actor="admin")
        assert result is not None
        assert result.failed_login_attempts == 0
        assert result.locked_until is None

    @pytest.mark.asyncio
    async def test_reset_password_admin(self):
        user = _make_user(username="reset_me")
        session = _make_session(return_user=user)

        result = await auth_service.reset_password(
            str(user.id), "admin_set_123", session, actor="admin"
        )
        assert result is not None
        assert verify_password("admin_set_123", result.password_hash)
        assert result.must_change_password is False
        assert result.failed_login_attempts == 0


# ═══════════════════════════════════════════════════════════════
# JWT encode / decode
# ═══════════════════════════════════════════════════════════════


class TestJWT:
    def test_encode_decode_access(self):
        user = _make_user(username="juser")
        token = create_access_token(user)
        payload = decode_token(token)
        assert payload["sub"] == "juser"
        assert payload["type"] == "access"
        assert payload["role"] == "admin"

    def test_encode_decode_refresh(self):
        user = _make_user(username="juser2")
        token = create_refresh_token(user)
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_decode_garbage_raises(self):
        with pytest.raises(auth_service.InvalidTokenError):
            decode_token("not.a.valid.token")

    def test_access_token_has_uid_claim(self):
        # Required so /auth/me can correlate to DB row even after username rename
        user = _make_user(username="juser3")
        user.id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        token = create_access_token(user)
        payload = decode_token(token)
        assert payload["uid"] == "12345678-1234-5678-1234-567812345678"


# ═══════════════════════════════════════════════════════════════
# /me helper
# ═══════════════════════════════════════════════════════════════


class TestUserLookup:
    @pytest.mark.asyncio
    async def test_get_user_by_username(self):
        user = _make_user(username="lookupme")
        session = _make_session(return_user=user)
        result = await auth_service.get_user_by_username(session, "lookupme")
        assert result is user

    @pytest.mark.asyncio
    async def test_get_user_by_id_round_trip(self):
        user = _make_user(username="byid")
        session = _make_session(return_user=user)
        result = await auth_service.get_user_by_id(session, str(user.id))
        assert result is user

    @pytest.mark.asyncio
    async def test_get_user_by_invalid_id_returns_none(self):
        session = _make_session(return_user=None)
        assert await auth_service.get_user_by_id(session, "not-a-uuid") is None
