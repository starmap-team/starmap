"""Authentication service layer — all auth business logic lives here.

Routes in auth.py and admin_users.py are thin HTTP wrappers that delegate
to this module. This keeps auth logic testable without HTTP concerns.

Public surface:
- Password: hash_password / verify_password
- Tokens: create_access_token / create_refresh_token / decode_token /
          create_tokens / refresh_access_token / revoke_refresh_token
- Authentication: authenticate / change_password / forgot_password_request
                  / reset_password_with_token
- User CRUD (admin): list_users / create_user / update_user / delete_user
                     / reset_password / unlock_user
- Helpers: get_user_by_username / get_user_by_id / update_login_tracking
"""
from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from datetime import timedelta as _td  # JWT leeway helper (public keyring API uses _td alias)
from typing import Any

import bcrypt
import jwt
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import ALLOWED_ROLES, User
from app.utils.audit import AuditEntry, AuditEvent, audit_log

# ═══════════════════════════════════════════════════════════════


# INJ-03 fix: 转义 SQL LIKE 通配符，防止通配符注入
def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards (% and _) in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
# Configuration
# ═══════════════════════════════════════════════════════════════

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Lockout policy
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Forgot-password token TTL
FORGOT_PASSWORD_TOKEN_TTL_MINUTES = 30


# ═══════════════════════════════════════════════════════════════
# Custom exceptions — caught by the FastAPI layer
# ═══════════════════════════════════════════════════════════════


class AuthError(Exception):
    """Base class for authentication-service errors."""

    http_status = 400


class InvalidCredentialsError(AuthError):
    """Username or password is wrong."""

    http_status = 401


class AccountLockedError(AuthError):
    """Account is temporarily locked after too many failed attempts."""

    http_status = 423  # Locked (WebDAV) — well-understood status code

    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        super().__init__(
            f"Account locked until {locked_until.isoformat()} (UTC)"
        )


class AccountDisabledError(AuthError):
    """Account has been soft-disabled by an admin."""

    http_status = 403


class PasswordPolicyError(AuthError):
    """Password does not meet policy requirements."""

    http_status = 422


class UserNotFoundError(AuthError):
    """User does not exist."""

    http_status = 404


# public-deploy-preflight 2026-08-20 (P0): JWT keyring 真消费。
# 此前 config.py 声明 jwt_kid / jwt_secret_keyring 但代码未读取，
# 改 SECRET_KEY 即全员强制下线。改为：
# - 签发：写入 JOSE `kid` header
# - 验签：先解 header 取 kid → 从 keyring 找对应 secret；找不到则用 settings.secret_key 兜底
# 这样轮换密钥时把旧 kid 加进 jwt_secret_keyring 字典即可无缝切换。
def _resolve_signing_key(kid: str) -> str:
    """Return the signing secret for ``kid`` from the configured keyring.

    Empty keyring falls back to ``{settings.jwt_kid: settings.secret_key}``
    for backward compatibility with tokens signed before keyring was added.
    """
    if settings.jwt_secret_keyring:
        return settings.jwt_secret_keyring.get(kid, settings.secret_key)
    return settings.secret_key


def _resolve_verification_key(token: str) -> tuple[str, str]:
    """Return ``(kid, secret)`` for verification, reading the JOSE header.

    Unknown kid falls back to ``settings.secret_key`` (legacy / dev tokens).
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return settings.jwt_kid, settings.secret_key
    kid = unverified_header.get("kid") or settings.jwt_kid
    return kid, _resolve_signing_key(kid)


def _jwt_sign(payload: dict[str, Any], kid: str | None = None) -> str:
    """Sign ``payload`` with HS256 + write the active ``kid`` header.

    Falls back to ``settings.jwt_kid`` if ``kid`` is omitted.
    """
    headers = {"kid": kid or settings.jwt_kid}
    secret = _resolve_signing_key(headers["kid"])
    return jwt.encode(payload, secret, algorithm="HS256", headers=headers)


def _jwt_verify(token: str, *, audience: str | None, issuer: str | None, leeway: int = 0,
                options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify ``token`` using the key chosen by its JOSE ``kid`` header.

    ``audience`` / ``issuer`` / ``leeway`` / ``options`` are passed straight
    to PyJWT — this helper only differs from raw ``jwt.decode`` in that it
    selects the verification key from ``settings.jwt_secret_keyring``.
    """
    kid, secret = _resolve_verification_key(token)
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=audience,
        issuer=issuer,
        leeway=_td(seconds=leeway) if leeway is not None else None,
        options=options,  # type: ignore[arg-type]  # PyJWT 运行时接受 dict；mypy stub 仅认 Options TypedDict
    )


