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
    # 2026-08-18 fix: 019 已创建 jd_raw 表含 simhash 列+索引 →
    # add_column / create_index 可能因已存在而失败。
    # 幂等检查：列/索引已存在则跳过。
    conn = op.get_bind()
    simhash_exists = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns "
                "WHERE table_name='jd_raw' AND column_name='simhash'")
    ).scalar() is not None
    if not simhash_exists:
        op.add_column(
            "jd_raw",
            sa.Column("simhash", sa.BigInteger, nullable=True),
        )
    # 近似去重查询路径是 get_existing_hashes → 大表上线性扫描。
    # 为按 simhash 精确匹配先建索引，后续若再近一步的"小于阈值扫描"再视负载评估。
    try:
        op.create_index(
            "ix_jd_raw_simhash",
            "jd_raw",
            ["simhash"],
        )
    except Exception:
        pass  # Index already exists


def downgrade() -> None:
    op.drop_index("ix_jd_raw_simhash", table_name="jd_raw")
    op.drop_column("jd_raw", "simhash")
