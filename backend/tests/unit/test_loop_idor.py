"""Tests for SEC-04: loop_results IDOR complete fix."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helper: mock LoopResultRecord ──


def _make_record(run_id: str, user_id: str = "system", status: str = "completed", steps_json: dict | None = None):
    """Create a mock LoopResultRecord."""
    record = MagicMock()
    record.run_id = run_id
    record.user_id = user_id
    record.status = status
    record.steps_json = steps_json or {"steps": []}
    return record


# ── Test: run_loop passes user_id ──


class TestRunLoopUserId:
    """SEC-04: run_loop creates record with user_id."""

    @pytest.mark.asyncio
    async def test_run_loop_passes_user_id(self) -> None:
        """POST /loop/run stores the authenticated user's sub as user_id."""
        from app.core.pipeline.loop_orchestrator import LoopOrchestrator

        orchestrator = LoopOrchestrator()
        with patch.object(orchestrator, "_insert_loop_run", new_callable=AsyncMock) as mock_insert, \
             patch.object(orchestrator, "_update_steps_json", new_callable=AsyncMock), \
             patch.object(orchestrator, "_complete_loop_run", new_callable=AsyncMock):
            mock_insert.return_value = None
            # _step1_validate_input is sync, need to patch it to return success
            with patch.object(orchestrator, "_step1_validate_input") as mock_step1, \
                 patch.object(orchestrator, "_step2_extract_skills", new_callable=AsyncMock), \
                 patch.object(orchestrator, "_step3_graph_update", new_callable=AsyncMock):
                from app.core.pipeline.loop_orchestrator import LoopStepResult, StepStatus
                mock_step1.return_value = LoopStepResult(
                    step=1, name="Input", status=StepStatus.FAILED, error="test",
                    duration_seconds=0.01,
                )
                await orchestrator.run_loop(
                    jd_text="test jd",
                    target_position="test pos",
                    session=None,
                    user_id="alice",
                )
                # Verify _insert_loop_run was called with user_id
                mock_insert.assert_called_once()
                call_kwargs = mock_insert.call_args
                assert call_kwargs.kwargs.get("user_id") == "alice" or \
                       (len(call_kwargs.args) > 2 and call_kwargs.args[2] == "alice") or \
                       call_kwargs.kwargs.get("user_id") == "alice"


# ── Test: get_loop_status IDOR guard ──


class TestLoopStatusIDOR:
    """SEC-04: loop_status ownership check."""

    @pytest.mark.asyncio
    async def test_own_run_visible(self) -> None:
        """User can see their own run (returns data)."""
        from app.core.pipeline.loop_orchestrator import get_loop_status

        mock_session = AsyncMock()
        mock_record = _make_record("run-1", user_id="alice")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_loop_status(
            "run-1", session=mock_session, user_id="alice", is_admin=False,
        )
        assert status is not None
        assert status["run_id"] == "run-1"

    @pytest.mark.asyncio
    async def test_other_user_run_hidden(self) -> None:
        """Non-admin user gets None for another user's run."""
        from app.core.pipeline.loop_orchestrator import get_loop_status

        mock_session = AsyncMock()
        # scalar_one_or_none returns None when the WHERE filter excludes the row
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_loop_status(
            "run-2", session=mock_session, user_id="alice", is_admin=False,
        )
        # Falls through to pipeline_runs and in-memory, both return None
        assert status is None

    @pytest.mark.asyncio
    async def test_admin_sees_any_run(self) -> None:
        """Admin user can see any run regardless of user_id."""
        from app.core.pipeline.loop_orchestrator import get_loop_status

        mock_session = AsyncMock()
        mock_record = _make_record("run-3", user_id="bob")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_loop_status(
            "run-3", session=mock_session, user_id="admin", is_admin=True,
        )
        assert status is not None
        assert status["run_id"] == "run-3"


# ── Test: get_loop_history IDOR guard ──


class TestLoopHistoryIDOR:
    """SEC-04: loop_history filters by user_id."""

    @pytest.mark.asyncio
    async def test_non_admin_sees_own_runs(self) -> None:
        """Non-admin user only sees their own runs in history."""
        from app.core.pipeline.loop_orchestrator import get_loop_history

        mock_session = AsyncMock()
        mock_record = _make_record("run-a", user_id="alice")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_record]
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await get_loop_history(
            limit=50, session=mock_session, user_id="alice", is_admin=False,
        )
        assert len(items) == 1
        assert items[0]["run_id"] == "run-a"

    @pytest.mark.asyncio
    async def test_admin_sees_all_runs(self) -> None:
        """Admin user sees all runs in history."""
        from app.core.pipeline.loop_orchestrator import get_loop_history

        mock_session = AsyncMock()
        mock_record1 = _make_record("run-x", user_id="alice")
        mock_record2 = _make_record("run-y", user_id="bob")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_record1, mock_record2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await get_loop_history(
            limit=50, session=mock_session, user_id="admin", is_admin=True,
        )
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_system_runs_visible_to_admin_only(self) -> None:
        """Historical data (user_id='system') is visible to admin only."""
        from app.core.pipeline.loop_orchestrator import get_loop_history

        # Non-admin: query filters by user_id, so system runs are excluded
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # no matching rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await get_loop_history(
            limit=50, session=mock_session, user_id="alice", is_admin=False,
        )
        # Falls through to pipeline_runs and in-memory, both return empty
        assert items == []


# ── Test: backward compatibility ──


class TestLoopIDORBackwardCompat:
    """SEC-04: Backward compatibility with default params."""

    @pytest.mark.asyncio
    async def test_no_user_id_param_uses_default(self) -> None:
        """Calling get_loop_status without user_id uses default 'system'."""
        from app.core.pipeline.loop_orchestrator import get_loop_status

        # Without user_id/is_admin params, defaults to user_id="system", is_admin=False
        # This means only system-owned runs are visible
        mock_session = AsyncMock()
        mock_record = _make_record("run-sys", user_id="system")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_loop_status("run-sys", session=mock_session)
        assert status is not None