class UsernameTakenError(AuthError):
    """Username already in use."""

    http_status = 409


class InvalidTokenError(AuthError, ValueError):
    """Token is invalid, expired, or revoked.

    Inherits from ValueError so existing `pytest.raises(ValueError)`
    assertions in legacy tests keep working. This is intentional —
    token-decoding failures are semantically a ValueError, not a
    domain exception that needs HTTP-mapping at the auth-service
    boundary (the HTTP layer maps to 401 explicitly).
    """

    http_status = 401


# ═══════════════════════════════════════════════════════════════
# Password utilities
# ═══════════════════════════════════════════════════════════════


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (cost factor 12)."""
    if len(plain) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(plain) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password too long (max {MAX_PASSWORD_LENGTH} characters)"
        )
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash.

    The legacy plaintext fallback has been removed — only bcrypt is accepted.
    """
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def _validate_password_policy(password: str, username: str = "") -> None:
    """Enforce password policy. Raises PasswordPolicyError if violated."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"密码至少需要 {MIN_PASSWORD_LENGTH} 个字符"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"密码不能超过 {MAX_PASSWORD_LENGTH} 个字符"
        )
    # ── ponytail: reject trivial patterns ──
    if password.isdigit():
        raise PasswordPolicyError("密码不能是纯数字")
    if password.isalpha():
        raise PasswordPolicyError("密码不能是纯字母")
    # ── reject password == username ──
    if username and password.lower() == username.lower():
        raise PasswordPolicyError("密码不能与用户名相同")
    # ── common password blocklist (ponytail: inline set, no file dep) ──
    _blocklist = frozenset({
        "password", "password1", "admin123", "admin1234",
        "12345678", "123456789", "qwerty123", "abc12345", "11111111",
        "changeme", "welcome1", "iloveyou", "sunshine", "monkey123",
    })
    if password.lower() in _blocklist:
        raise PasswordPolicyError("该密码过于常见，请使用更安全的密码")


# ═══════════════════════════════════════════════════════════════
# JWT utilities
# ═══════════════════════════════════════════════════════════════


def _build_jwt_payload(
    user: User,
    exp_seconds: int,
    token_type: str = "access",
) -> dict[str, Any]:
    """Build a JWT payload dict for the given user."""
    now = time.time()
    return {
        "sub": user.username,
        "role": user.role,
        "username": user.username,
        "uid": str(user.id),  # user id — distinct from username
        "type": token_type,
        "exp": now + exp_seconds,
        "iat": now,
        "nbf": now,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid.uuid4()),
    }


def create_access_token(user: User) -> str:
    """Sign an access token (short-lived, 15 min)."""
    payload = _build_jwt_payload(
        user,
        exp_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        token_type="access",
    )
    return _jwt_sign(payload)


def create_refresh_token(user: User) -> str:
    """Sign a refresh token (long-lived, 7 days)."""
    payload = _build_jwt_payload(
        user,
        exp_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        token_type="refresh",
    )
    return _jwt_sign(payload)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises InvalidTokenError on invalid/expired/wrong-audience/wrong-issuer.
    Enforces aud/iss claims (SEC-03).
    """
    from datetime import timedelta as _td  # noqa: F401  kept for backward import compat

    if token.count(".") != 2:
        raise InvalidTokenError("Invalid JWT format")

    try:
        payload = _jwt_verify(
            token,
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=int(settings.jwt_leeway_seconds),
            options={
                "require": ["iat", "sub", "exp"],
                "verify_aud": bool(settings.jwt_audience),
            },
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidTokenError("JWT expired") from e
    except jwt.InvalidSignatureError as e:
        raise InvalidTokenError("Invalid JWT signature") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid JWT: {e}") from e
    return payload


# ═══════════════════════════════════════════════════════════════
# Authentication (with lockout, audit, tracking)
# ═══════════════════════════════════════════════════════════════


async def authenticate(
    username: str,
    password: str,
    session: AsyncSession,
    client_ip: str | None = None,
) -> User:
    """Authenticate a user by username + password.

    Behaviour:
    - Increments failed_login_attempts on each failure; locks the account
      for LOCKOUT_DURATION_MINUTES after MAX_FAILED_LOGIN_ATTEMPTS bad tries
      (AccountLockedError)
    - Resets the counter and updates last_login_at / last_login_ip on success
    - Writes audit events for AUTH_FAILURE / LOGIN_LOCKED / LOGIN_SUCCESS
    - Raises AccountDisabledError if the user is soft-deleted
    - Raises UserNotFoundError / InvalidCredentialsError otherwise

    Returns the authenticated User (caller may inspect must_change_password).
    """
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        # Avoid leaking whether the username exists
        audit_log(AuditEntry(
            event=AuditEvent.AUTH_FAILURE,
            actor=username,
            action="login",
            detail=f"Unknown user (ip={client_ip or ''})",
            ip=client_ip or "",
        ))
        raise InvalidCredentialsError("Invalid username or password")

    if user.is_disabled:
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=username,
            action="login",
            detail=f"Account disabled (reason={user.disabled_reason or 'unspecified'})",
            ip=client_ip or "",
        ))
        raise AccountDisabledError(
            f"Account has been disabled: {user.disabled_reason or 'contact admin'}"
        )

    if user.is_locked:
        # mypy: is_locked property guarantees locked_until is set + future
        locked_until = user.locked_until
        assert locked_until is not None  # for type narrowing; guaranteed by is_locked
        audit_log(AuditEntry(
            event=AuditEvent.LOGIN_LOCKED,
            actor=username,
            action="login",
            detail=f"Locked until {locked_until.isoformat()} (ip={client_ip or ''})",
            ip=client_ip or "",
        ))
        raise AccountLockedError(locked_until=locked_until)

    if not user.is_active:
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=username,
            action="login",
            detail="Account inactive",
            ip=client_ip or "",
        ))
        raise AccountDisabledError("Account is inactive")

    # ── Password check ──
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            await session.commit()
            audit_log(AuditEntry(
                event=AuditEvent.LOGIN_LOCKED,
                actor=username,
                action="login",
                detail=(
                    f"Account locked after {user.failed_login_attempts} failed attempts "
                    f"(ip={client_ip or ''})"
                ),
                ip=client_ip or "",
            ))
            raise AccountLockedError(locked_until=user.locked_until)

        await session.commit()
        audit_log(AuditEntry(
            event=AuditEvent.AUTH_FAILURE,
            actor=username,
            action="login",
            detail=(
                f"Bad password (attempt {user.failed_login_attempts}/"
                f"{MAX_FAILED_LOGIN_ATTEMPTS}, ip={client_ip or ''})"
            ),
            ip=client_ip or "",
        ))
        raise InvalidCredentialsError("Invalid username or password")

    # ── Success ──
    await _record_successful_login(user, session, client_ip)
    audit_log(AuditEntry(
        event=AuditEvent.LOGIN_SUCCESS,
        actor=username,
        action="login",
        detail=f"User logged in (ip={client_ip or ''})",
        ip=client_ip or "",
    ))
    return user


