"""Add UNIQUE constraint on jd_raw.content_hash (Phase 15-02).

之前 content_hash 只有 INDEX 没有 UNIQUE 约束，导致 dao.upsert_jd 无法用
ON CONFLICT (content_hash) DO NOTHING 去重。改用 content_hash 作为
去重 key 后必须有 UNIQUE 约束。

Revision ID: 022
Revises: 021
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 15-02: 让 content_hash 成为真正的去重 key
    op.execute("DROP INDEX IF EXISTS idx_jd_raw_content_hash")
    op.execute("CREATE UNIQUE INDEX uq_jd_raw_content_hash ON jd_raw(content_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_jd_raw_content_hash")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jd_raw_content_hash ON jd_raw(content_hash)")