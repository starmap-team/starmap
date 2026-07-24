"""Add status column to evolution_changelog (reapply — 004 was never executed).

Revision ID: 018
Revises: 017
Create Date: 2026-07-23
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add status column with default 'pending'
    op.add_column(
        "evolution_changelog",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )

    # Create composite index for review-queue queries
    op.create_index(
        "ix_evolution_changelog_status_trust",
        "evolution_changelog",
        ["status", "trust_score"],
    )


def downgrade() -> None:
    op.drop_index("ix_evolution_changelog_status_trust", table_name="evolution_changelog")
    op.drop_column("evolution_changelog", "status")
