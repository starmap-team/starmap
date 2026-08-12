"""Drop raw_jd_records dead table (D5, 2026-08-12).

raw_jd_records 是遗留死表：管线 crawl 经 dao.upsert_jd 写 jd_raw（status_aggregator
注释 "RawJDRecord 永不被写入"），该表仅剩测试/过期数据（D5 已清空 85 行）。
模型 RawJDRecord 已移除，dashboard_service 退化路径已改读 jd_raw。
本迁移删除空表，彻底消除"死表陷阱"（曾导致 valid_records 清零/累加污染）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "033"
down_revision: tuple[str, ...] = ("032",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("raw_jd_records")


def downgrade() -> None:
    # 反向迁移：重建空表（原 schema 见 002_add_extraction_tables.py）
    op.create_table(
        "raw_jd_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_platform", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("title_raw", sa.String(255)),
        sa.Column("company_name", sa.String(255)),
        sa.Column("crawl_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hash_dedup", sa.String(64), index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
