"""PostgreSQL SQLAlchemy model for user accounts.

Supports the login-module-redesign: database-backed users with bcrypt
password hashing, replacing the legacy AUTH_USERS environment variable.

Enterprise lifecycle fields (Phase DB-AUTH):
- email: password-reset target
- failed_login_attempts / locked_until: brute-force protection
- last_login_at / last_login_ip: audit trail
- password_changed_at / must_change_password: password-rotation policy
- disabled_at / disabled_by / disabled_reason: soft-delete with attribution
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# ── Role constants (use these in code instead of magic strings) ──
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ALLOWED_ROLES = frozenset({ROLE_ADMIN, ROLE_USER})


class User(Base):
    """User account table for authentication and authorization.

    Replaces the legacy AUTH_USERS env-var approach. Passwords are stored
    as bcrypt hashes only. The initial admin is seeded via bootstrap.py.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'user')",
            name="users_role_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ROLE_USER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # ── Lifecycle (added in migration 014) ──
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    disabled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    disabled_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def to_dict(self) -> dict[str, object]:
        """Serialize user for API responses (excludes password_hash)."""
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "must_change_password": self.must_change_password,
            "failed_login_attempts": self.failed_login_attempts,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "last_login_ip": self.last_login_ip,
            "password_changed_at": (
                self.password_changed_at.isoformat() if self.password_changed_at else None
            ),
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "disabled_by": str(self.disabled_by) if self.disabled_by else None,
            "disabled_reason": self.disabled_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_locked(self) -> bool:
        """True if the user is currently within a lockout window."""
        return (
            self.locked_until is not None
            and self.locked_until > datetime.now(UTC)
        )

    @property
    def is_disabled(self) -> bool:
        """True if the user has been soft-deleted by an admin."""
        return self.disabled_at is not None

    @property
    def is_login_blocked(self) -> bool:
        """True if account cannot log in (inactive, disabled, or locked)."""
        return (
            not self.is_active
            or self.is_disabled
            or self.is_locked
        )
