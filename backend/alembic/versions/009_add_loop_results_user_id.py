"""Add user_id column to loop_results table.

Revision ID: 009
Revises: 008
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add user_id column (nullable, with server_default for existing rows)
    op.add_column(
        "loop_results",
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=True,
            server_default="system",
            comment="User who triggered this loop run",
        ),
    )
    # Create index for user_id lookups
    op.create_index("ix_loop_results_user_id", "loop_results", ["user_id"])

    # Backfill existing rows: set user_id to 'system' for any NULL values
    # (server_default handles new rows, but explicit UPDATE ensures existing rows)
    op.execute(
        sa.text("UPDATE loop_results SET user_id = 'system' WHERE user_id IS NULL")
    )


def downgrade() -> None:
    op.drop_index("ix_loop_results_user_id", table_name="loop_results")
    op.drop_column("loop_results", "user_id")
