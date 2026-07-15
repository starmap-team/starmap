"""Extend users table with enterprise lifecycle fields.

Adds email (password-reset target), failed-login counter + lockout window,
last-login audit, password-rotation tracking, and soft-delete columns.

Revision ID: 014
Revises: 013
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Email (nullable, unique) ──
    op.add_column(
        "users",
        sa.Column("email", sa.String(120), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── Brute-force protection ──
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Audit trail ──
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_login_ip", sa.String(45), nullable=True),
    )

    # ── Password rotation policy ──
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ── Soft-delete with attribution ──
    op.add_column(
        "users",
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("disabled_by", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("disabled_reason", sa.String(255), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_disabled_by",
        "users",
        "users",
        ["disabled_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── Role enum constraint ──
    op.create_check_constraint(
        "users_role_check",
        "users",
        "role IN ('admin', 'user')",
    )


def downgrade() -> None:
    op.drop_constraint("users_role_check", "users", type_="check")
    op.drop_constraint("fk_users_disabled_by", "users", type_="foreignkey")
    op.drop_column("users", "disabled_reason")
    op.drop_column("users", "disabled_by")
    op.drop_column("users", "disabled_at")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")
