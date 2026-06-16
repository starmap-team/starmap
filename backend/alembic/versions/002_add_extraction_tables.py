"""Create remaining 5 extraction tables: raw_jd, alias, evaluation, relations, config.

Revision ID: 002
Revises: 001
Create Date: 2026-06-16 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 4. raw_jd_records ---
    op.create_table(
        "raw_jd_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_platform", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("title_raw", sa.String(255), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("crawl_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hash_dedup", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_raw_jd_hash_dedup", "raw_jd_records", ["hash_dedup"])
    op.create_index("ix_raw_jd_crawl_time", "raw_jd_records", ["crawl_time"])

    # --- 5. skill_alias_records ---
    op.create_table(
        "skill_alias_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("standard_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_skill_alias_alias", "skill_alias_records", ["alias"])

    # --- 6. extraction_evaluation_records ---
    op.create_table(
        "extraction_evaluation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("golden_id", sa.String(100), nullable=False),
        sa.Column("precision", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("recall", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("f1_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("job_title_match", sa.Boolean(), nullable=True),
        sa.Column("experience_error", sa.Float(), nullable=True),
        sa.Column("education_match", sa.Boolean(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_eval_extraction_id", "extraction_evaluation_records", ["extraction_id"])

    # --- 7. position_skill_relations ---
    op.create_table(
        "position_skill_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_type", sa.String(20), nullable=False, server_default="required"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_psr_position_id", "position_skill_relations", ["position_id"])
    op.create_index("ix_psr_skill_id", "position_skill_relations", ["skill_id"])

    # --- 8. system_config ---
    op.create_table(
        "system_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("config_key", sa.String(100), unique=True, nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("config_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_system_config_key", "system_config", ["config_key"])

    # --- Seed prompt version ---
    op.execute(
        sa.text(
            """INSERT INTO system_config (config_key, config_value, config_type, description)
VALUES ('prompt.jd_extraction.version', '1.0', 'string', 'Current JD extraction prompt version');"""
        )
    )


def downgrade() -> None:
    op.drop_table("system_config")
    op.drop_table("position_skill_relations")
    op.drop_table("extraction_evaluation_records")
    op.drop_table("skill_alias_records")
    op.drop_table("raw_jd_records")
