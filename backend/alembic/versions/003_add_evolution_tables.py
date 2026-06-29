"""Create evolution subsystem tables: snapshots, changelog, paths, timeseries.

Revision ID: 003
Revises: 002
Create Date: 2026-06-28 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evolution_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("position_name", sa.String(255), nullable=False),
        sa.Column("snapshot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_skills", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("preferred_skills", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_evolution_snapshots_position_name", "evolution_snapshots", ["position_name"])
    op.create_index("ix_evolution_snapshots_snapshot_date", "evolution_snapshots", ["snapshot_date"])

    op.create_table(
        "evolution_changelog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("position_name", sa.String(255), nullable=False),
        sa.Column("skill_name", sa.String(255), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("old_proficiency", sa.String(50), nullable=True),
        sa.Column("new_proficiency", sa.String(50), nullable=True),
        sa.Column("old_requirement", sa.String(20), nullable=True),
        sa.Column("new_requirement", sa.String(20), nullable=True),
        sa.Column("snapshot_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("evidence_json", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_evolution_changelog_position_name", "evolution_changelog", ["position_name"])
    op.create_index("ix_evolution_changelog_skill_name", "evolution_changelog", ["skill_name"])
    op.create_index("ix_evolution_changelog_snapshot_from_id", "evolution_changelog", ["snapshot_from_id"])
    op.create_index("ix_evolution_changelog_snapshot_to_id", "evolution_changelog", ["snapshot_to_id"])

    op.create_table(
        "evolution_paths",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_position", sa.String(255), nullable=False),
        sa.Column("target_position", sa.String(255), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skill_overlap", postgresql.JSON(), nullable=True),
        sa.Column("key_gaps", postgresql.JSON(), nullable=True),
        sa.Column("avg_months", sa.Float(), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("first_detected", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_evolution_paths_source_position", "evolution_paths", ["source_position"])
    op.create_index("ix_evolution_paths_target_position", "evolution_paths", ["target_position"])

    op.create_table(
        "skill_timeseries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("skill_name", sa.String(255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positions", postgresql.JSON(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False, server_default="general"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_skill_timeseries_skill_name", "skill_timeseries", ["skill_name"])
    op.create_index("ix_skill_timeseries_window_start", "skill_timeseries", ["window_start"])


def downgrade() -> None:
    op.drop_table("skill_timeseries")
    op.drop_table("evolution_paths")
    op.drop_table("evolution_changelog")
    op.drop_table("evolution_snapshots")
