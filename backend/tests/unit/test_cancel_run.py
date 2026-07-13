"""Unit tests for Phase 1 cancel_run feature.

Covers D-04, D-05, D-06:
- Cancel a running run -> status='cancelled'
- Cancel a completed run -> 409
- Cancel a non-existent run -> 404
- STOP flag is correctly set in Redis
- Cascade: stages[] with status='running' -> 'cancelled'
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.orchestrator import cancel_run, is_run_cancelled
from app.exceptions import RunAlreadyTerminalError, RunNotFoundError


@pytest.mark.asyncio
async def test_cancel_running_run_returns_cancelled_status():
    """Test D-04: cancelling a running run sets status='cancelled'."""
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.status = "running"
    mock_run.completed_at = None
    mock_run.error_log = None
    mock_run.stages = [
        {"name": "crawl", "status": "running", "started_at": None, "completed_at": None},
        {"name": "dedup", "status": "pending", "started_at": None, "completed_at": None},
        {"name": "import", "status": "pending", "started_at": None, "completed_at": None},
    ]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    with patch("app.core.pipeline.orchestrator.flag_modified"):
        result = await cancel_run(mock_session, mock_redis, run_id)

    # Verify result
    assert result.run_id == run_id
    assert result.status == "cancelled"
    assert "crawl" in result.stopped_stage_names
    assert "dedup" not in result.stopped_stage_names  # pending, not running
    assert mock_run.status == "cancelled"
    assert mock_run.error_log == "cancelled by user"
    assert mock_run.completed_at is not None

    # Verify Redis STOP flag set
    mock_redis.setex.assert_called_once_with(f"pipeline:stop:{run_id}", 3600, "1")

    # Verify session commit
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_completed_run_returns_409():
    """Test D-06: cancelling a completed run raises RunAlreadyTerminalError."""
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.status = "completed"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result

    mock_redis = AsyncMock()

    with pytest.raises(RunAlreadyTerminalError) as exc_info:
        await cancel_run(mock_session, mock_redis, run_id)
    assert "completed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancel_nonexistent_run_returns_404():
    """Test D-06: cancelling a non-existent run raises RunNotFoundError."""
    run_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_redis = AsyncMock()

    with pytest.raises(RunNotFoundError):
        await cancel_run(mock_session, mock_redis, run_id)


@pytest.mark.asyncio
async def test_cancel_already_cancelled_run_returns_409():
    """Test D-06: re-cancelling raises RunAlreadyTerminalError."""
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.status = "cancelled"  # already cancelled

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result

    mock_redis = AsyncMock()

    with pytest.raises(RunAlreadyTerminalError) as exc_info:
        await cancel_run(mock_session, mock_redis, run_id)
    assert "cancelled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancel_run_handles_redis_failure():
    """Test: cancel succeeds even if Redis fails (best-effort)."""
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.status = "running"
    mock_run.stages = []

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection lost"))

    with patch("app.core.pipeline.orchestrator.flag_modified"):
        result = await cancel_run(mock_session, mock_redis, run_id)

    assert result.status == "cancelled"
    # Cancel should still succeed despite Redis error


@pytest.mark.asyncio
async def test_cancel_run_handles_no_redis():
    """Test: cancel works when redis_client is None."""
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.status = "running"
    mock_run.stages = []

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    with patch("app.core.pipeline.orchestrator.flag_modified"):
        result = await cancel_run(mock_session, None, run_id)

    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_is_run_cancelled_returns_true_when_flag_set():
    """Test: is_run_cancelled returns True when Redis flag is '1'."""
    run_id = uuid.uuid4()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"1")

    result = await is_run_cancelled(mock_redis, run_id)
    assert result is True


@pytest.mark.asyncio
async def test_is_run_cancelled_returns_false_when_no_flag():
    """Test: is_run_cancelled returns False when Redis flag is not set."""
    run_id = uuid.uuid4()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    result = await is_run_cancelled(mock_redis, run_id)
    assert result is False


@pytest.mark.asyncio
async def test_is_run_cancelled_handles_no_redis():
    """Test: is_run_cancelled returns False when redis is None."""
    run_id = uuid.uuid4()
    result = await is_run_cancelled(None, run_id)
    assert result is False
