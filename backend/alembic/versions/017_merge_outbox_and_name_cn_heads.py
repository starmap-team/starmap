"""Merge two outbox / name_cn heads under 015.

Phase 7 fix: 016 (outbox run_id nullable) and 3a3d8b3c5b08 (add_name_cn_to
_position_records) both branched from 015, blocking ``alembic upgrade head``.
This empty merge rev joins both branches under a single 017 head.

Revision ID: 017
Revises: 016, 3a3d8b3c5b08
Create Date: 2026-07-23
"""
from collections.abc import Sequence

from alembic import op

revision: str = "017"
down_revision: tuple[str, str] | None = ("016", "3a3d8b3c5b08")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Empty merge — both branches are independent schema changes.
    pass


def downgrade() -> None:
    # No-op merge: downgrade path for both children remains intact.
    pass
