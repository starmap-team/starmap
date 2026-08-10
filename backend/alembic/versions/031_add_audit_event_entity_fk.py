"""Add entity_type / entity_id to audit_events (admin audit traceability, 2026-08-09).

BUG-18 fix: previously audit_events only logged (event, actor, action, detail)
strings. There was no link from an audit row to the specific entity (position /
skill / user / etc.) it acted on, making "who approved which skill?" queries
impossible to answer without scanning detail text.

After this migration:
  - entity_type VARCHAR(32) — e.g. 'position', 'skill', 'user', 'graph_node'
  - entity_id VARCHAR(64) — string-form UUID or other identifier
  - composite index on (entity_type, entity_id) for "show me everything that
    happened to entity X" queries
  - existing rows get NULL (legacy audit entries keep their detail string)

Idempotent / additive — no data loss.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "031"
down_revision: tuple[str, ...] = ("030",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("entity_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("entity_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_column("audit_events", "entity_id")
    op.drop_column("audit_events", "entity_type")