async def _record_successful_login(
    user: User,
    session: AsyncSession,
    client_ip: str | None,
) -> None:
    """Reset failure counters and write audit metadata on successful login."""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    if client_ip:
        user.last_login_ip = client_ip[:45]  # IPv6 max length
    await session.commit()


# ═══════════════════════════════════════════════════════════════
# Token issuance (access + refresh with Redis revocation)
# ═══════════════════════════════════════════════════════════════


async def create_tokens(user: User, redis: Redis) -> dict[str, Any]:
    """Create access + refresh token pair. Store refresh jti in Redis.

    Returns: {access_token, refresh_token, expires_in, user: {username, role}}
    """
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Decode refresh to get jti for Redis storage
    refresh_payload = _jwt_verify(
        refresh_token,
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"verify_exp": False},
    )
    jti = refresh_payload["jti"]

    # Store refresh:{jti} = user_id in Redis with TTL matching token expiry
    await redis.set(
        f"refresh:{jti}",
        str(user.id),
        ex=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "role": user.role,
            "must_change_password": user.must_change_password,
        },
    }


async def refresh_access_token(
    refresh_token: str,
    redis: Redis,
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Use a refresh token to get a new access token.

    Validates: refresh not expired + jti exists in Redis + user still active.
    Does NOT rotate the refresh token (simpler; jti revocation list is the
    primary revocation mechanism).
    """
    try:
        payload = decode_token(refresh_token)
    except InvalidTokenError:
        audit_log(AuditEntry(
            event=AuditEvent.TOKEN_INVALID,
            actor="unknown",
            action="refresh_token",
            detail="Refresh token decode failed",
            ip="",
        ))
        return None

    if payload.get("type") != "refresh":
        audit_log(AuditEntry(
            event=AuditEvent.TOKEN_INVALID,
            actor=payload.get("sub", "unknown"),
            action="refresh_token",
            detail="Token is not a refresh token",
            ip="",
        ))
        return None

    jti = payload.get("jti")
    if not jti:
        audit_log(AuditEntry(
            event=AuditEvent.TOKEN_INVALID,
            actor=payload.get("sub", "unknown"),
            action="refresh_token",
            detail="Refresh token missing jti",
            ip="",
        ))
        return None

    # Check Redis for revocation
    stored_user_id = await redis.get(f"refresh:{jti}")
    if stored_user_id is None:
        audit_log(AuditEntry(
            event=AuditEvent.TOKEN_INVALID,
            actor=payload.get("sub", "unknown"),
            action="refresh_token",
            detail="Refresh token revoked or expired",
            ip="",
        ))
        return None

    # Look up user to ensure still active
    username = payload.get("sub")
    if not username:
        return None
    user = await get_user_by_username(session, username)
    if user is None:
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=username,
            action="refresh_token",
            detail="User not found during token refresh",
            ip="",
        ))
        return None
    if user.is_login_blocked:
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=username,
            action="refresh_token",
            detail="User is blocked during token refresh",
            ip="",
        ))
        return None

    # Issue new access token
    new_access = create_access_token(user)
    audit_log(AuditEntry(
        event=AuditEvent.SENSITIVE_READ,
        actor=username,
        action="refresh_token",
        detail="Access token refreshed",
        ip="",
    ))
    return {
        "access_token": new_access,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def revoke_refresh_token(refresh_token: str, redis: Redis) -> bool:
    """Revoke a refresh token by deleting its jti from Redis.

    Returns True if the jti was found and deleted, False otherwise.
    """
    actor = "unknown"
    try:
        payload = _jwt_verify(
            refresh_token,
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"verify_exp": False},
        )
        actor = payload.get("sub", "unknown")
    except jwt.InvalidTokenError:
        audit_log(AuditEntry(
            event=AuditEvent.TOKEN_INVALID,
            actor=actor,
            action="revoke_refresh_token",
            detail="Invalid token for revocation",
            ip="",
        ))
        return False

    jti = payload.get("jti")
    if not jti:
        return False

    deleted = await redis.delete(f"refresh:{jti}")
    if deleted > 0:
        audit_log(AuditEntry(
            event=AuditEvent.SENSITIVE_WRITE,
            actor=actor,
            action="revoke_refresh_token",
            detail="Refresh token revoked",
            ip="",
        ))
    return deleted > 0


# ═══════════════════════════════════════════════════════════════
# Password management
# ═══════════════════════════════════════════════════════════════


async def change_password(
    user: User,
    old_password: str,
    new_password: str,
    session: AsyncSession,
    actor: str | None = None,
) -> bool:
    """Change a user's password (self-service).

    Returns True on success, False if old password wrong.
    Raises PasswordPolicyError if new password fails policy.
    """
    if not verify_password(old_password, user.password_hash):
        return False
    if verify_password(new_password, user.password_hash):
        raise PasswordPolicyError("新密码不能与原密码相同")
    _validate_password_policy(new_password, username=user.username)

    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    user.must_change_password = False
    await session.commit()

    audit_log(AuditEntry(
        event=AuditEvent.PASSWORD_CHANGED,
        actor=actor or user.username,
        action="change_password",
        detail=f"User '{user.username}' changed own password",
        ip="",
    ))
    return True


async def forgot_password_request(
    email: str,
    redis: Redis,
    session: AsyncSession,
    base_url: str = "",
) -> str | None:
    """Initiate a password reset.

    Generates a one-time token stored in Redis. Returns the token so the
    caller (e.g. an API endpoint) can email it (email integration is left
    to the caller — see plan §I).

    Always returns None if the email is not registered (avoids leaking
    which addresses have accounts) but the audit event is still written.
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        audit_log(AuditEntry(
            event=AuditEvent.PASSWORD_RESET,
            actor=email,
            action="forgot_password",
            detail="Email not registered (response suppressed)",
            ip="",
        ))
        return None

    token = secrets.token_urlsafe(32)
    await redis.set(
        f"forgot_password:{token}",
        str(user.id),
        ex=FORGOT_PASSWORD_TOKEN_TTL_MINUTES * 60,
    )

    audit_log(AuditEntry(
        event=AuditEvent.PASSWORD_RESET,
        actor=user.username,
        action="forgot_password",
        detail=f"Reset token issued (ttl={FORGOT_PASSWORD_TOKEN_TTL_MINUTES}min)",
        ip="",
    ))
    return token


async def reset_password_with_token(
    token: str,
    new_password: str,
    redis: Redis,
    session: AsyncSession,
) -> User:
    """Reset password using a forgot-password token.

    Raises InvalidTokenError / PasswordPolicyError / UserNotFoundError.
    """
    raw = await redis.get(f"forgot_password:{token}")
    if raw is None:
        raise InvalidTokenError("Reset token is invalid or expired")

    # redis-py may return bytes or str depending on decode_responses setting
    user_id_str = raw.decode() if isinstance(raw, bytes) else raw
    user = await get_user_by_id(session, user_id_str)
    if user is None:
        raise UserNotFoundError("User no longer exists")

    _validate_password_policy(new_password, username=user.username)

    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    await session.commit()

    # Token is single-use
    await redis.delete(f"forgot_password:{token}")

    audit_log(AuditEntry(
        event=AuditEvent.PASSWORD_RESET,
        actor=user.username,
        action="reset_password",
        detail="Password reset via token",
        ip="",
    ))
    return user


# ═══════════════════════════════════════════════════════════════
# Helpers (read-only queries)
# ═══════════════════════════════════════════════════════════════


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    result = await session.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════
# User CRUD (admin only)
# ═══════════════════════════════════════════════════════════════


async def list_users(
    session: AsyncSession,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[User], int]:
    """Paginated user listing with optional filters.

    Returns (rows, total_count).
    """
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if search:
        like = f"%{_escape_like(search)}%"
        stmt = stmt.where(User.username.ilike(like, escape="\\"))
        count_stmt = count_stmt.where(User.username.ilike(like, escape="\\"))
    if role is not None:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(User.created_at).offset((page - 1) * page_size).limit(page_size)
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def create_user(
    username: str,
    password: str,
    role: str,
    session: AsyncSession,
    email: str | None = None,
    actor: str | None = None,
) -> User:
    """Create a new user. Raises PasswordPolicyError / UsernameTakenError."""
    _validate_password_policy(password)
    if role not in ALLOWED_ROLES:
        raise PasswordPolicyError(f"Role must be one of: {sorted(ALLOWED_ROLES)}")

    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise UsernameTakenError(f"Username '{username}' already exists")

    if email:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none() is not None:
            raise UsernameTakenError(f"Email '{email}' already in use")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
        password_changed_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    audit_log(AuditEntry(
        event=AuditEvent.USER_CREATED,
        actor=actor or "system",
        action="create_user",
        detail=f"Created user '{username}' (role={role})",
        ip="",
    ))
    return user


async def update_user(
    user_id: str,
    session: AsyncSession,
    role: str | None = None,
    is_active: bool | None = None,
    must_change_password: bool | None = None,
    email: str | None = None,
    actor: str | None = None,
) -> User | None:
    """Update user role and/or active status. Returns updated User or None."""
    user = await get_user_by_id(session, user_id)
    if user is None:
        return None

    changes: list[str] = []
    if role is not None:
        if role not in ALLOWED_ROLES:
            raise PasswordPolicyError(f"Role must be one of: {sorted(ALLOWED_ROLES)}")
        if role != user.role:
            changes.append(f"role {user.role} -> {role}")
            user.role = role
    if is_active is not None and is_active != user.is_active:
        changes.append(f"is_active {user.is_active} -> {is_active}")
        user.is_active = is_active
        if not is_active:
            user.disabled_at = datetime.now(UTC)
        else:
            user.disabled_at = None
            user.disabled_by = None
            user.disabled_reason = None
    if must_change_password is not None and must_change_password != user.must_change_password:
        changes.append(
            f"must_change_password {user.must_change_password} -> {must_change_password}"
        )
        user.must_change_password = must_change_password
    if email is not None and email != user.email:
        changes.append("email updated")
        user.email = email or None

    if changes:
        await session.commit()
        await session.refresh(user)
        audit_log(AuditEntry(
            event=AuditEvent.USER_UPDATED,
            actor=actor or "system",
            action="update_user",
            detail=f"User '{user.username}': {'; '.join(changes)}",
            ip="",
        ))
    return user


async def delete_user(
    user_id: str,
    session: AsyncSession,
    actor: str | None = None,
    reason: str | None = None,
) -> bool:
    """Soft-delete a user by setting disabled_at. Returns True if changed."""
    user = await get_user_by_id(session, user_id)
    if user is None:
        return False

    if user.is_disabled:
        return False  # already deleted

    user.is_active = False
    user.disabled_at = datetime.now(UTC)
    user.disabled_reason = reason
    # disabled_by set by caller via update_user(actor); leave null if unknown
    await session.commit()

    audit_log(AuditEntry(
        event=AuditEvent.USER_DISABLED,
        actor=actor or "system",
        action="delete_user",
        detail=f"Disabled user '{user.username}' (reason={reason or 'unspecified'})",
        ip="",
    ))

    # DATA-05 fix: 软删除时同时匿名化 PII（邮箱、登录 IP）
    # 用户名保留用于审计追踪，但标记为已匿名化
    if user.email:
        user.email = None
    if user.last_login_ip:
        user.last_login_ip = None
    await session.commit()

    return True


async def unlock_user(
    user_id: str,
    session: AsyncSession,
    actor: str | None = None,
) -> User | None:
    """Clear a user's lockout window and failed-attempt counter."""
    user = await get_user_by_id(session, user_id)
    if user is None:
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    await session.commit()
    await session.refresh(user)

    audit_log(AuditEntry(
        event=AuditEvent.USER_UNLOCKED,
        actor=actor or "system",
        action="unlock_user",
        detail=f"Unlocked user '{user.username}'",
        ip="",
    ))
    return user


async def reset_password(
    user_id: str,
    new_password: str,
    session: AsyncSession,
    actor: str | None = None,
) -> User | None:
    """Admin-initiated password reset. Returns updated User or None."""
    user = await get_user_by_id(session, user_id)
    if user is None:
        return None

    _validate_password_policy(new_password, username=user.username)

    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    await session.commit()
    await session.refresh(user)

    audit_log(AuditEntry(
        event=AuditEvent.PASSWORD_RESET,
        actor=actor or "system",
        action="reset_password",
        detail=f"Admin reset password for '{user.username}'",
        ip="",
    ))
    return user
