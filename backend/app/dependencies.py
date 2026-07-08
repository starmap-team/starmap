"""Dependency injection + 认证依赖。

P0 修复 (AUTH-01/AUTHZ-01): 添加 JWT 认证基础设施。
- 生产环境 (app_env=production): 强制 JWT 验证
- 开发环境: 使用 Bearer token 或默认 dev 用户（宽松模式，便于调试）
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, HTTPException, Request, status
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
    """解码 JWT token。使用 HMAC-SHA256，密钥来自 settings.secret_key。"""
    import base64
    import hashlib
    import hmac
    import json

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    # 验证签名
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    sig = hmac.new(
        settings.secret_key.encode(), signing_input, hashlib.sha256
    ).digest()
    expected_sig = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    if not hmac.compare_digest(expected_sig, parts[2]):
        raise ValueError("Invalid JWT signature")

    # 解码 payload
    payload_b64 = parts[1]
    # 补齐 padding
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)

    # 检查过期
    import time
    exp = payload.get("exp")
    if exp and exp < time.time():
        raise ValueError("JWT expired")

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
