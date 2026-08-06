"""Add status column to evolution_changelog.

Revision ID: 004
Revises: 003
Create Date: 2026-07-20

NOTE (2026-07-24): This file was renamed from 004_add_changelog_status.py to
004a_add_changelog_status.py to disambiguate from 004b_add_match_results_table.py.
Both share revision ID "004" (branch point from 003). This is a known Alembic
branch — use `alembic upgrade 017` to specify the target explicitly.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004a"  # 2026-08-07 唯一化 (与 004b 重复导致 005 down 悬空)
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
dends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add status column with default 'pending'
    op.add_column(
        "evolution_changelog",
        sa.Column("status", sa.String(20), nullable=True, server_default="pending"),
    )

    # Create composite index for review-queue queries
    op.create_index(
        "ix_evolution_changelog_status_trust",
        "evolution_changelog",
        ["status", "trust_score"],
    )

    # Backfill existing data: trust_score < 0.5 -> pending, others -> approved
    op.execute(
        """
        UPDATE evolution_changelog
        SET status = CASE
            WHEN trust_score < 0.5 THEN 'pending'
            ELSE 'approved'
        END
        WHERE status IS NULL OR status = 'pending'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_evolution_changelog_status_trust", table_name="evolution_changelog")
    op.drop_column("evolution_changelog", "status")
