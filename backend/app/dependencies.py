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

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security.client_ip import resolve_client_ip
from app.services.auth_service import decode_token
from app.services.dev_token import dev_token_identity, is_dev_token_allowed
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

    生产环境: 必须提供有效 Bearer token (强制 JWT 鉴权)。
    开发环境 (默认 dev_anon_admin=False): 无 token 时返回 role=viewer
        的 dev 占位用户，访问 admin 端点会被 require_admin 拦截。
    开发环境 (显式 opt-in dev_anon_admin=True): 无 token 时返回
        role=admin 的 dev 用户，仅供本地调试 / e2e 自测用。
    """
    # 生产环境永远强制鉴权；不论 settings.dev_anon_admin 为何值
    if settings.app_env == "production" and credentials is None:
        audit_log(
            AuditEntry(
                event=AuditEvent.AUTH_FAILURE,
                actor="anonymous",
                action="missing_token",
                detail="No Bearer token provided in production",
                ip="",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Dev / 测试环境：缺 token 时按 dev_anon_admin 开关分流
    if credentials is None:
        if settings.dev_anon_admin:
            # 显式 opt-in：返回 admin（仅供本地调试）
            return {"sub": "dev", "role": "admin", "username": "developer"}
        # 默认 dev 行为：返回 viewer（低权限）而不是 admin
        # 这样默认 dev compose up 后访问 admin 端点会自然得到 403
        return {"sub": "dev", "role": "viewer", "username": "developer"}

    token = credentials.credentials

    # PLAN-015③: dev-token 守门收敛到 services.dev_token (避免历史
    # `settings.app_env != "production"` 二元判定误放行 staging/testing)
    if is_dev_token_allowed(token):
        return dev_token_identity()

    # JWT 验证
    try:
        payload = _decode_token_payload(token)
    except ValueError as e:
        err_msg = str(e)
        event = AuditEvent.TOKEN_EXPIRED if "expired" in err_msg else AuditEvent.TOKEN_INVALID
        audit_log(
            AuditEntry(
                event=event,
                actor="anonymous",
                action="jwt_validate",
                detail=err_msg,
                ip="",
            )
        )
        logger.warning("JWT validation failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # BUG-17 fix: even if JWT signature/exp is valid, reject the request if
    # the user is currently disabled. Without this, flipping is_active=False
    # in admin does not invalidate already-issued tokens until they expire.
    # We do a cheap PG lookup keyed on the JWT subject.
    sub = payload.get("sub")
    if sub and sub != "dev":
        try:
            from sqlalchemy import select

            from app.db.session import get_session_factory
            from app.models.user import User

            sm = get_session_factory()
            async with sm() as s:
                user = (
                    await s.execute(select(User).where(User.username == sub))
                ).scalar_one_or_none()
                if user is not None and not user.is_active:
                    audit_log(
                        AuditEntry(
                            event=AuditEvent.AUTHZ_DENIED,
                            actor=sub,
                            action="jwt_validate",
                            detail="Account disabled after token issuance",
                            ip="",
                        )
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Account is disabled",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            # Don't fail closed on PG hiccups — JWT signature is still valid.
            logger.warning("post-JWT is_active check skipped: {}", exc)

    return payload


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """要求 admin 角色 (AUTHZ-01 修复)。

    开发环境: 默认 dev 用户即为 admin。
    生产环境: JWT payload 中 role 必须为 "admin"。
    """
    if user.get("role") != "admin":
        audit_log(
            AuditEntry(
                event=AuditEvent.AUTHZ_DENIED,
                actor=user.get("sub", "unknown"),
                action="require_admin",
                detail=f"User role={user.get('role')} attempted admin action",
                ip="",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ══════════════════════════════════════════════════════════
# SSE 连接数限制 (API-05 修复)
# ══════════════════════════════════════════════════════════

# Per-IP SSE 连接计数 — 防止单 IP 开大量 EventSource 耗尽资源
_SSE_MAX_PER_IP = 25  # 单 IP 最大并发 SSE 连接（从 10 上调，适配前端自动刷新场景）
_SSE_MAX_GLOBAL = 500  # 全局最大并发 SSE 连接
_sse_ip_connections: dict[str, int] = defaultdict(int)
_sse_global_connections = 0
_sse_lock = asyncio.Lock()
# Stale-entry 清理：连接断开时减计数，若 IP 计数归零且距上次 connect ≥ 60s，
# 把 _sse_ip_connections 中的零值条目清掉，防止 dict 永驻（旧连接因 vite HMR /
# page reload 服务端未收到 FIN packet 时计数会卡住，导致假阳性 429）。
_SSE_STALE_CLEANUP_SECONDS = 60.0
_sse_last_connect_at: dict[str, float] = {}

# 可注入的 SSE 连接检查函数 — 测试时可替换为 no-op 避免全局状态污染。
# 使用方式: monkeypatch.setattr("app.dependencies._sse_connect_check", _noop_sse_check)
_sse_connect_check: Any = None  # None → 使用默认 sse_connect


async def sse_connect(client_ip: str) -> None:
    """在 SSE 连接建立时调用，检查连接数限制。超限抛 429。"""
    global _sse_global_connections
    async with _sse_lock:
        if _sse_global_connections >= _SSE_MAX_GLOBAL:
            audit_log(
                AuditEntry(
                    event=AuditEvent.RATE_LIMITED,
                    actor=client_ip,
                    action="sse_connect",
                    detail=f"Global SSE limit reached ({_SSE_MAX_GLOBAL})",
                    ip=client_ip,
                )
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many SSE connections. Try again later.",
            )
        if _sse_ip_connections[client_ip] >= _SSE_MAX_PER_IP:
            audit_log(
                AuditEntry(
                    event=AuditEvent.RATE_LIMITED,
                    actor=client_ip,
                    action="sse_connect",
                    detail=f"Per-IP SSE limit reached ({_SSE_MAX_PER_IP})",
                    ip=client_ip,
                )
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many SSE connections from your IP. Try again later.",
            )
        _sse_ip_connections[client_ip] += 1
        _sse_global_connections += 1
        # 记录本次 connect 时间，供 sweep_stale_sse_counters 兜底
        import time as _time
        _sse_last_connect_at[client_ip] = _time.monotonic()


async def sse_disconnect(client_ip: str) -> None:
    """在 SSE 连接断开时调用，释放连接计数。

    P2-16 fix: 安全断开 — 先检查再减，防止负数泄漏；
    同时清理 IP 计数归零的条目，防止 _sse_ip_connections 无限增长。
    """
    global _sse_global_connections
    async with _sse_lock:
        if _sse_ip_connections.get(client_ip, 0) > 0:
            _sse_ip_connections[client_ip] -= 1
            # 清理归零条目，防止 dict 无限膨胀
            if _sse_ip_connections[client_ip] <= 0:
                _sse_ip_connections.pop(client_ip, None)
        if _sse_global_connections > 0:
            _sse_global_connections -= 1


async def sweep_stale_sse_counters() -> int:
    """扫描并清理卡住的 SSE 计数（dev 环境 stale 连接兜底）。

    触发条件: IP 计数 > 0 但距上次 connect 已过 ≥ _SSE_STALE_CLEANUP_SECONDS
    且该 IP 上 _active stream 已断开（依赖 _sse_last_connect_at 时间戳）。

    调用场景:
    - 服务端健康检查（health/detail endpoint）
    - 定时 Celery beat 任务（每小时一次）
    - FastAPI startup hook（每次进程重启）

    返回: 清理的 IP 数。失败计数仍可能存在，但已不再增长。
    """
    import time as _time

    cleaned = 0
    now = _time.monotonic()
    async with _sse_lock:
        stale_ips = [
            ip for ip, last_at in _sse_last_connect_at.items()
            if (now - last_at) >= _SSE_STALE_CLEANUP_SECONDS
            and _sse_ip_connections.get(ip, 0) > 0
        ]
        for ip in stale_ips:
            leaked = _sse_ip_connections.pop(ip, 0)
            _sse_last_connect_at.pop(ip, None)
            if leaked > 0:
                # 同步减全局计数
                global _sse_global_connections
                _sse_global_connections = max(0, _sse_global_connections - leaked)
                cleaned += 1
                logger.warning(
                    "[sse-limit] swept stale counter for ip={} leaked={} (no FIN in {}s)",
                    ip, leaked, int(_SSE_STALE_CLEANUP_SECONDS),
                )
    return cleaned


async def get_current_user_sse(
    request: Request,
    token: str | None = Query(None, description="JWT token (EventSource fallback)"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """SSE-friendly auth: accept token via query param OR Authorization header (LOOP-02).

    EventSource API doesn't support custom headers, so the frontend passes
    the JWT token as a ``?token=xxx`` query parameter. This dependency checks
    the query param first, then falls back to the standard Bearer header.

    P0-F2 fix: when the query-param token is expired, the 401 response includes
    ``X-Token-Expired: true`` so the frontend SSE composable can trigger a
    silent refresh before reconnecting (EventSource cannot set Authorization
    headers, so the standard 401→refresh→retry flow in request.ts is bypassed).

    API-05 fix: per-IP + global SSE connection limit to prevent resource exhaustion.
    """
    # API-05: 检查 SSE 连接数限制
    # 通过 _sse_connect_check 注入点，测试可替换为 no-op 避免全局状态污染
    client_ip = resolve_client_ip(request)
    check_fn = _sse_connect_check or sse_connect
    await check_fn(client_ip)

    # Try query-param token first (for EventSource connections)
    if token:
        # PLAN-015③: dev-token 守门收敛到 services.dev_token (SSE 路径同上)
        if is_dev_token_allowed(token):
            return dev_token_identity()
        try:
            payload = _decode_token_payload(token)
            return payload
        except ValueError as e:
            err_msg = str(e)
            is_expired = "expired" in err_msg
            event = AuditEvent.TOKEN_EXPIRED if is_expired else AuditEvent.TOKEN_INVALID
            audit_log(
                AuditEntry(
                    event=event,
                    actor="anonymous",
                    action="jwt_validate_sse",
                    detail=err_msg,
                    ip=resolve_client_ip(request),
                )
            )
            logger.warning("SSE JWT validation failed: {}", e)
            headers: dict[str, str] = {}
            if is_expired:
                # P0-F2: signal to frontend that a silent refresh may recover
                headers["X-Token-Expired"] = "true"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers=headers,
            ) from e

    # Fall back to standard Bearer header auth
    return await get_current_user(credentials)
