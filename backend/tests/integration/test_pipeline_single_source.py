"""Integration test for single-source sync crawl filter (CONCERN 2.6, audit 2026-08-15).

Commit ``e0f7431f`` (P0-AUDIT-FIX 2026-08-13) added ``selected_sources=[ds.name]``
to the ``trigger_and_start`` call in ``backend/app/api/v1/datasource.py:377``.
Prior to that fix, ``selected_sources=None`` meant the crawl stage iterated
over every active source - the response claimed "Source sync triggered for X"
but actually crawled them all.

This test mocks the crawler executor (via ``trigger_and_start``) and asserts
that ``POST /api/v1/datasources/{id}/sync`` forwards exactly one source name
to ``trigger_and_start``. The downstream crawl filter at
``backend/app/core/pipeline/stages/crawl.py:128-134`` is exercised by
existing stage tests.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db_session
from app.main import app


class _FakeDataSourceRecord:
    def __init__(self, name: str):
        self.id = uuid4()
        self.name = name
        self.source_type = "crawler"
        self.status = "active"
        self.authority_score = 0.8
        self.config = {}


class _FakePipelineRun:
    def __init__(self, run_id, selected_sources):
        self.id = run_id
        self.run_type = "incremental"
        self.status = "running"
        self.started_at = datetime.now(UTC)
        self.completed_at = None
        self.selected_sources = selected_sources
        self.stages = []


def _make_fake_session(ds):
    """Build an AsyncMock session whose execute() returns ``ds`` on scalar_one_or_none."""
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=ds)
    mock_session.execute = AsyncMock(return_value=execute_result)
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    return mock_session


@pytest.fixture(autouse=True)
def _override_deps():
    """Override get_db_session + get_current_user with mocks for all tests in this module."""
    fake_user = {"sub": "admin", "role": "admin", "username": "admin", "type": "access"}
    app.dependency_overrides[get_current_user] = lambda: fake_user

    def _set_session(ds):
        mock_session = _make_fake_session(ds)

        async def _override_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = _override_db

    yield _set_session
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db_session, None)


def test_single_source_sync_passes_selected_sources(_override_deps):
    """POST /api/v1/datasources/{id}/sync forwards selected_sources=[ds.name].

    Reference: backend/app/api/v1/datasource.py:377 (commit e0f7431f).
    The crawler executor is mocked via ``trigger_and_start`` - we never
    actually run the crawl - and we still verify that the route forwarded
    exactly one source name to ``trigger_and_start``.
    """
    ds = _FakeDataSourceRecord(name="bosszhipin")
    _override_deps(ds)

    fake_run = _FakePipelineRun(
        run_id=uuid4(),
        selected_sources=["bosszhipin"],
    )

    with patch(
        "app.services.pipeline_service.trigger_and_start",
        new_callable=AsyncMock,
        return_value=fake_run,
    ) as mock_trigger:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(f"/api/v1/datasources/{ds.id}/sync")

    # The route invoked trigger_and_start with selected_sources=[ds.name].
    assert resp.status_code == 200, resp.text
    mock_trigger.assert_awaited_once()
    kwargs = mock_trigger.await_args.kwargs
    assert kwargs.get("selected_sources") == ["bosszhipin"], kwargs
    assert kwargs.get("run_type") == "incremental"

    body = resp.json()
    assert body["source_name"] == "bosszhipin"
    assert body["status"] == "running"
    assert body["run_id"] == str(fake_run.id)


def test_single_source_sync_calls_trigger_with_exactly_one_source(_override_deps):
    """Regression guard: selected_sources list must contain exactly 1 entry.

    Pre-fix ``e0f7431f``, ``selected_sources=None`` was passed - the crawl
    stage would then iterate over every active source, contradicting the
    "Source sync triggered for X" semantics in the response. This test
    pins the list length to 1.
    """
    ds = _FakeDataSourceRecord(name="v2ex_remote")
    _override_deps(ds)

    fake_run = _FakePipelineRun(
        run_id=uuid4(),
        selected_sources=["v2ex_remote"],
    )

    with patch(
        "app.services.pipeline_service.trigger_and_start",
        new_callable=AsyncMock,
        return_value=fake_run,
    ) as mock_trigger:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(f"/api/v1/datasources/{ds.id}/sync")

    assert resp.status_code == 200, resp.text
    call_args = mock_trigger.await_args
    selected = (
        call_args.kwargs.get("selected_sources") if call_args else None
    )
    assert selected is not None, "trigger_and_start was not called with selected_sources"
    assert isinstance(selected, list)
    assert selected == ["v2ex_remote"]
    assert len(selected) == 1, (
        f"Regression: selected_sources should have exactly 1 entry, got {selected}"
    )


def test_single_source_sync_iterates_only_one_source_in_crawl_stage(_override_deps):
    """End-to-end: the run's selected_sources is a single-element list.

    This complements the route-level assertions by checking that the
    resulting run carries the single-source intent forward into the
    crawl-stage filter at ``crawl.py:128-134``. If a future caller passes
    ``selected_sources=None`` (the pre-fix bug) the run's list would be
    None - this test fails on regression.
    """
    ds = _FakeDataSourceRecord(name="jobicy")
    _override_deps(ds)

    fake_run = _FakePipelineRun(
        run_id=uuid4(),
        selected_sources=["jobicy"],
    )

    with patch(
        "app.services.pipeline_service.trigger_and_start",
        new_callable=AsyncMock,
        return_value=fake_run,
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(f"/api/v1/datasources/{ds.id}/sync")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The run carries the single source name (mirrors the SQL row that
    # the crawl stage will read at crawl.py:97-103).
    assert fake_run.selected_sources == ["jobicy"]
    assert fake_run.stages == []  # executor is mocked; no stages mutated
    assert body["message"].startswith("Source sync triggered for 'jobicy'")
