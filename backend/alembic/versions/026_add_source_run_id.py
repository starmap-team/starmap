"""add source_run_id to position_records and skill_records

Revision ID: 026_add_source_run_id
Revises: 025_add_pipeline_indexes
Create Date: 2026-07-28

业务说明：为岗位和技能记录增加数据来源追溯字段，
关联到产生该记录的 Pipeline Run，支持按运行审核数据。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_records",
        sa.Column("source_run_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_position_records_source_run_id",
        "position_records",
        ["source_run_id"],
    )
    op.add_column(
        "skill_records",
        sa.Column("source_run_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_skill_records_source_run_id",
        "skill_records",
        ["source_run_id"],
    )
    # 批量 approve 已有数据: 它们已在图谱中，保持连续性。
    # 新数据将默认 pending_review，需人工审核后才进入图谱。
    op.execute(
        "UPDATE position_records SET review_status = 'approved', "
        "reviewed_by = 'system:migration', reviewed_at = NOW() "
        "WHERE review_status = 'pending_review'"
    )
    op.execute(
        "UPDATE skill_records SET review_status = 'approved', "
        "reviewed_by = 'system:migration', reviewed_at = NOW() "
        "WHERE review_status = 'pending_review'"
    )


def downgrade() -> None:
    op.drop_index("ix_skill_records_source_run_id", table_name="skill_records")
    op.drop_column("skill_records", "source_run_id")
    op.drop_index("ix_position_records_source_run_id", table_name="position_records")
    op.drop_column("position_records", "source_run_id")
