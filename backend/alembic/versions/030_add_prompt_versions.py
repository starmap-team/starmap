"""Add prompt_versions table (admin prompt version persistence, 2026-08-08).

此前 /admin/prompts 的版本注册/切换只写进程内存 dict（_PROMPT_VERSIONS/
_ACTIVE_VERSIONS），重启即丢。此表持久化自定义版本与活跃选择，
启动时合并进内存注册表（见 app.core.extraction.prompt.apply_custom_prompt_versions）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "030"
down_revision: tuple[str, str] = ("029",)  # 单链：029 已是最新
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_name", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("prompt_name", "version", name="uq_prompt_name_version"),
    )
    op.create_index("ix_prompt_versions_prompt_name", "prompt_versions", ["prompt_name"])


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_prompt_name", table_name="prompt_versions")
    op.drop_table("prompt_versions")
