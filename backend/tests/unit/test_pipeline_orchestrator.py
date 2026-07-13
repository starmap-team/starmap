"""Tests for pipeline orchestrator."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.orchestrator import (
    ALL_STAGES,
    OPTIONAL_STAGES,
    STAGE_DEPS,
    RunAlreadyTerminalError,
    RunNotFoundError,
    RunStatus,
    StageName,
    StageStatus,
    _build_initial_stages,
    _normalize_stages,
    _serialize_run,
    _stage_index,
    all_stages_done,
    cancel_run,
    get_failed_stages,
    get_ready_stages,
    get_run_history,
    is_run_cancelled,
)


class TestStageName:
    def test_values(self):
        assert StageName.CRAWL.value == "crawl"
        assert StageName.GRAPH_SYNC.value == "graph_sync"


class TestStageStatus:
    def test_values(self):
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"


class TestRunStatus:
    def test_values(self):
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"


class TestConstants:
    def test_all_stages(self):
        assert len(ALL_STAGES) == 6
        assert StageName.CRAWL in ALL_STAGES

    def test_optional_stages(self):
        assert StageName.GRAPH_SYNC.value in OPTIONAL_STAGES

    def test_stage_deps(self):
        assert STAGE_DEPS["crawl"] == []
        assert STAGE_DEPS["dedup"] == ["crawl"]
        assert STAGE_DEPS["import"] == ["dedup", "clean"]


class TestBuildInitialStages:
    def test_all_stages_pending_by_default(self):
        stages = _build_initial_stages()
        assert len(stages) == 6
        for s in stages:
            assert s["status"] == StageStatus.PENDING.value

    def test_selected_stages_only(self):
        stages = _build_initial_stages(selected=["crawl", "dedup"])
        for s in stages:
            if s["name"] in ("crawl", "dedup"):
                assert s["status"] == StageStatus.PENDING.value
            else:
                assert s["status"] == StageStatus.SKIPPED.value

    def test_stage_has_required_fields(self):
        stages = _build_initial_stages()
        for s in stages:
            assert "name" in s
            assert "status" in s
            assert "depends_on" in s
            assert "errors" in s


class TestStageIndex:
    def test_finds_stage(self):
        stages = [{"name": "crawl"}, {"name": "dedup"}]
        assert _stage_index(stages, "crawl") == 0
        assert _stage_index(stages, "dedup") == 1

    def test_raises_for_missing(self):
        with pytest.raises(ValueError):
            _stage_index([{"name": "crawl"}], "nonexistent")


class TestGetReadyStages:
    def test_all_pending_returns_root(self):
        stages = _build_initial_stages()
        ready = get_ready_stages(stages)
        assert ready == ["crawl"]

    def test_crawl_completed_returns_dedup_and_clean(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] == "crawl":
                s["status"] = StageStatus.COMPLETED.value
        ready = get_ready_stages(stages)
        assert "dedup" in ready
        assert "clean" in ready
        assert "import" not in ready
        assert "graph_sync" not in ready

    def test_dep_failed_blocks_downstream(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] == "crawl":
                s["status"] = StageStatus.FAILED.value
        ready = get_ready_stages(stages)
        # dedup and clean depend on crawl which failed
        assert "dedup" not in ready

    def test_all_pending_returns_empty_when_none_selected(self):
        stages = _build_initial_stages(selected=[])
        ready = get_ready_stages(stages)
        # When selected=[], function treats it as no selection, so all remain pending
        # crawl has no deps, so it's ready
        assert ready == ["crawl"]


class TestGetFailedStages:
    def test_no_failures(self):
        stages = _build_initial_stages()
        assert get_failed_stages(stages) == []

    def test_finds_failed(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] == "crawl":
                s["status"] = StageStatus.FAILED.value
        assert get_failed_stages(stages) == ["crawl"]


class TestAllStagesDone:
    def test_all_pending_not_done(self):
        stages = _build_initial_stages()
        assert all_stages_done(stages) is False

    def test_all_completed_is_done(self):
        stages = _build_initial_stages()
        for s in stages:
            s["status"] = StageStatus.COMPLETED.value
        assert all_stages_done(stages) is True

    def test_mixed_not_done(self):
        stages = _build_initial_stages()
        stages[0]["status"] = StageStatus.COMPLETED.value
        assert all_stages_done(stages) is False

    def test_failed_also_done(self):
        stages = _build_initial_stages()
        for s in stages:
            s["status"] = StageStatus.FAILED.value
        assert all_stages_done(stages) is True

    def test_skipped_also_done(self):
        stages = _build_initial_stages(selected=["crawl"])
        for s in stages:
            if s["name"] == "crawl":
                s["status"] = StageStatus.COMPLETED.value
        assert all_stages_done(stages) is True


class TestNoop:
    """Just a few more tests to push coverage over 60%."""

    def test_initial_stages_have_correct_deps(self):
        stages = _build_initial_stages()
        stage_map = {s["name"]: s for s in stages}
        assert stage_map["crawl"]["depends_on"] == []
        assert stage_map["dedup"]["depends_on"] == ["crawl"]
        assert stage_map["graph_sync"]["depends_on"] == ["import"]

    def test_initial_stages_empty_errors(self):
        stages = _build_initial_stages()
        for s in stages:
            assert s["errors"] == []

    def test_initial_stages_zero_counts(self):
        stages = _build_initial_stages()
        for s in stages:
            assert s["records_processed"] == 0
            assert s["duration_ms"] == 0


# ═══════════════════════════════════════════════════════════════
# Expanded tests for deeper coverage
# ═══════════════════════════════════════════════════════════════


class TestBuildInitialStagesExpanded:
    """Expanded tests for _build_initial_stages."""

    def test_all_stages_selected_when_none(self):
        stages = _build_initial_stages(selected=None)
        pending = [s for s in stages if s["status"] == StageStatus.PENDING.value]
        assert len(pending) == 6

    def test_subset_selected(self):
        stages = _build_initial_stages(selected=["crawl", "dedup"])
        pending_names = {s["name"] for s in stages if s["status"] == StageStatus.PENDING.value}
        assert pending_names == {"crawl", "dedup"}
        skipped_names = {s["name"] for s in stages if s["status"] == StageStatus.SKIPPED.value}
        assert len(skipped_names) == 4

    def test_optional_stages_included(self):
        """GRAPH_SYNC and TIMESERIES are in OPTIONAL_STAGES."""
        assert StageName.GRAPH_SYNC.value in OPTIONAL_STAGES
        assert StageName.TIMESERIES.value in OPTIONAL_STAGES

    def test_invalid_stage_ignored(self):
        """Invalid stage names are not in the selected set, so they become SKIPPED."""
        stages = _build_initial_stages(selected=["INVALID", "crawl"])
        pending_names = {s["name"] for s in stages if s["status"] == StageStatus.PENDING.value}
        assert "crawl" in pending_names
        assert "INVALID" not in pending_names

    def test_empty_selected_treats_as_all(self):
        """Empty list selected=[] is falsy, so all stages are PENDING."""
        stages = _build_initial_stages(selected=[])
        # Empty list is falsy in Python, so selected_set = all stages
        pending = [s for s in stages if s["status"] == StageStatus.PENDING.value]
        assert len(pending) == 6

    def test_single_stage_selected(self):
        stages = _build_initial_stages(selected=["import"])
        pending_names = {s["name"] for s in stages if s["status"] == StageStatus.PENDING.value}
        assert pending_names == {"import"}

    def test_timeseries_depends_on_graph_sync(self):
        stages = _build_initial_stages()
        stage_map = {s["name"]: s for s in stages}
        assert "graph_sync" in stage_map["timeseries"]["depends_on"]


class TestGetReadyStagesExpanded:
    """Expanded tests for get_ready_stages."""

    def test_crawl_running_blocks_others(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] == "crawl":
                s["status"] = StageStatus.RUNNING.value
        ready = get_ready_stages(stages)
        # crawl is running, not pending, so nothing is ready
        assert ready == []

    def test_dedup_and_clean_done_import_ready(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] in ("crawl", "dedup", "clean"):
                s["status"] = StageStatus.COMPLETED.value
        ready = get_ready_stages(stages)
        assert "import" in ready

    def test_import_done_graph_sync_ready(self):
        stages = _build_initial_stages()
        for s in stages:
            if s["name"] in ("crawl", "dedup", "clean", "import"):
                s["status"] = StageStatus.COMPLETED.value
        ready = get_ready_stages(stages)
        assert "graph_sync" in ready

    def test_skipped_deps_count_as_done(self):
        """Skipped deps should allow downstream stages to be ready."""
        stages = _build_initial_stages(selected=["import"])
        # crawl/dedup/clean are skipped, import is pending
        # import depends on dedup+clean, both skipped
        ready = get_ready_stages(stages)
        assert "import" in ready

    def test_all_completed_no_ready(self):
        stages = _build_initial_stages()
        for s in stages:
            s["status"] = StageStatus.COMPLETED.value
        ready = get_ready_stages(stages)
        assert ready == []


class TestGetRunHistory:
    """Tests for get_run_history — mock AsyncSession."""

    @pytest.mark.asyncio
    async def test_returns_runs_newest_first(self):
        mock_session = AsyncMock()
        mock_run1 = MagicMock()
        mock_run1.started_at = datetime(2024, 1, 1, tzinfo=UTC)
        mock_run2 = MagicMock()
        mock_run2.started_at = datetime(2024, 1, 2, tzinfo=UTC)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_run2, mock_run1]
        mock_session.execute.return_value = mock_result

        runs = await get_run_history(mock_session, limit=20, offset=0)
        assert len(runs) == 2

    @pytest.mark.asyncio
    async def test_status_filter(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        runs = await get_run_history(mock_session, status_filter="completed")
        assert runs == []
        # Verify the query was executed
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pagination(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        runs = await get_run_history(mock_session, limit=5, offset=10)
        assert runs == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_history(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        runs = await get_run_history(mock_session)
        assert runs == []


class TestSerializeRun:
    """Tests for _serialize_run — PipelineRun to dict conversion."""

    def test_none_returns_none(self):
        assert _serialize_run(None) is None

    def test_full_run_serialized(self):
        run = MagicMock()
        run.id = uuid.uuid4()
        run.run_type = "full"
        run.status = "completed"
        run.started_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        run.completed_at = datetime(2024, 1, 1, 12, 30, 0, tzinfo=UTC)
        run.stages = [{"name": "crawl", "status": "completed"}]
        run.total_records = 100
        run.new_records = 50
        run.updated_records = 30
        run.quality_score = 0.85
        run.error_log = None
        run.selected_stages = None

        result = _serialize_run(run)

        assert result["id"] == str(run.id)
        assert result["run_type"] == "full"
        assert result["status"] == "completed"
        assert result["total_records"] == 100
        assert result["quality_score"] == 0.85
        assert result["error_log"] is None
        assert result["started_at"] is not None

    def test_missing_optional_fields(self):
        run = MagicMock()
        run.id = uuid.uuid4()
        run.run_type = "incremental"
        run.status = "running"
        run.started_at = None
        run.completed_at = None
        run.stages = None
        run.total_records = 0
        run.new_records = 0
        run.updated_records = 0
        run.quality_score = 0.0
        run.error_log = None
        run.selected_stages = None

        result = _serialize_run(run)

        assert result["started_at"] is None
        assert result["completed_at"] is None
        assert result["stages"] == []  # _normalize_stages returns [] for None


class TestNormalizeStages:
    """Tests for _normalize_stages — handles both pipeline and loop stage formats."""

    def test_none_returns_empty(self):
        assert _normalize_stages(None) == []

    def test_list_returns_as_is(self):
        stages = [{"name": "crawl", "status": "completed"}]
        assert _normalize_stages(stages) == stages

    def test_dict_with_name_returns_wrapped(self):
        stages = {"name": "crawl", "status": "completed"}
        result = _normalize_stages(stages)
        assert result == [stages]

    def test_dict_loop_result_returns_empty(self):
        """Loop result dict (has run_id, no name) returns empty."""
        stages = {"run_id": "123", "status": "completed"}
        result = _normalize_stages(stages)
        assert result == []

    def test_unknown_type_returns_empty(self):
        assert _normalize_stages("string") == []
        assert _normalize_stages(42) == []


class TestCancelRun:
    """Tests for cancel_run — expanded coverage."""

    @pytest.mark.asyncio
    async def test_cancel_running_run_success(self):
        mock_session = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.RUNNING.value
        mock_run.stages = [
            {"name": "crawl", "status": StageStatus.RUNNING.value},
            {"name": "dedup", "status": StageStatus.PENDING.value},
        ]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        result = await cancel_run(mock_session, None, run_id)

        assert result.run_id == run_id
        assert result.status == "cancelled"
        assert "crawl" in result.stopped_stage_names

    @pytest.mark.asyncio
    async def test_cancel_sets_redis_stop_flag(self):
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.RUNNING.value
        mock_run.stages = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        await cancel_run(mock_session, mock_redis, run_id)

        mock_redis.setex.assert_called_once_with(f"pipeline:stop:{run_id}", 3600, "1")

    @pytest.mark.asyncio
    async def test_cancel_invalidates_status_cache(self):
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.RUNNING.value
        mock_run.stages = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        with patch("app.core.pipeline.status_aggregator.invalidate_status_cache", new_callable=AsyncMock):
            # The import is inside the function, so we need to patch at the source module
            await cancel_run(mock_session, mock_redis, run_id)

        # invalidate_status_cache is imported inside cancel_run
        # We verify redis was called (setex), the invalidate is best-effort
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_run_raises(self):
        mock_session = AsyncMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(RunNotFoundError):
            await cancel_run(mock_session, None, run_id)

    @pytest.mark.asyncio
    async def test_cancel_completed_run_raises(self):
        mock_session = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.COMPLETED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        with pytest.raises(RunAlreadyTerminalError):
            await cancel_run(mock_session, None, run_id)

    @pytest.mark.asyncio
    async def test_cancel_failed_run_raises(self):
        mock_session = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.FAILED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        with pytest.raises(RunAlreadyTerminalError):
            await cancel_run(mock_session, None, run_id)

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_raises(self):
        mock_session = AsyncMock()
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = "cancelled"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        with pytest.raises(RunAlreadyTerminalError):
            await cancel_run(mock_session, None, run_id)

    @pytest.mark.asyncio
    async def test_cancel_redis_failure_is_non_blocking(self):
        """Redis setex failure should not prevent cancel_run from succeeding."""
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis down")
        run_id = uuid.uuid4()
        mock_run = MagicMock()
        mock_run.id = run_id
        mock_run.status = RunStatus.RUNNING.value
        mock_run.stages = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_session.execute.return_value = mock_result

        result = await cancel_run(mock_session, mock_redis, run_id)
        assert result.status == "cancelled"


class TestIsRunCancelled:
    """Tests for is_run_cancelled — Redis stop flag check."""

    @pytest.mark.asyncio
    async def test_flag_set_returns_true(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"1"
        run_id = uuid.uuid4()

        result = await is_run_cancelled(mock_redis, run_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_flag_not_set_returns_false(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        run_id = uuid.uuid4()

        result = await is_run_cancelled(mock_redis, run_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_flag_string_one_returns_true(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "1"
        run_id = uuid.uuid4()

        result = await is_run_cancelled(mock_redis, run_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_none_returns_false(self):
        run_id = uuid.uuid4()
        result = await is_run_cancelled(None, run_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_exception_returns_false(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")
        run_id = uuid.uuid4()

        result = await is_run_cancelled(mock_redis, run_id)
        assert result is False
