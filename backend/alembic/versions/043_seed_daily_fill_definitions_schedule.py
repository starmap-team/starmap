"""Seed daily_fill_definitions schedule row (A3 可持续闭环 ④).

`pipeline_schedules` 需注册 `daily_fill_definitions` 行，cron_scanner 才会在
每日 04:00 UTC 派发 `daily_fill_missing_definitions_task`——扫描 approved 且
五要素为空的岗位（含图外）自动 LLM 补齐（成本护栏 200/日，多日自然收敛）。

与 039 同模式：纯数据迁移 + WHERE NOT EXISTS 幂等守卫 + HEAL 损坏行。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "043"
down_revision: tuple[str, ...] = ("042",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. INSERT（fresh 环境）——幂等守卫（name 无唯一约束，不能 ON CONFLICT）
    op.execute(
        sa.text(
            """
            INSERT INTO pipeline_schedules
                (id, name, cron_expression, run_type, enabled, selected_stages, next_run_at)
            SELECT gen_random_uuid(), 'daily_fill_definitions', '0 4 * * *', 'manual', true, NULL,
                   -- 下个 04:00 UTC
                   date_trunc('day', now() AT TIME ZONE 'UTC')
                     + CASE WHEN (now() AT TIME ZONE 'UTC')::time >= '04:00:00'
                            THEN interval '1 day' ELSE interval '0 day' END
                     + interval '4 hours'
            WHERE NOT EXISTS (SELECT 1 FROM pipeline_schedules WHERE name = 'daily_fill_definitions')
            """
        )
    )
    # 2. HEAL 既有行（enabled/next_run_at 损坏修复，幂等安全）
    op.execute(
        sa.text(
            """
            UPDATE pipeline_schedules
            SET enabled = true,
                run_type = 'manual',
                cron_expression = '0 4 * * *',
                next_run_at = date_trunc('day', now() AT TIME ZONE 'UTC')
                               + CASE WHEN (now() AT TIME ZONE 'UTC')::time >= '04:00:00'
                                      THEN interval '1 day' ELSE interval '0 day' END
                               + interval '4 hours'
            WHERE name = 'daily_fill_definitions'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM pipeline_schedules WHERE name = 'daily_fill_definitions'")
    )
