"""安全审计日志 (LOG-05 修复)。

记录关键安全事件：认证失败、权限拒绝、速率限制触发、敏感操作。
使用 loguru 结构化日志，生产环境 JSON 输出可直接接入 ELK/Loki。

ponytail: 最小实现 — loguru + 结构化 dict，无额外存储。
升级路径: 写入 PostgreSQL audit_log 表或外发 SIEM。
"""
from __future__ import annotations

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


@dataclass(frozen=True)
class AuditEntry:
    """单条审计记录。"""

    event: AuditEvent
    actor: str  # user_id or "anonymous"
    action: str  # HTTP method + path or operation name
    detail: str = ""
    ip: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def audit_log(entry: AuditEntry) -> None:
    """写入审计日志。

    使用 loguru structured binding，生产环境 JSON 输出自动包含所有字段。
    """
    logger.bind(
        audit_event=entry.event.value,
        audit_actor=entry.actor,
        audit_action=entry.action,
        audit_detail=entry.detail,
        audit_ip=entry.ip,
        **entry.extra,
    ).warning("AUDIT: {} actor={} action={} detail={}", entry.event.value, entry.actor, entry.action, entry.detail)
