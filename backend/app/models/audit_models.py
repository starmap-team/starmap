"""Audit event SQLAlchemy model — persists audit logs to PostgreSQL.

Phase 17: Dual-write — loguru structured logging (existing) + DB persistence.
The DB write is fire-and-forget async so it never blocks the caller.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AuditEventRecord(Base):
    """Persisted audit event row.

    Mirrors the fields from utils/audit.py AuditEntry dataclass,
    but stored in the ``audit_events`` table for querying / dashboards.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Audit event type: auth_failure, authz_denied, etc.",
    )
    actor: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="user_id or 'anonymous'",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="HTTP method + path or operation name",
    )
    detail: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
    )
    ip: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        server_default="",
        comment="IPv4 or IPv6 address",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
