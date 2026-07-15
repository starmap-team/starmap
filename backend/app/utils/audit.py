"""安全审计日志 (LOG-05 修复)。

记录关键安全事件：认证失败、权限拒绝、速率限制触发、敏感操作。
使用 loguru 结构化日志，生产环境 JSON 输出可直接接入 ELK/Loki。
同时异步双写到 PostgreSQL audit_events 表（fire-and-forget，不阻塞调用方）。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger


class AuditEvent(StrEnum):
    """审计事件类型。"""

    AUTH_FAILURE = "auth_failure"
    AUTHZ_DENIED = "authz_denied"
    RATE_LIMITED = "rate_limited"
    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    SENSITIVE_READ = "sensitive_read"
    SENSITIVE_WRITE = "sensitive_write"
    FILE_UPLOAD = "file_upload"
    ADMIN_ACTION = "admin_action"
    # ── User lifecycle (Phase DB-AUTH) ──
    LOGIN_LOCKED = "login_locked"
    LOGIN_SUCCESS = "login_success"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DISABLED = "user_disabled"
    USER_UNLOCKED = "user_unlocked"
    ACCOUNT_DELETED = "account_deleted"


@dataclass(frozen=True)
class AuditEntry:
    """单条审计记录。"""

    event: AuditEvent
    actor: str  # user_id or "anonymous"
    action: str  # HTTP method + path or operation name
    detail: str = ""
    ip: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


async def _persist_to_db(entry: AuditEntry) -> None:
    """Fire-and-forget async DB persist. Silently catches all errors."""
    try:
        from app.db.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            from app.models.audit_models import AuditEventRecord

            record = AuditEventRecord(
                event=entry.event.value,
                actor=entry.actor,
                action=entry.action,
                detail=entry.detail[:500] if entry.detail else "",
                ip=entry.ip,
            )
            session.add(record)
            await session.commit()
    except Exception as e:
        # DB failures must NEVER block the caller — log and move on
        logger.debug("Audit DB persist failed (non-blocking): {}", e)


def audit_log(entry: AuditEntry) -> None:
    """写入审计日志。

    使用 loguru structured binding，生产环境 JSON 输出自动包含所有字段。
    同时异步双写到 PostgreSQL audit_events 表（fire-and-forget）。
    """
    logger.bind(
        audit_event=entry.event.value,
        audit_actor=entry.actor,
        audit_action=entry.action,
        audit_detail=entry.detail,
        audit_ip=entry.ip,
        **entry.extra,
    ).warning("AUDIT: {} actor={} action={} detail={}", entry.event.value, entry.actor, entry.action, entry.detail)

    # Fire-and-forget DB persist — never blocks the caller
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_to_db(entry))
    except RuntimeError:
        # No running event loop (e.g. sync context) — skip DB persist silently
        pass
