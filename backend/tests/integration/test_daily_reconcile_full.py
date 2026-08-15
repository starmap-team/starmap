"""Phase 23 Task 4 — 每日对账 cron 集成测试（DC-01/DC-03/IS-03）。

依赖真实 PostgreSQL（`db_session` fixture 在无 PG 时 skip）+ Neo4j（全量对账段在
Neo4j 不可用时 skip）。

断言：
- 迁移 039 种子行存在（daily_reconcile / enabled / next_run_at 非 NULL ≤ now+1day）
- next_run_at 到期时 scan_due_schedules 能选中该行（BLOCKER：可触发）
- _run_daily_reconcile 全量对账写 audit_events（detail 含 requires_diff/边 diff）
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _reset_async_engine() -> object:
    """每个测试后用独立事件循环重建 engine。

    get_async_engine 是 lru_cache 单例——pytest-asyncio 每测试一个新 loop，跨测试复用
    旧 engine 会报 "NoneType' object has no attribute 'send'"（engine 绑定到已关闭 loop）。
    """
    yield
    from app.db.session import get_async_engine, get_session_factory

    get_async_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.mark.integration
class TestDailyReconcileSeedRow:
    """迁移 039 种子行 + scan_due_schedules 可触发（BLOCKER 修复）。"""

    async def test_seed_row_exists_with_non_null_next_run_at(self, db_session) -> None:
        rows = (
            await db_session.execute(
                text(
                    "SELECT name, enabled, next_run_at FROM pipeline_schedules "
                    "WHERE name = 'daily_reconcile'"
                )
            )
        ).all()
        assert rows, "daily_reconcile 种子行必须存在（迁移 039）"
        for row in rows:
            assert row.enabled is True, "种子行必须 enabled=True（否则 scan_due_schedules 跳过）"
            assert row.next_run_at is not None, (
                "next_run_at IS NULL → scan_due_schedules（next_run_at <= now）永不选中 (BLOCKER)"
            )
            assert row.next_run_at <= datetime.now(UTC) + timedelta(days=1), (
                "next_run_at 必须 <= now + 1day（下个 03:00 UTC）"
            )

    async def test_scan_due_schedules_picks_due_reconcile(self, db_session) -> None:
        from app.core.pipeline.cron_scheduler import scan_due_schedules

        sched_id = (
            await db_session.execute(
                text("SELECT id FROM pipeline_schedules WHERE name = 'daily_reconcile' LIMIT 1")
            )
        ).scalar_one_or_none()
        if sched_id is None:
            pytest.skip("daily_reconcile 种子行缺失")
        # 模拟到期：next_run_at 置为过去 → scan 应能选中（enabled=True）
        await db_session.execute(
            text("UPDATE pipeline_schedules SET next_run_at = NOW() - interval '1 hour' WHERE id = :id"),
            {"id": sched_id},
        )
        await db_session.commit()
        try:
            due = await scan_due_schedules(db_session)
            assert any(str(getattr(x, "id", "")) == str(sched_id) for x in due), (
                "next_run_at 到期后 scan_due_schedules 必须选中 daily_reconcile"
            )
        finally:
            # 恢复（不污染调度状态）
            await db_session.execute(
                text("UPDATE pipeline_schedules SET next_run_at = NOW() + interval '1 day' WHERE id = :id"),
                {"id": sched_id},
            )
            await db_session.commit()


@pytest.mark.integration
class TestDailyReconcileFull:
    """_run_daily_reconcile 全量对账写 audit_events（detail 含边 diff）。"""

    async def test_full_reconcile_writes_audit_with_edge_diff(self, db_session) -> None:
        from app.core.pipeline.cron_scheduler import _run_daily_reconcile
        from app.services.resources import init_resources

        resources = await init_resources()
        if not resources.neo4j_driver:
            pytest.skip("Neo4j 不可用，跳过全量对账测试")

        await _run_daily_reconcile(db_session)

        detail = (
            await db_session.execute(
                text(
                    "SELECT detail FROM audit_events "
                    "WHERE actor = 'cron_scanner' AND action = 'daily_reconcile' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            )
        ).scalar_one_or_none()
        assert detail is not None, "daily_reconcile 必须写 audit_events"
        # DC-03：audit detail 含节点 + 边 diff
        assert "requires_neo4j=" in detail
        assert "requires_pg=" in detail
        assert "requires_diff=" in detail
        assert "orphans=" in detail
