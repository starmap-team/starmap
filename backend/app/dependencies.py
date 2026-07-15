"""Dependency injection + 认证依赖.

P0 修复 (AUTH-01/AUTHZ-01): JWT 认证基础设施。
- 生产环境 (app_env=production): 强制 JWT 验证
- 开发环境: 使用 Bearer token 或默认 dev 用户（宽松模式，便于调试）

Phase DB-AUTH:
- Token decode now goes through app.services.auth_service.decode_token
  (which enforces aud/iss + leeway uniformly).
- AUTH_USERS env-var bypass removed.
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
from app.services.auth_service import decode_token
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
    """Yield an async DB session that auto-commits on success and auto-rolls back on exception.

    Delegates to app.db.session.get_db_session which provides the commit/rollback
    guarantee. Kept here as a FastAPI dependency injection point.
    """
    from app.db.session import get_db_session as _get_db_session

    async with _get_db_session() as session:
        yield session


# ══════════════════════════════════════════════════════════
# 认证依赖 (AUTH-01 修复)
# ══════════════════════════════════════════════════════════


def _decode_token_payload(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Routes through auth_service.decode_token so we keep one
    aud/iss/leeway policy across all entry points (HTTP, SSE).
    """
    try:
        return decode_token(token)
    except Exception as exc:  # auth_service.InvalidTokenError is the only expected one
        raise ValueError(str(exc)) from exc


# Backwards-compat alias — legacy code (and tests) imported `_decode_token`
# from this module. Phase DB-AUTH moved the implementation to
# app.services.auth_service.decode_token but we keep the old name to avoid
# breaking importers; it raises ValueError on failure, matching the
# historical behaviour.
def _decode_token(token: str) -> dict[str, Any]:
    """Deprecated alias — prefer app.services.auth_service.decode_token.

    Raises ValueError (not InvalidTokenError) to preserve legacy callers
    that catch ValueError specifically.
    """
    try:
        return decode_token(token)
    except Exception as exc:
        raise ValueError(str(exc)) from exc


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
        payload = _decode_token_payload(token)
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
            payload = _decode_token_payload(token)
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
