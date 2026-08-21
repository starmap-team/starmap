"""Regression test for watchdog timezone-aware comparisons.

CONCERN 2.2 (reliability audit 2026-08-15): P0-AUDIT-FIX (2026-08-13) added
naive/aware handling at one site (orchestrator.py:340-346, celery_app.py:355-361).
Without that normalization, comparing a naive ``datetime.utcnow()`` against the
``DateTime(timezone=True)`` ``threshold`` would raise ``TypeError: can't compare
offset-naive and offset-aware datetimes``.

This test seeds a ``PipelineRun`` whose ``started_at`` is naive (the historical
shape) and asserts the watchdog sweep completes without raising.

Comparison sites exercised:
- backend/app/tasks/celery_app.py:361 - ``started_at < threshold``
- backend/app/core/pipeline/orchestrator.py:345-346 - same naive normalization
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings


class _FakeScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return self

    def all(self) -> list:
        return self._rows


class _FakeRun:
    """Minimal stand-in for an ORM ``PipelineRun`` row."""

    def __init__(self, started_at: datetime) -> None:
        self.id = "00000000-0000-0000-0000-000000000001"
        self.started_at = started_at
        self.status = "running"
        self.completed_at = None
        self.error_log = None
        # 2026-08-21: watchdog stage-sync 会遍历 stages —— fake 必须提供该属性
        self.stages = [
            {"name": "import", "status": "running", "completed_at": None, "errors": []},
        ]


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)

    async def commit(self) -> None:
        return None


def _build_factory(rows: list) -> MagicMock:
    """Build a ``get_session_factory`` mock returning a session with the given rows.

    The factory must be callable and return an async-context-manager that
    yields a session (mirrors ``async_sessionmaker()`` usage at
    ``celery_app.py:348``: ``sm = get_session_factory(); async with sm() as session``).
    """
    session = _FakeSession(rows=rows)
    # The factory's callable ``()`` returns the context-manager directly.
    ctx_manager = MagicMock()
    ctx_manager.__aenter__ = _async_return(session)
    ctx_manager.__aexit__ = _async_return(None)

    factory = MagicMock(return_value=ctx_manager)
    return factory


def _async_return(value: object):
    async def _coro(*_args: object, **_kwargs: object) -> object:
        return value

    return _coro


@pytest.mark.asyncio
async def test_watchdog_does_not_raise_on_naive_started_at():
    """Sweep must NOT raise ``TypeError`` when ``started_at`` is naive.

    CONCERN 2.2: regression guard for ``celery_app.py:361`` comparison
    ``started_at < threshold`` where threshold is timezone-aware and
    ``started_at`` is naive (legacy rows / SQLite test fixtures).
    """
    # Naive datetime - the legacy shape before the timezone normalization fix.
    naive_started_at = datetime.utcnow() - timedelta(
        seconds=settings.pipeline_stage_timeout * 3
    )
    run = _FakeRun(started_at=naive_started_at)

    factory = _build_factory([run])

    with patch("app.db.session.get_session_factory", return_value=factory):
        from app.tasks.celery_app import _sweep_orphan_runs_async

        # The function under test must complete without raising a TypeError.
        result = await _sweep_orphan_runs_async()

    assert result["orphans_found"] == 1
    assert run.status == "failed"
    assert run.error_log == "orphaned by watchdog"


@pytest.mark.asyncio
async def test_watchdog_handles_aware_started_at():
    """Sweep must accept timezone-aware ``started_at`` rows (the post-fix shape)."""
    aware_started_at = datetime.now(UTC) - timedelta(
        seconds=settings.pipeline_stage_timeout * 3
    )
    run = _FakeRun(started_at=aware_started_at)

    factory = _build_factory([run])

    with patch("app.db.session.get_session_factory", return_value=factory):
        from app.tasks.celery_app import _sweep_orphan_runs_async

        result = await _sweep_orphan_runs_async()

    assert result["orphans_found"] == 1


@pytest.mark.asyncio
async def test_watchdog_skips_recent_runs():
    """Sweep must NOT orphan a recent (within stage_timeout*2) running run."""
    fresh_started_at = datetime.now(UTC) - timedelta(seconds=10)
    run = _FakeRun(started_at=fresh_started_at)

    factory = _build_factory([run])

    with patch("app.db.session.get_session_factory", return_value=factory):
        from app.tasks.celery_app import _sweep_orphan_runs_async

        result = await _sweep_orphan_runs_async()

    assert result["orphans_found"] == 0
    assert run.status == "running"
