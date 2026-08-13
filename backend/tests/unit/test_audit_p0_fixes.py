"""P0-AUDIT-FIX 根因单测 (2026-08-13 代码审计 · 审计项 4.2)。

覆盖三个此前无单测、审计后才修复的分支：
- RateLimitMiddleware Redis 故障兜底 → 内存限流仍生效（死键/永久封禁防护）
- execute_pipeline_stage retries 耗尽 → 显式 _mark_stage_failed（stage 不再永久 running）
- _sweep_orphan_runs_async naive started_at → 不抛 TypeError，正确标记孤儿
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import settings


class TestRateLimitRedisFallback:
    """审计 2.2/2.3: Redis 故障时兜底内存限流；阈值读 settings 非硬编码。"""

    def test_redis_down_falls_back_to_in_memory_limiter(self, monkeypatch):
        from app.main import _rate_buckets, app

        monkeypatch.setattr(settings, "rate_limit_max", 3)
        monkeypatch.setattr(settings, "rate_limit_window", 60)

        class FakeRedis:
            async def eval(self, *args: Any, **kwargs: Any) -> int:
                raise ConnectionError("redis down")

        class FakeResources:
            redis_client = FakeRedis()  # 非 None → 走 Redis 分支 → eval 抛错 → 兜底内存

        with TestClient(app) as client:
            # lifespan 启动后才替换 resources，避免被真实 init_resources 覆盖
            monkeypatch.setattr(app.state, "resources", FakeResources())

            for _ in range(3):
                assert client.get("/api/v1/__rl_probe__").status_code == 404
            # 第 4 个请求应被内存限流拦截（阈值 3）
            assert client.get("/api/v1/__rl_probe__").status_code == 429

        assert _rate_buckets  # 内存桶被使用过（兜底路径真实生效）


class TestExecutePipelineStageRetriesExhausted:
    """审计 2.1: retries 耗尽必须显式标记 stage failed，而非静默卡 running。"""

    def test_marks_stage_failed_when_retries_exhausted(self, monkeypatch):
        from types import MethodType

        from app.tasks import celery_app as ca

        run_id = "11111111-1111-1111-1111-111111111111"

        def boom(run_id: str, run_type: str = "full") -> dict[str, Any]:
            raise ValueError("boom")

        # STAGE_EXECUTORS 在任务函数内 `from ...executor import STAGE_EXECUTORS`，
        # 故 patch 源模块而非 celery_app 上的引用
        import app.core.pipeline.executor as executor_mod

        monkeypatch.setitem(executor_mod.STAGE_EXECUTORS, "crawl", boom)

        dispatched: list[Any] = []

        def fake_run_async(coro: Any) -> None:
            dispatched.append(coro)

        monkeypatch.setattr(ca, "run_async", fake_run_async)

        class FakeRequest:
            retries: int = settings.pipeline_retry_max

        class FakeTask:
            request = FakeRequest()

        # .run 是 Celery Task 包装的已绑定方法（self=task 实例）——取 __func__
        # 解绑后用 MethodType 注入假 self，直接调用原始函数体
        raw_fn = ca.execute_pipeline_stage.run.__func__
        result = MethodType(raw_fn, FakeTask())(run_id, "crawl")

        assert result["status"] == "failed"
        assert result["exhausted"] is True
        assert result["stage"] == "crawl"
        # STOP 检查也经 run_async 分发 is_run_cancelled，故按协程名过滤
        mark_dispatched = [
            c for c in dispatched if hasattr(c, "cr_code") and c.cr_code.co_name == "_mark_stage_failed"
        ]
        assert len(mark_dispatched) == 1  # _mark_stage_failed 被分发，stage 不再卡 running

    def test_below_max_retries_raises_retry(self, monkeypatch):
        from types import MethodType

        from app.tasks import celery_app as ca

        run_id = "22222222-2222-2222-2222-222222222222"

        def boom(run_id: str, run_type: str = "full") -> dict[str, Any]:
            raise ValueError("boom")

        import app.core.pipeline.executor as executor_mod

        monkeypatch.setitem(executor_mod.STAGE_EXECUTORS, "extract", boom)

        dispatched: list[Any] = []

        def fake_run_async(coro: Any) -> None:
            dispatched.append(coro)

        monkeypatch.setattr(ca, "run_async", fake_run_async)

        class FakeRequest:
            retries: int = settings.pipeline_retry_max - 1

        class FakeTask:
            request = FakeRequest()

            def retry(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError("Celery retry scheduled")

        raw_fn = ca.execute_pipeline_stage.run.__func__
        with pytest.raises(RuntimeError, match="Celery retry scheduled"):
            MethodType(raw_fn, FakeTask())(run_id, "extract")

        # 未耗尽 → 不标记 failed，只走 retry（无 _mark_stage_failed 分发）
        mark_dispatched = [
            c for c in dispatched if hasattr(c, "cr_code") and c.cr_code.co_name == "_mark_stage_failed"
        ]
        assert mark_dispatched == []


class TestSweepOrphanRunsTimezone:
    """审计 2.4: naive started_at 不抛 TypeError，且按阈值正确判定孤儿。

    注：测试库 PG 会话时区为 +08:00，naive datetime 写入 timestamptz 会被当作
    本地时间转 UTC（偏移 8h），故集成部分用 aware UTC 行（与生产写入路径一致），
    naive 分支用 fake session 直测（覆盖审计的 TypeError 场景）。
    """

    async def test_aware_utc_rows_orphan_only_when_stale(self, db_session, monkeypatch):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.models.pipeline_models import PipelineRun

        threshold_seconds = settings.pipeline_stage_timeout * 2
        now0 = datetime.now(UTC)
        old = now0 - timedelta(seconds=threshold_seconds + 60)
        fresh = now0 - timedelta(seconds=60)

        orphan_id = uuid.uuid4()
        fresh_id = uuid.uuid4()
        db_session.add_all([
            PipelineRun(id=orphan_id, run_type="full", status="running", started_at=old),
            PipelineRun(id=fresh_id, run_type="full", status="running", started_at=fresh),
        ])
        await db_session.commit()

        # _sweep_orphan_runs_async 内部 `from app.db.session import get_session_factory`
        # 局部导入 —— patch 源模块属性即可注入同引擎的新 sessionmaker
        sm = async_sessionmaker(db_session.bind, expire_on_commit=False)

        def fake_factory() -> Any:
            return sm

        monkeypatch.setattr("app.db.session.get_session_factory", fake_factory)

        from app.tasks.celery_app import _sweep_orphan_runs_async

        result = await _sweep_orphan_runs_async()
        assert result["orphans_found"] >= 1

        from sqlalchemy import select

        # identity map 中的种子对象未过期（expire_on_commit=False），SELECT 会
        # 命中缓存返回 stale 行——用 populate_existing 强制从 PG 重读
        orphan_row = (await db_session.execute(
            select(PipelineRun)
            .where(PipelineRun.id == orphan_id)
            .execution_options(populate_existing=True)
        )).scalar_one()
        assert orphan_row.status == "failed"
        assert orphan_row.error_log == "orphaned by watchdog"

        fresh_row = (await db_session.execute(
            select(PipelineRun)
            .where(PipelineRun.id == fresh_id)
            .execution_options(populate_existing=True)
        )).scalar_one()
        assert fresh_row.status == "running"

        # 清理种子数据
        await db_session.execute(
            PipelineRun.__table__.delete().where(PipelineRun.id.in_([orphan_id, fresh_id]))
        )
        await db_session.commit()

    async def test_naive_started_at_does_not_raise(self, monkeypatch):
        """naive started_at 行（SQLite/历史数据场景）不抛 TypeError 且被正确清理。"""
        from app.core.pipeline.orchestrator import RunStatus
        from app.tasks.celery_app import _sweep_orphan_runs_async

        naive_old = (datetime.now(UTC) - timedelta(seconds=settings.pipeline_stage_timeout * 2 + 60)).replace(tzinfo=None)
        captured_run: dict[str, Any] = {}

        class FakeResult:
            def scalars(self) -> FakeResult:
                return self

            def all(self) -> list[Any]:
                return [captured_run["run"]]

        class FakeSession:
            async def __aenter__(self) -> FakeSession:
                return self

            async def __aexit__(self, *args: Any) -> bool:
                return False

            async def execute(self, stmt: Any) -> FakeResult:
                return FakeResult()

            async def commit(self) -> None:
                captured_run["committed"] = True

        class FakeFactory:
            def __call__(self) -> FakeSession:
                return FakeSession()

        run = type("Run", (), {"started_at": naive_old, "status": "running", "id": uuid.uuid4()})()
        captured_run["run"] = run

        # get_session_factory() 必须返回可调用对象（真实实现返回 async_sessionmaker），
        # 调用它得到 async 上下文管理器 session
        monkeypatch.setattr("app.db.session.get_session_factory", lambda: FakeFactory())

        result = await _sweep_orphan_runs_async()

        assert result["orphans_found"] == 1
        assert run.status == RunStatus.FAILED.value  # 被标记 failed
        assert captured_run.get("committed") is True
