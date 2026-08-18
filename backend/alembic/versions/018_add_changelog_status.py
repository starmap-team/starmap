"""Add status column to evolution_changelog (reapply — 004 was never executed).

Revision ID: 018
Revises: 017
Create Date: 2026-07-23
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 2026-08-18 fix: 用原始 SQL 保证完全幂等——004a 可能已执行过，重复
    # add_column 会污染事务状态导致后续 UPDATE alembic_version 失败。原始 SQL
    # 在 PG 事务中安全：若列/索引已存在，IF NOT EXISTS 直接跳过。
    conn = op.get_bind()
    conn.execute(
        sa.text("ALTER TABLE evolution_changelog ADD COLUMN IF NOT EXISTS "
                "status VARCHAR(20) NOT NULL DEFAULT 'pending'")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_evolution_changelog_status_trust "
                "ON evolution_changelog (status, trust_score)")
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DROP INDEX IF EXISTS ix_evolution_changelog_status_trust")
    )
    conn.execute(
        sa.text("ALTER TABLE evolution_changelog DROP COLUMN IF EXISTS status")
    )


def downgrade() -> None:
    op.drop_index("ix_evolution_changelog_status_trust", table_name="evolution_changelog")
    op.drop_column("evolution_changelog", "status")
