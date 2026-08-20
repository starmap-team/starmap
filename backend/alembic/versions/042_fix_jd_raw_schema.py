"""Fix jd_raw table to match ORM model — add missing columns.

The live DB was created with an old jd_raw schema that lacks source_url,
raw_html, clean_text, job_title, company, salary_min, salary_max,
location, publish_date, simhash, error_msg. These columns are required
by the JdRaw ORM and dedup stage — fix the schema.

Revision ID: 042_fix_jd_raw_schema
Revises: 041_review_audit_log_action
Create Date: 2026-08-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "042_fix_jd_raw_schema"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("jd_raw")}

    # 1. 补全缺失的列（用 IF NOT EXISTS 幂等保护）
    if "source_url" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN source_url TEXT")
    if "raw_html" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN raw_html TEXT")
    if "clean_text" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN clean_text TEXT")
    if "job_title" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN job_title VARCHAR(200)")
    if "company" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN company VARCHAR(200)")
    if "salary_min" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN salary_min INTEGER")
    if "salary_max" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN salary_max INTEGER")
    if "location" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN location VARCHAR(200)")
    if "publish_date" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN publish_date DATE")
    if "simhash" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN simhash BIGINT")
    if "error_msg" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN error_msg TEXT")
    if "content_hash" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN content_hash CHAR(64)")
    if "extracted_at" not in cols:
        op.execute("ALTER TABLE jd_raw ADD COLUMN extracted_at TIMESTAMP")

    # 2. source_url UNIQUE 约束（ORM 声明 unique=True）
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'jd_raw_source_url_key'
            ) THEN
                ALTER TABLE jd_raw ADD CONSTRAINT jd_raw_source_url_key UNIQUE (source_url);
            END IF;
        END$$;
    """)

    # 3. simhash 索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_jd_raw_simhash ON jd_raw (simhash);
    """)

    # 4. 修 status enum 名称（如果旧 schema 用了 'jd_status_enum'）
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'jdstatus') THEN
                ALTER TYPE jdstatus RENAME TO jd_status;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # 不再回滚（生产已有数据；需手动决策）
    pass
