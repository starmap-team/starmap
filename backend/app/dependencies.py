"""Dependency injection + 认证依赖。

P0 修复 (AUTH-01/AUTHZ-01): 添加 JWT 认证基础设施。
- 生产环境 (app_env=production): 强制 JWT 验证
- 开发环境: 使用 Bearer token 或默认 dev 用户（宽松模式，便于调试）
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.resources import resources
from app.utils.audit import AuditEntry, AuditEvent, audit_log

# ── Bearer token scheme ──
_bearer_scheme = HTTPBearer(auto_error=False)


def get_neo4j_driver(request: Request) -> Any:
    res = getattr(request.app.state, "resources", None)
    if res is None:
        return None
    return res.neo4j_driver


def get_redis_client(request: Request) -> Redis | None:
    res = getattr(request.app.state, "resources", None)
    if res is None:
        return None
    return res.redis_client


async def get_db_session() -> AsyncIterator[AsyncSession]:
    if resources.pg_sessionmaker is None:
        raise RuntimeError("PostgreSQL sessionmaker not initialized")
    async with resources.pg_sessionmaker() as session:
        yield session


# ══════════════════════════════════════════════════════════
# 认证依赖 (AUTH-01 修复)
# ══════════════════════════════════════════════════════════


def _decode_token(token: str) -> dict[str, Any]:
    """解码 JWT token。使用 PyJWT，密钥来自 settings.secret_key。"""
    import jwt as _jwt
    from datetime import timedelta

    try:
        payload = _jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            leeway=timedelta(seconds=settings.jwt_leeway_seconds),
            options={
                "require": ["exp", "iat", "sub"],
                "verify_aud": False,  # Phase A: don't enforce aud claim yet
            },
        )
    except _jwt.ExpiredSignatureError as e:
        raise ValueError("JWT expired") from e
    except _jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT: {e}") from e
    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """获取当前认证用户。

    开发环境: 无 token 时返回 dev 默认用户（便于调试）。
    生产环境: 必须提供有效 Bearer token。
    """
    # 开发环境宽松模式：无 token 时返回默认用户
    if credentials is None:
        if settings.app_env != "production":
            return {"sub": "dev", "role": "admin", "username": "developer"}
        audit_log(AuditEntry(
            event=AuditEvent.AUTH_FAILURE,
            actor="anonymous",
            action="missing_token",
            detail="No Bearer token provided in production",
            ip="",
        ))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 开发环境：接受固定 dev token
    if settings.app_env != "production" and token == "dev-token":
        return {"sub": "dev", "role": "admin", "username": "developer"}

    # JWT 验证
    try:
        payload = _decode_token(token)
    except ValueError as e:
        err_msg = str(e)
        event = AuditEvent.TOKEN_EXPIRED if "expired" in err_msg else AuditEvent.TOKEN_INVALID
        audit_log(AuditEntry(
            event=event,
            actor="anonymous",
            action="jwt_validate",
            detail=err_msg,
            ip="",
        ))
        logger.warning("JWT validation failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    return payload


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """要求 admin 角色 (AUTHZ-01 修复)。

    开发环境: 默认 dev 用户即为 admin。
    生产环境: JWT payload 中 role 必须为 "admin"。
    """
    if user.get("role") != "admin":
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=user.get("sub", "unknown"),
            action="require_admin",
            detail=f"User role={user.get('role')} attempted admin action",
            ip="",
        ))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_current_user_sse(
    token: str | None = Query(None, description="JWT token (EventSource fallback)"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """SSE-friendly auth: accept token via query param OR Authorization header (LOOP-02).

    EventSource API doesn't support custom headers, so the frontend passes
    the JWT token as a ``?token=xxx`` query parameter. This dependency checks
    the query param first, then falls back to the standard Bearer header.
    """
    # Try query-param token first (for EventSource connections)
    if token:
        # 开发环境：接受固定 dev token
        if settings.app_env != "production" and token == "dev-token":
            return {"sub": "dev", "role": "admin", "username": "developer"}
        try:
            payload = _decode_token(token)
            return payload
        except ValueError as e:
            err_msg = str(e)
            event = AuditEvent.TOKEN_EXPIRED if "expired" in err_msg else AuditEvent.TOKEN_INVALID
            audit_log(AuditEntry(
                event=event,
                actor="anonymous",
                action="jwt_validate_sse",
                detail=err_msg,
                ip="",
            ))
            logger.warning("SSE JWT validation failed: {}", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from e

    # Fall back to standard Bearer header auth
    return await get_current_user(credentials)
