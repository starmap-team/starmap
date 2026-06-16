"""Initial migration: create extraction and skill tables.

Revision ID: 001
Revises:
Create Date: 2026-06-15 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = "20260616_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create jd_extraction_records, skill_records, position_records tables."""

    op.create_table(
        "jd_extraction_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("jd_content", sa.Text(), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("extracted_skills", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("education", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("hallucination_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )

    op.create_index(
        "ix_jd_extraction_records_status",
        "jd_extraction_records",
        ["status"],
    )
    op.create_index(
        "ix_jd_extraction_records_created_at",
        "jd_extraction_records",
        ["created_at"],
    )

    op.create_table(
        "skill_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="general"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_skill_records_name", "skill_records", ["name"])
    op.create_index("ix_skill_records_category", "skill_records", ["category"])

    op.create_table(
        "position_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_position_records_name", "position_records", ["name"])


def downgrade() -> None:
    """Drop all created tables."""
    op.drop_table("position_records")
    op.drop_table("skill_records")
    op.drop_table("jd_extraction_records")
