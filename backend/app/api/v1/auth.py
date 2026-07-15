"""Authentication API — thin wrappers over app.services.auth_service.

Endpoints (all under /api/v1/auth):
- POST /login             username + password → access + refresh token pair
- POST /refresh           refresh_token → new access_token
- POST /logout            refresh_token → revoke jti in Redis
- GET  /me                current authenticated user (DB truth)
- POST /change-password   self-service password change
- POST /forgot-password   start password-reset flow (returns token in dev)
- POST /reset-password    complete password-reset flow with token

Replace-the-legacy-`AUTH_USERS`-env-var: this router now authenticates
exclusively against the PostgreSQL `users` table with bcrypt-hashed
passwords (see app.services.auth_service).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    _bearer_scheme,
    _decode_token_payload,
    get_current_user,
    get_db_session,
    get_redis_client,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


# ═══════════════════════════════════════════════════════════════
# Pydantic schemas
# ═══════════════════════════════════════════════════════════════


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict[str, Any]


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=auth_service.MIN_PASSWORD_LENGTH, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=auth_service.MIN_PASSWORD_LENGTH, max_length=128)


# ═══════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════


def get_client_ip(request: Request) -> str:
    """FastAPI dependency that returns the client IP for the current request."""
    if request.client is None:
        return ""
    return request.client.host


def _domain_error_to_http(exc: auth_service.AuthError) -> HTTPException:
    """Map domain exceptions to HTTP responses with Chinese error messages."""
    if isinstance(exc, auth_service.InvalidCredentialsError):
        detail_zh = "用户名或密码错误"
    elif isinstance(exc, auth_service.AccountLockedError):
        detail_zh = "登录失败次数过多，账号已被临时锁定，请稍后再试"
    elif isinstance(exc, auth_service.AccountDisabledError):
        detail_zh = "账号已被停用，请联系管理员"
    elif isinstance(exc, auth_service.PasswordPolicyError):
        detail_zh = str(exc)  # message already policy-shaped
    elif isinstance(exc, auth_service.UserNotFoundError):
        detail_zh = "用户不存在"
    elif isinstance(exc, auth_service.UsernameTakenError):
        detail_zh = "用户名已被占用"
    elif isinstance(exc, auth_service.InvalidTokenError):
        detail_zh = "令牌无效或已过期"
    else:
        detail_zh = "认证服务错误"
    return HTTPException(status_code=exc.http_status, detail=detail_zh)


# ═══════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis | None = Depends(get_redis_client),
    client_ip: str = Depends(get_client_ip),
) -> dict[str, Any]:
    """Authenticate username + password against DB; issue access+refresh pair."""
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable — token refresh cannot run",
        )
    ip = client_ip
    try:
        user = await auth_service.authenticate(
            body.username, body.password, session, client_ip=ip
        )
    except auth_service.AuthError as exc:
        raise _domain_error_to_http(exc) from exc

    return await auth_service.create_tokens(user, redis)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis | None = Depends(get_redis_client),
) -> dict[str, Any]:
    """Exchange a refresh token for a new access token."""
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )
    result = await auth_service.refresh_access_token(
        body.refresh_token, redis, session
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    redis: Redis | None = Depends(get_redis_client),
) -> dict[str, Any]:
    """Revoke the refresh token (best-effort). Returns the count deleted."""
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )
    revoked = await auth_service.revoke_refresh_token(body.refresh_token, redis)
    return {"revoked": revoked}


@router.get("/me")
async def me(
    session: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """Return the current authenticated user (server truth, not JWT-only).

    Requires a valid JWT — does NOT accept the dev-mode fallback from
    get_current_user, because /me is the canonical "who am I" endpoint
    and returning a fake dev user would mask real auth failures with
    confusing 404s ("User not found" for the non-existent dev account).
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = _decode_token_payload(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    db_user = await auth_service.get_user_by_username(session, username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user.to_dict()


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Self-service password change (requires old password)."""
    username = user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = await auth_service.get_user_by_username(session, username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        ok = await auth_service.change_password(
            db_user,
            body.old_password,
            body.new_password,
            session,
            actor=username,
        )
    except auth_service.AuthError as exc:
        raise _domain_error_to_http(exc) from exc

    if not ok:
        raise HTTPException(status_code=400, detail="原密码错误")

    return {"changed": True}


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis | None = Depends(get_redis_client),
) -> dict[str, Any]:
    """Initiate password reset. Always returns ok (avoid email enumeration)."""
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )
    token = await auth_service.forgot_password_request(body.email, redis, session)
    if token is None:
        # Email not registered — still return success, but no token
        return {"submitted": True, "token": None}
    # In production this token would be sent via email. For now we return it
    # so frontends / smoke tests can complete the flow.
    return {"submitted": True, "token": token}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis | None = Depends(get_redis_client),
) -> dict[str, Any]:
    """Complete password reset using the token issued by /forgot-password."""
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )
    try:
        await auth_service.reset_password_with_token(
            body.token, body.new_password, redis, session
        )
    except auth_service.AuthError as exc:
        raise _domain_error_to_http(exc) from exc
    return {"reset": True}
