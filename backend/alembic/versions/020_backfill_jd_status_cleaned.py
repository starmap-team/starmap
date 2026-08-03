"""backfill jd_status to cleaned for historical records

Phase 3 Plan 02: PostgreSQL requires new enum values to be committed in
a separate transaction before use. Split data backfill out of 019.

Revision ID: 020
Revises: 019
"""
from __future__ import annotations

from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE jd_raw SET status = 'cleaned' "
        "WHERE status = 'raw' AND clean_text IS NOT NULL AND clean_text != ''"
    )


def downgrade() -> None:
    op.execute("UPDATE jd_raw SET status = 'raw' WHERE status = 'cleaned'")
