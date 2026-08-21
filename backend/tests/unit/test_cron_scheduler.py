"""Tests for pipeline cron scheduler."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.cron_scheduler import (
    compute_next_cron,
    cron_scanner_once,
    scan_due_schedules,
    trigger_schedule,
)

# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------

class FakeScalarsResult:
    def __init__(self, items: list):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    def __init__(self, scalars_list=None):
        self._scalars = FakeScalarsResult(scalars_list) if scalars_list is not None else FakeScalarsResult([])

    def scalars(self):
        return self._scalars

    def scalar(self):
        rows = self._scalars.all()
        return rows[0] if rows else None


class FakeAsyncSession:
    def __init__(self, results: list | None = None):
        self._results = results or []
        self._idx = 0

    async def execute(self, stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult()

    async def flush(self):
        pass

    async def commit(self):
        pass


def _make_schedule(
    name: str = "test-schedule",
    cron_expression: str = "0 */6 * * *",
    enabled: bool = True,
    next_run_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="sched-001",
        name=name,
        cron_expression=cron_expression,
        enabled=enabled,
        next_run_at=next_run_at or datetime.now(UTC) - timedelta(minutes=5),
        last_run_at=None,
    )


# ---------------------------------------------------------------------------
# compute_next_cron
# ---------------------------------------------------------------------------
class TestComputeNextCron:
    def test_valid_cron_expression(self):
        result = compute_next_cron("0 */6 * * *")
        assert result is not None
        assert isinstance(result, datetime)

    def test_valid_cron_with_croniter_available(self):
        """When croniter is installed, it parses real cron expressions."""
        mock_croniter_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.get_next.return_value = datetime(2025, 6, 1, 18, 0, tzinfo=UTC)
        mock_croniter_cls.return_value = mock_instance

        with patch("app.core.pipeline.cron_scheduler.HAS_CRONITER", True), \
             patch("app.core.pipeline.cron_scheduler.croniter", mock_croniter_cls, create=True):
            result = compute_next_cron("0 */6 * * *")
        assert result is not None

    def test_croniter_value_error(self):
        """croniter raises ValueError on bad expression."""
        mock_croniter_cls = MagicMock()
        mock_croniter_cls.side_effect = ValueError("bad cron")

        with patch("app.core.pipeline.cron_scheduler.HAS_CRONITER", True), \
             patch("app.core.pipeline.cron_scheduler.croniter", mock_croniter_cls, create=True):
            result = compute_next_cron("bad")
        assert result is None

    def test_custom_base_time(self):
        base = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
        result = compute_next_cron("0 14 * * *", base=base)
        assert result is not None
        assert result > base  # next run is in the future

    def test_invalid_cron_returns_none(self):
        result = compute_next_cron("not a cron")
        assert result is None

    def test_fallback_without_croniter(self):
        with patch("app.core.pipeline.cron_scheduler.HAS_CRONITER", False):
            result = compute_next_cron("0 */6 * * *")
            # Fallback returns base + 1 hour
            assert result is not None

    def test_fallback_invalid_parts(self):
        with patch("app.core.pipeline.cron_scheduler.HAS_CRONITER", False):
            result = compute_next_cron("0 */6 * *")
            # Not 5 parts → None
            assert result is None

    def test_fallback_exception(self):
        with patch("app.core.pipeline.cron_scheduler.HAS_CRONITER", False):
            # Pass something that causes an exception in fallback parsing
            result = compute_next_cron(None)  # type: ignore
            assert result is None


# ---------------------------------------------------------------------------
# scan_due_schedules
# ---------------------------------------------------------------------------
class TestScanDueSchedules:
    @pytest.mark.asyncio
    async def test_returns_due_schedules(self):
        sched = _make_schedule()
        session = FakeAsyncSession([FakeResult(scalars_list=[sched])])
        result = await scan_due_schedules(session)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_due_schedules(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        result = await scan_due_schedules(session)
        assert result == []


# ---------------------------------------------------------------------------
# trigger_schedule
# ---------------------------------------------------------------------------
class TestTriggerSchedule:
    @pytest.mark.asyncio
    async def test_successful_trigger(self):
        sched = _make_schedule()
        session = FakeAsyncSession()
        with patch("app.core.pipeline.cron_scheduler.compute_next_cron", return_value=datetime.now(UTC) + timedelta(hours=6)):
            with patch("app.tasks.celery_app.scheduled_pipeline_run") as mock_task:
                result = await trigger_schedule(session, sched)
        assert result is True
        assert sched.last_run_at is not None
        assert sched.next_run_at is not None
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_failure_returns_false(self):
        sched = _make_schedule()
        session = FakeAsyncSession()
        with patch("app.tasks.celery_app.scheduled_pipeline_run") as mock_task:
            mock_task.delay.side_effect = Exception("celery down")
            result = await trigger_schedule(session, sched)
        assert result is False

    @pytest.mark.asyncio
    async def test_daily_reconcile_dispatches_reconcile_graph_task(self):
        """Phase 23 Task 4 (DC-01): daily_reconcile name 分发到 reconcile_graph_task.delay。

        迁移 039 种子行 name='daily_reconcile' → trigger_schedule 按 name 派发
        `reconcile_graph_task`（而非 scheduled_pipeline_run）→ 每日自动全量对账。
        """
        sched = _make_schedule(name="daily_reconcile")
        session = FakeAsyncSession()
        with patch("app.core.pipeline.cron_scheduler.compute_next_cron", return_value=datetime.now(UTC) + timedelta(hours=6)):
            with patch("app.tasks.celery_app.reconcile_graph_task") as mock_task:
                result = await trigger_schedule(session, sched)
        assert result is True
        mock_task.delay.assert_called_once_with(str(sched.id))
        assert sched.last_run_at is not None
        assert sched.next_run_at is not None

    @pytest.mark.asyncio
    async def test_graph_reconcile_dispatches_reconcile_graph_task(self):
        """graph_reconcile 别名同样分发 reconcile_graph_task（name 白名单）。"""
        sched = _make_schedule(name="graph_reconcile")
        session = FakeAsyncSession()
        with patch("app.core.pipeline.cron_scheduler.compute_next_cron", return_value=datetime.now(UTC) + timedelta(hours=6)):
            with patch("app.tasks.celery_app.reconcile_graph_task") as mock_task:
                result = await trigger_schedule(session, sched)
        assert result is True
        mock_task.delay.assert_called_once_with(str(sched.id))

    @pytest.mark.asyncio
    async def test_trigger_with_no_next_cron_fallback(self):
        sched = _make_schedule(cron_expression="invalid")
        session = FakeAsyncSession()
        with patch("app.core.pipeline.cron_scheduler.compute_next_cron", return_value=None):
            with patch("app.tasks.celery_app.scheduled_pipeline_run"):
                result = await trigger_schedule(session, sched)
        assert result is True
        # next_run_at should be last_run_at + 1 hour
        assert sched.next_run_at is not None
        expected = sched.last_run_at + timedelta(hours=1)
        assert abs((sched.next_run_at - expected).total_seconds()) < 2


# ---------------------------------------------------------------------------
# cron_scanner_once
# ---------------------------------------------------------------------------
class TestCronScannerOnce:
    @pytest.mark.asyncio
    async def test_triggers_due_schedules(self):
        sched = _make_schedule()
        session = FakeAsyncSession([FakeResult(scalars_list=[sched])])
        with patch("app.core.pipeline.cron_scheduler.trigger_schedule", AsyncMock(return_value=True)):
            count = await cron_scanner_once(session)
        assert count == 1

    @pytest.mark.asyncio
    async def test_no_due_schedules(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        count = await cron_scanner_once(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        sched1 = _make_schedule(name="ok")
        sched2 = _make_schedule(name="fail")

        async def fake_trigger(session, schedule):
            return schedule.name == "ok"

        session = FakeAsyncSession([FakeResult(scalars_list=[sched1, sched2])])
        with patch("app.core.pipeline.cron_scheduler.trigger_schedule", fake_trigger):
            count = await cron_scanner_once(session)
        assert count == 1
