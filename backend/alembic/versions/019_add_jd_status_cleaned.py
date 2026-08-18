"""add cleaned to jd_status enum

Phase 3 Plan 02: clean 阶段完成后标记 status=cleaned，
import 阶段改读 cleaned 而非 raw，实现阶段间数据流隔离。

Revision ID: 019
Revises: 018
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 2026-08-18 fix: jd_raw 表 + jd_status 枚举由 crawler init_schema 运行时
    # 创建（Base.metadata.create_all），不在 alembic 迁移链内。bootstrap/alembic
    # 阶段 crawler 未启动 → jd_raw/jd_status 不存在 → 020-038 全部失败。
    # 修复：在此处一次性创建 jd_raw 表 + jd_status 枚举（全部幂等）。
    conn = op.get_bind()

    # 1. 创建 jd_status 枚举类型（IF NOT EXISTS via DO block）
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE jd_status AS ENUM ('raw','cleaned','extracted','duplicate','failed');"
        " EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    ))
    conn.execute(sa.text("ALTER TYPE jd_status ADD VALUE IF NOT EXISTS 'cleaned'"))

    # 2. 创建 jd_raw 表（CREATE TABLE IF NOT EXISTS + IF NOT EXISTS indexes）
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS jd_raw (
            id BIGSERIAL PRIMARY KEY,
            source_site VARCHAR(32) NOT NULL,
            source_url TEXT NOT NULL,
            raw_html TEXT,
            clean_text TEXT NOT NULL,
            job_title VARCHAR(200) NOT NULL,
            company VARCHAR(200),
            salary_min INTEGER,
            salary_max INTEGER,
            location VARCHAR(100),
            publish_date DATE,
            crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            content_hash CHAR(64) NOT NULL,
            simhash BIGINT,
            status jd_status NOT NULL DEFAULT 'raw',
            error_msg TEXT
        )
    """))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS idx_jd_raw_source_url_unique ON jd_raw (source_url)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jd_raw_status ON jd_raw (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jd_raw_source_site ON jd_raw (source_site)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jd_raw_crawled_at ON jd_raw (crawled_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jd_raw_content_hash ON jd_raw (content_hash)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_jd_raw_simhash ON jd_raw (simhash)"))


def downgrade() -> None:
    # PostgreSQL 无法删除枚举值，downgrade 仅注释说明
    pass
