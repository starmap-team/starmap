"""Seed daily_reconcile schedule row (Phase 23 Task 4, DC-01/IS-03).

`pipeline_schedules` 此前没有任何 `daily_reconcile` 种子行 → cron_scanner 的
`scan_due_schedules`（`next_run_at <= now` 过滤）永远不会选中该行，Celery 的
`reconcile_graph_task` 永不派发，每日自动对账（DC-01）落空。

039 是**纯数据迁移**（不改表结构，`pipeline_schedules` 结构停留在 007）：
- `WHERE NOT EXISTS` 幂等守卫——`pipeline_schedules.name` 无唯一约束（007:31），
  不能用 `ON CONFLICT (name)`（034 的 data_sources.name 有 unique 才可用）。
- `next_run_at` 用 SQL 计算**下个 03:00 UTC**——BLOCKER 修复：`scan_due_schedules`
  过滤 `next_run_at <= now`，NULL 永不满足 → 种子行必须写非 NULL next_run_at，
  否则 reconcile_graph_task 永不触发（cron_scheduler.py:146-154）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "039"
down_revision: tuple[str, ...] = ("038",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. INSERT（fresh 环境）——WHERE NOT EXISTS 幂等守卫：
    #    `pipeline_schedules.name` 无唯一约束（007:31），不能用 ON CONFLICT (name)。
    op.execute(
        sa.text(
            """
            INSERT INTO pipeline_schedules
                (id, name, cron_expression, run_type, enabled, selected_stages, next_run_at)
            SELECT gen_random_uuid(), 'daily_reconcile', '0 3 * * *', 'manual', true, NULL,
                   -- 下个 03:00 UTC: 若已过今日 03:00 则取明日，否则取今日
                   date_trunc('day', now() AT TIME ZONE 'UTC')
                     + CASE WHEN (now() AT TIME ZONE 'UTC')::time >= '03:00:00'
                            THEN interval '1 day' ELSE interval '0 day' END
                     + interval '3 hours'
            WHERE NOT EXISTS (SELECT 1 FROM pipeline_schedules WHERE name = 'daily_reconcile')
            """
        )
    )
    # 2. HEAL 既有行（BLOCKER 修复）：dev/历史环境可能存在手动创建或损坏的
    #    daily_reconcile 行（enabled=false / next_run_at 过期 / run_type 错误）——
    #    scan_due_schedules 过滤 `enabled==True AND next_run_at <= now`，损坏行永不
    #    触发。此处统一修正为 enabled=true + 下个 03:00 UTC（对步骤 1 新插入的行
    #    重算同值，幂等安全）。
    op.execute(
        sa.text(
            """
            UPDATE pipeline_schedules
            SET enabled = true,
                run_type = 'manual',
                cron_expression = '0 3 * * *',
                next_run_at = date_trunc('day', now() AT TIME ZONE 'UTC')
                               + CASE WHEN (now() AT TIME ZONE 'UTC')::time >= '03:00:00'
                                      THEN interval '1 day' ELSE interval '0 day' END
                               + interval '3 hours'
            WHERE name = 'daily_reconcile'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM pipeline_schedules WHERE name = 'daily_reconcile'")
    )
