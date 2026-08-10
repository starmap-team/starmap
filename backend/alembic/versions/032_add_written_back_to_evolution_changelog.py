"""Add written_back column to evolution_changelog (D-06 write-back marker).

D-06: changelog rows that were successfully upserted into
position_skill_relations are marked written_back=true so the dashboard /
audit can distinguish "written back to SSOT" from "review-only". Additive,
server_default=false so existing rows are all False.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "032"
down_revision: tuple[str, ...] = ("031",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evolution_changelog",
        sa.Column("written_back", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_evolution_changelog_written_back",
        "evolution_changelog",
        ["written_back"],
    )


def downgrade() -> None:
    op.drop_index("ix_evolution_changelog_written_back", table_name="evolution_changelog")
    op.drop_column("evolution_changelog", "written_back")
