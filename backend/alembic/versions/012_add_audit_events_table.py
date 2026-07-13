"""Add audit_events table for persisted audit logs.

Revision ID: 012
Revises: 011
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event", sa.String(50), nullable=False, comment="Audit event type: auth_failure, authz_denied, etc."),
        sa.Column("actor", sa.String(100), nullable=False, comment="user_id or 'anonymous'"),
        sa.Column("action", sa.String(100), nullable=False, comment="HTTP method + path or operation name"),
        sa.Column("detail", sa.Text, nullable=False, server_default=""),
        sa.Column("ip", sa.String(45), nullable=False, server_default="", comment="IPv4 or IPv6 address"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_events_event", "audit_events", ["event"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_event", table_name="audit_events")
    op.drop_table("audit_events")
