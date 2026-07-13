"""Authentication service layer — all auth business logic lives here.

Routes in auth.py and admin.py are thin HTTP wrappers that delegate to this module.
This keeps auth logic testable without HTTP concerns.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import bcrypt
import jwt
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

# ── Token configuration ──

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
MIN_PASSWORD_LENGTH = 8


# ── Password utilities ──


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (cost factor 12)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT utilities ──


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
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(user: User) -> str:
    """Sign a refresh token (long-lived, 7 days) and store its jti in Redis."""
    payload = _build_jwt_payload(
        user,
        exp_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        token_type="refresh",
    )
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises ValueError on invalid/expired."""
    from datetime import timedelta

    # Pre-validation: JWT must have exactly 3 dot-separated parts
    if token.count(".") != 2:
        raise ValueError("Invalid JWT format")

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            leeway=timedelta(seconds=int(settings.jwt_leeway_seconds)),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["iat", "sub"], "verify_aud": bool(settings.jwt_audience)},
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("JWT expired") from e
    except jwt.InvalidSignatureError as e:
        raise ValueError("Invalid JWT signature") from e
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT: {e}") from e
    return payload


# ── Core auth functions ──


async def authenticate(
    username: str,
    password: str,
    session: AsyncSession,
) -> User | None:
    """Look up user by username and verify password. Returns User or None."""
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_tokens(
    user: User,
    redis: Redis,
) -> dict[str, Any]:
    """Create access + refresh token pair. Store refresh jti in Redis.

    Returns: {access_token, refresh_token, expires_in, user: {username, role}}
    """
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Decode refresh to get jti for Redis storage
    refresh_payload = jwt.decode(
        refresh_token,
        settings.secret_key,
        algorithms=["HS256"],
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
            "username": user.username,
            "role": user.role,
        },
    }


async def refresh_access_token(
    refresh_token: str,
    redis: Redis,
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Use a refresh token to get a new access token.

    Validates: refresh not expired + jti exists in Redis + user still active.
    Does NOT rotate the refresh token (simpler, still secure with Redis revocation).
    """
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return None

    if payload.get("type") != "refresh":
        return None

    jti = payload.get("jti")
    if not jti:
        return None

    # Check Redis for revocation
    stored_user_id = await redis.get(f"refresh:{jti}")
    if stored_user_id is None:
        return None

    # Look up user to ensure still active
    username = payload.get("sub")
    if not username:
        return None
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    # Issue new access token
    new_access = create_access_token(user)
    return {
        "access_token": new_access,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def revoke_refresh_token(
    refresh_token: str,
    redis: Redis,
) -> bool:
    """Revoke a refresh token by deleting its jti from Redis.

    Returns True if the jti was found and deleted, False otherwise.
    """
    try:
        payload = jwt.decode(
            refresh_token,
            settings.secret_key,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        return False

    jti = payload.get("jti")
    if not jti:
        return False

    deleted = await redis.delete(f"refresh:{jti}")
    return deleted > 0


async def change_password(
    user: User,
    old_password: str,
    new_password: str,
    session: AsyncSession,
) -> bool:
    """Change a user's password. Returns True on success, False if old password wrong."""
    if not verify_password(old_password, user.password_hash):
        return False
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"New password must be at least {MIN_PASSWORD_LENGTH} characters")

    new_hash = hash_password(new_password)
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(password_hash=new_hash)
    )
    await session.commit()
    logger.info("Password changed for user '{}'", user.username)
    return True


# ── User CRUD (admin only) ──


async def list_users(session: AsyncSession) -> list[User]:
    """Return all users (password_hash excluded via to_dict)."""
    result = await session.execute(
        select(User).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def create_user(
    username: str,
    password: str,
    role: str,
    session: AsyncSession,
) -> User:
    """Create a new user. Raises ValueError if username taken or password too short."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if role not in ("admin", "user"):
        raise ValueError("Role must be 'admin' or 'user'")

    # Check uniqueness
    existing = await session.execute(
        select(User).where(User.username == username)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Username '{username}' already exists")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("User '{}' created (role={})", username, role)
    return user


async def update_user(
    user_id: str,
    role: str | None = None,
    is_active: bool | None = None,
    session: AsyncSession | None = None,
) -> User | None:
    """Update user role and/or active status. Returns updated User or None."""
    if session is None:
        return None
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None

    if role is not None:
        if role not in ("admin", "user"):
            raise ValueError("Role must be 'admin' or 'user'")
        user.role = role
    if is_active is not None:
        user.is_active = is_active

    await session.commit()
    await session.refresh(user)
    logger.info("User '{}' updated (role={}, is_active={})", user.username, user.role, user.is_active)
    return user


async def delete_user(user_id: str, session: AsyncSession) -> bool:
    """Delete a user by ID. Returns True if deleted, False if not found."""
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        return False

    await session.delete(user)
    await session.commit()
    logger.info("User '{}' deleted", user.username)
    return True


async def reset_password(
    user_id: str,
    new_password: str,
    session: AsyncSession,
) -> bool:
    """Admin reset a user's password. Returns True on success."""
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        return False

    user.password_hash = hash_password(new_password)
    await session.commit()
    logger.info("Password reset for user '{}'", user.username)
    return True
