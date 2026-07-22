"""Allow NULL run_id on graph_write_outbox for ad-hoc extractions.

H1 fix: manual single-extraction calls (run_batch_extract_jd outside a
pipeline run) have no PipelineRun to link to. Previously they used UUID nil
which made all manual runs share one index key, hurting audit traceability.
Now run_id is nullable; extraction_ids (already a JSON list column) carries
the link to JDExtractionRecord IDs for these rows.

Revision ID: 016
Revises: 015
Create Date: 2026-07-22
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ponytail: table may not exist if bootstrap relies on ORM create_all or if
    # the schema was hand-created. Create-if-not-exists keeps 016 idempotent
    # so first-run fresh DBs don't fail the container healthcheck.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_write_outbox (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID,
            extraction_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            triples_written INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
        """
    )
    op.create_index(
        "ix_graph_write_outbox_run_id",
        "graph_write_outbox",
        ["run_id"],
        unique=False,
        if_not_exists=True,
    )

    # H1 fix: relax NOT NULL → NULL on run_id for ad-hoc extractions.
    op.alter_column(
        "graph_write_outbox",
        "run_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=True,
    )
    # Backfill: any legacy UUID nil rows → NULL (cleans up the prior workaround).
    op.execute(
        "UPDATE graph_write_outbox SET run_id = NULL "
        "WHERE run_id = '00000000-0000-0000-0000-000000000000'"
    )


def downgrade() -> None:
    # Re-introduce NOT NULL. Existing NULL rows must be backfilled first.
    op.execute(
        "UPDATE graph_write_outbox SET run_id = '00000000-0000-0000-0000-000000000000' "
        "WHERE run_id IS NULL"
    )
    op.alter_column(
        "graph_write_outbox",
        "run_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=False,
    )
