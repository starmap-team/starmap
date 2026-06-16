"""jd_raw 初始 schema 迁移。"""
from alembic import op
import sqlalchemy as sa


revision = "0001_init_jd_raw"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_site", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(200), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("status", sa.Enum("raw", "extracted", "duplicate", "failed", name="jd_status"), nullable=False, server_default="raw"),
        sa.Column("error_msg", sa.Text(), nullable=True),
    )
    op.create_index("idx_jd_raw_status", "jd_raw", ["status"])
    op.create_index("idx_jd_raw_source_site", "jd_raw", ["source_site"])
    op.create_index("idx_jd_raw_crawled_at", "jd_raw", ["crawled_at"])
    op.create_index("idx_jd_raw_content_hash", "jd_raw", ["content_hash"])

    op.create_table(
        "compliance_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_site", sa.String(32), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("robots_allowed", sa.Boolean(), nullable=False),
        sa.Column("user_agent", sa.String(200), nullable=False),
        sa.Column("qps", sa.Float(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=False),
        sa.Column("response_bytes", sa.Integer(), nullable=True),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("compliance_log")
    op.drop_index("idx_jd_raw_content_hash", table_name="jd_raw")
    op.drop_index("idx_jd_raw_crawled_at", table_name="jd_raw")
    op.drop_index("idx_jd_raw_source_site", table_name="jd_raw")
    op.drop_index("idx_jd_raw_status", table_name="jd_raw")
    op.drop_table("jd_raw")
    sa.Enum(name="jd_status").drop(op.get_bind(), checkfirst=True)
