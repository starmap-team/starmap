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
    op.add_column(
        "jd_raw",
        sa.Column("simhash", sa.BigInteger, nullable=True),
    )
    # 近似去重查询路径是 get_existing_hashes → 大表上线性扫描。
    # 为按 simhash 精确匹配先建索引，后续若再近一步的"小于阈值扫描"再视负载评估。
    op.create_index(
        "ix_jd_raw_simhash",
        "jd_raw",
        ["simhash"],
    )


def downgrade() -> None:
    op.drop_index("ix_jd_raw_simhash", table_name="jd_raw")
    op.drop_column("jd_raw", "simhash")
