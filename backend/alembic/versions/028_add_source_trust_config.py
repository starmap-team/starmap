"""Add source_trust_config table (§4.2 / PLAN-012 / DEV-14).

数据源信任度配置表 — §7.1 Authority 因子的按源配置载体。
与 data_sources 职责分离: 本表只存信任度分类 (official/platform/aggregator/social)。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "028"
down_revision: str | None = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_trust_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(100), nullable=False, unique=True),
        sa.Column("authority_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="aggregator"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_source_trust_config_source_name", "source_trust_config", ["source_name"])


def downgrade() -> None:
    op.drop_index("ix_source_trust_config_source_name", table_name="source_trust_config")
    op.drop_table("source_trust_config")
