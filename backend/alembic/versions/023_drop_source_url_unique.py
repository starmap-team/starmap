"""Drop source_url UNIQUE constraint, keep content_hash UNIQUE (Phase 15-02).

Phase 15-02: 改用 content_hash 作为 dedup key。
- 添加 content_hash UNIQUE 索引 (迁移 022)
- 删除 source_url UNIQUE 约束 (本迁移)

因为 CSV 导入的 source_url 经常为空，source_url UNIQUE 会导致
所有空 source_url 的条目互相冲突，无法入库。

Revision ID: 023
Revises: 022
"""
from __future__ import annotations

from alembic import op

revision: str = "023"
down_revision: str | None = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jd_raw DROP CONSTRAINT IF EXISTS jd_raw_source_url_key")


def downgrade() -> None:
    # Downgrade: 重建 unique on source_url (注: 已有空 source_url 会冲突)
    op.execute(
        """
        UPDATE jd_raw SET source_url = 'http://legacy/' || id::text
        WHERE source_url = '' OR source_url IS NULL
        """
    )
    op.execute("ALTER TABLE jd_raw ADD CONSTRAINT jd_raw_source_url_key UNIQUE (source_url)")