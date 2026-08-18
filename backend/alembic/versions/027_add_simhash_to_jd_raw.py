"""Add simhash column to jd_raw for near-duplicate detection (NEW-06 / PLAN-006③ / PLAN-009).

NEW-06 content_hash 决策：拆列方案 — content_hash 继续守精确去重（UNIQUE），新增
simhash 列（BIGINT, nullable）存 64-bit SimHash 指纹供 get_existing_hashes 近似去重。
旧记录 simhash 留 NULL（不再参与近似去重，但精确去重不受影响；新记录由
apify / incremental / m1_seed 写入 simhash）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 2026-08-18 fix: 019 已创建 jd_raw 表含 simhash 列+索引。
    # 用原始 SQL 保证完全幂等——alembic op.create_index 在 PG 事务中
    # 即使被 try/except 捕获，事务也会标记为 FAILED → UPDATE alembic_version
    # 报 InFailedSQLTransactionError。原始 SQL + IF NOT EXISTS 无此问题。
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_jd_raw_simhash ON jd_raw (simhash)"
    ))


def downgrade() -> None:
    op.drop_index("ix_jd_raw_simhash", table_name="jd_raw")
    op.drop_column("jd_raw", "simhash")
