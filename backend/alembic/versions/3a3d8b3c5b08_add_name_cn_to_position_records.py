"""add_name_cn_to_position_records

Revision ID: 3a3d8b3c5b08
Revises: 015
Create Date: 2026-07-20 01:16:40.496553

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3a3d8b3c5b08'
down_revision: str | Sequence[str] | None = '015'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    PATCHED (was a broken autogenerate):
    - Original generated migration also dropped 'review_audit_log' (STILL used by
      app.services.review_service for the position/skill review audit trail) and added
      a NOT NULL 'id' column to 'match_results' without a default (fails if the table
      has rows). Those operations are removed; this migration now does exactly one thing:
      add the 'name_cn' column that the PositionRecord ORM model expects.
    """
    op.add_column(
        'position_records',
        sa.Column('name_cn', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('position_records', 'name_cn')
