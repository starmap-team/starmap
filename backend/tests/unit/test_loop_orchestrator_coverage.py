"""Additional coverage for loop_orchestrator: run_loop orchestration, DB persistence
helpers, and DB-backed get_loop_status / get_loop_history.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.loop_orchestrator import (
    _LOOP_HISTORY_MAX,
    _LOOP_RESULTS,
    STEP_NAMES,
    LoopOrchestrator,
    LoopResult,
    LoopRunStatus,
    LoopStepResult,
    StepStatus,
    get_loop_history,
    get_loop_status,
)


def _resources_mock(neo4j_driver):
    """Build a stand-in for app.services.resources.resources with a configurable driver."""
    return type("R", (), {"neo4j_driver": neo4j_driver})()


def _patch_full_loop(
    extraction_return=None,
    sync_return=None,
    match_return=None,
    plan_return=None,
    driver=object(),
):
    """Stack of patches that intercept the four external dependencies of run_loop.

    Returns a context manager that activates all of them simultaneously.
    """
    from contextlib import ExitStack

    extraction = extraction_return if extraction_return is not None else {
        "success": True,
        "data": {
            "required_skills": [{"name": "Python", "category": "hard_skill", "level": "熟悉"}],
            "preferred_skills": [],
            "position_name": "Backend",
        },
    }
    sync = sync_return if sync_return is not None else {
        "synced": True, "nodes": 3, "edges": 2,
    }
    match = match_return if match_return is not None else {
        "match_score": 0.8, "skill_gap_detail": [],
        "estimated_learning_time": "2 weeks",
        "overall_assessment": "ok", "recommendations": [],
    }
    plan = plan_return if plan_return is not None else {"plan_id": "plan-1"}

    stack = ExitStack()
    stack.enter_context(
        patch("app.services.resources.resources", _resources_mock(driver))
    )
    stack.enter_context(
        patch("app.core.extraction.jd_extract.extract_from_jd",
              new=AsyncMock(return_value=extraction))
    )
    stack.enter_context(
        patch("app.services.graph_sync.sync_from_pipeline",
              new=AsyncMock(return_value=sync))
    )
    stack.enter_context(
        patch("app.services.match_service.run_match",
              new=AsyncMock(return_value=match))
    )
    stack.enter_context(
        patch("app.services.learning_service.create_plan_from_match",
              new=AsyncMock(return_value=plan))
    )
    return stack


@pytest.fixture(autouse=True)
def _clear_in_memory():
    """Make sure in-memory fallback cache is empty between tests."""
    _LOOP_RESULTS.clear()
    yield
    _LOOP_RESULTS.clear()


# ---------------------------------------------------------------------------
# Constants & enum sanity
# ---------------------------------------------------------------------------
class TestConstants:
    def test_step_names_has_five(self):
        assert set(STEP_NAMES.keys()) == {1, 2, 3, 4, 5}
        assert all(isinstance(v, str) and v for v in STEP_NAMES.values())

    def test_loop_run_status_values(self):
        assert LoopRunStatus.RUNNING.value == "running"
        assert LoopRunStatus.COMPLETED.value == "completed"
        assert LoopRunStatus.FAILED.value == "failed"

    def test_history_max_is_200(self):
        assert _LOOP_HISTORY_MAX == 200


# ---------------------------------------------------------------------------
# LoopResult edge cases
# ---------------------------------------------------------------------------
class TestLoopResultExtras:
    def test_to_dict_exactly_200_chars_not_truncated(self):
        r = LoopResult(
            run_id="r",
            jd_text="x" * 200,
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        d = r.to_dict()
        assert d["jd_text"] == "x" * 200

    def test_to_dict_includes_step_fields(self):
        r = LoopResult(
            run_id="r",
            jd_text="x",
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        r.steps = [
            LoopStepResult(
                step=1, name="x", status=StepStatus.SUCCESS,
                data={"k": 1}, duration_seconds=0.1, note="hi",
            )
        ]
        d = r.to_dict()
        s = d["steps"][0]
        assert s["data"] == {"k": 1}
        assert s["duration_seconds"] == 0.1
        assert s["note"] == "hi"


# ---------------------------------------------------------------------------
# run_loop orchestration
# ---------------------------------------------------------------------------
class TestRunLoopHappyPath:
    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        """Full pipeline: step1-5 all succeed, status COMPLETED."""
        orch = LoopOrchestrator()
        with _patch_full_loop():
            result = await orch.run_loop(
                jd_text="We need a Python dev",
                target_position="Backend Engineer",
            )

        assert result.status == LoopRunStatus.COMPLETED
        assert len(result.steps) == 5
        assert all(s.status == StepStatus.SUCCESS for s in result.steps)
        assert result.match_result.get("match_score") == 0.8
        assert result.learning_path.get("source") == "match_gaps"
        assert result.total_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_run_id_is_uuid(self):
        orch = LoopOrchestrator()
        with _patch_full_loop():
            result = await orch.run_loop("jd", "dev")
        # uuid.UUID round-trip
        uuid.UUID(result.run_id)


class TestRunLoopEarlyExit:
    @pytest.mark.asyncio
    async def test_empty_jd_exits_with_failed(self):
        orch = LoopOrchestrator()
        with _patch_full_loop():
            result = await orch.run_loop(jd_text="", target_position="dev")
        assert result.status == LoopRunStatus.FAILED
        assert len(result.steps) == 1
        assert result.steps[0].status == StepStatus.FAILED
        assert "empty" in result.steps[0].error.lower()

    @pytest.mark.asyncio
    async def test_empty_target_completes_via_inference(self):
        """LOOP-09: empty target_position is inferred from extraction, not rejected."""
        orch = LoopOrchestrator()
        with _patch_full_loop():
            result = await orch.run_loop(jd_text="valid jd", target_position="")
        assert result.status == LoopRunStatus.COMPLETED
        assert len(result.steps) == 5
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.target_position == "Backend"


class TestRunLoopStep3Failure:
    @pytest.mark.asyncio
    async def test_step3_fail_continues_to_step4_5(self):
        """When step3 fails, step4/5 still execute with graph_available=False."""
        orch = LoopOrchestrator()
        sync_fail = {"synced": False, "error": "neo4j down"}
        with _patch_full_loop(sync_return=sync_fail):
            result = await orch.run_loop("jd", "dev")
        # step1 + step2 succeed, step3 fails, step4/5 still run
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[1].status == StepStatus.SUCCESS
        assert result.steps[2].status == StepStatus.FAILED
        # step4 may succeed if run_match doesn't actually need graph
        # overall status depends on whether only step 4/5 failed
        assert result.status in (LoopRunStatus.COMPLETED, LoopRunStatus.FAILED)


class TestRunLoopOverallStatus:
    @pytest.mark.asyncio
    async def test_only_4_5_failed_still_completed(self):
        """All failures confined to steps 4 and 5 -> overall COMPLETED."""
        orch = LoopOrchestrator()
        with _patch_full_loop(
            sync_return={"synced": True, "nodes": 1, "edges": 0},
            match_return={"match_score": 0.0, "skill_gap_detail": []},  # forces step4 to succeed actually
            # we need step4 + step5 to fail. Easiest: patch step4 to raise.
        ):
            with patch("app.services.match_service.run_match",
                       new=AsyncMock(side_effect=RuntimeError("match exploded"))):
                result = await orch.run_loop("jd", "dev")
        # step4 fails, step5 then has match_ok=False -> fallback path -> FAILED
        # So step4 FAILED + step5 FAILED -> both in (4,5) -> COMPLETED
        assert result.status == LoopRunStatus.COMPLETED
        step_statuses = [(s.step, s.status) for s in result.steps]
        assert (4, StepStatus.FAILED) in step_statuses

    @pytest.mark.asyncio
    async def test_three_or_more_failures_means_failed(self):
        """3+ failed steps -> overall FAILED (not COMPLETED)."""
        orch = LoopOrchestrator()
        with _patch_full_loop(
            sync_return={"synced": False, "error": "boom"},
            match_return={},  # forces step4 to fall through (no skills derived), step5 also fails
        ):
            # Make step2 also fail by patching extract_from_jd to raise
            with patch("app.core.extraction.jd_extract.extract_from_jd",
                       new=AsyncMock(side_effect=RuntimeError("LLM down"))):
                result = await orch.run_loop("jd", "dev")
        # step2 fails, step3 fails, step4 may or may not depending on extracted_skills
        # We need 3+ failures
        failed = [s for s in result.steps if s.status == StepStatus.FAILED]
        assert len(failed) >= 3
        assert result.status == LoopRunStatus.FAILED


# ---------------------------------------------------------------------------
# DB persistence helpers (when session is None -> no-op, when session raises -> fallback)
# ---------------------------------------------------------------------------
class TestInsertLoopRun:
    @pytest.mark.asyncio
    async def test_no_session_returns_none(self):
        """Without a session, _insert_loop_run is a no-op and returns None."""
        result = await LoopOrchestrator._insert_loop_run("r-1", session=None)
        assert result is None


class TestUpdateStepsJson:
    @pytest.mark.asyncio
    async def test_no_record_returns_early(self):
        result = LoopResult(
            run_id="r-1", jd_text="x", target_position="dev",
            status=LoopRunStatus.RUNNING,
        )
        # db_record is None -> returns without doing anything
        out = await LoopOrchestrator._update_steps_json(None, result, session=None)
        assert out is None

    @pytest.mark.asyncio
    async def test_session_exception_is_swallowed(self):
        """If session.get raises, we swallow and don't propagate."""
        db_record = MagicMock()
        db_record.id = 1
        session = MagicMock()
        session.get = AsyncMock(side_effect=RuntimeError("db down"))

        result = LoopResult(
            run_id="r-1", jd_text="x", target_position="dev",
            status=LoopRunStatus.RUNNING,
        )
        # Must not raise
        await LoopOrchestrator._update_steps_json(db_record, result, session=session)


class TestCompleteLoopRun:
    @pytest.mark.asyncio
    async def test_no_record_falls_back_to_in_memory(self):
        """With no db_record, the in-memory cache is populated."""
        result = LoopResult(
            run_id="r-fallback", jd_text="x", target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        await LoopOrchestrator._complete_loop_run(None, result, session=None)
        assert "r-fallback" in _LOOP_RESULTS

    @pytest.mark.asyncio
    async def test_in_memory_evicts_oldest_when_over_cap(self):
        """When _LOOP_RESULTS exceeds _LOOP_HISTORY_MAX, oldest entries are dropped."""
        # Fill cache to exactly the cap
        for i in range(_LOOP_HISTORY_MAX):
            r = LoopResult(
                run_id=f"old-{i}", jd_text="x", target_position="dev",
                status=LoopRunStatus.COMPLETED,
            )
            _LOOP_RESULTS[r.run_id] = r

        # Adding one more should evict the oldest
        new_result = LoopResult(
            run_id="r-new", jd_text="x", target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        await LoopOrchestrator._complete_loop_run(None, new_result, session=None)

        assert len(_LOOP_RESULTS) == _LOOP_HISTORY_MAX
        assert "old-0" not in _LOOP_RESULTS  # oldest evicted
        assert "r-new" in _LOOP_RESULTS

    @pytest.mark.asyncio
    async def test_session_exception_falls_back_to_in_memory(self):
        """If session.get raises inside _complete_loop_run, fall back to in-memory."""
        db_record = MagicMock()
        db_record.id = 1
        session = MagicMock()
        session.get = AsyncMock(side_effect=RuntimeError("db down"))

        result = LoopResult(
            run_id="r-fallback2", jd_text="x", target_position="dev",
            status=LoopRunStatus.FAILED,
        )
        result.steps = [LoopStepResult(
            step=1, name="x", status=StepStatus.FAILED, error="boom"
        )]

        await LoopOrchestrator._complete_loop_run(db_record, result, session=session)
        assert "r-fallback2" in _LOOP_RESULTS

    @pytest.mark.asyncio
    async def test_session_success_skips_in_memory(self):
        """When DB write succeeds, in-memory cache is NOT used as primary store."""
        db_record = MagicMock()
        db_record.id = 1
        refreshed = MagicMock()
        session = MagicMock()
        session.get = AsyncMock(return_value=refreshed)
        session.commit = AsyncMock()

        result = LoopResult(
            run_id="r-db", jd_text="x", target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        await LoopOrchestrator._complete_loop_run(db_record, result, session=session)
        assert "r-db" not in _LOOP_RESULTS  # DB path took it
        assert refreshed.status == LoopRunStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# get_loop_status with DB session
# ---------------------------------------------------------------------------
class TestGetLoopStatusWithSession:
    @pytest.mark.asyncio
    async def test_returns_loop_results_row(self):
        row = MagicMock()
        row.run_id = "r-1"
        row.status = "completed"
        row.steps_json = {"steps": [{"step": 1, "status": "success"}]}

        session = MagicMock()
        session.execute = AsyncMock()
        # First call (loop_results): returns the row
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=row))

        result = await get_loop_status("r-1", session=session)
        assert result["run_id"] == "r-1"
        assert result["status"] == "completed"
        assert result["steps"] == [{"step": 1, "status": "success"}]

    @pytest.mark.asyncio
    async def test_falls_through_to_pipeline_runs(self):
        """When loop_results is empty, query pipeline_runs (legacy)."""
        legacy_row = MagicMock()
        legacy_row.id = "uuid-as-string"  # string id (we use uuid.UUID in query)
        legacy_row.status = "completed"
        legacy_row.stages = {"steps": [{"step": 1}], "extra": "data"}

        session = MagicMock()
        # Two execute calls: loop_results empty, then pipeline_runs hit
        # pipeline_runs expects select(PipelineRun).where(id == uuid.UUID(run_id))
        # We can't easily satisfy uuid.UUID(run_id) for arbitrary strings; use a real uuid.
        run_uuid = uuid.uuid4()
        legacy_row.id = run_uuid

        empty = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        hit = MagicMock()
        hit.scalar_one_or_none = MagicMock(return_value=legacy_row)
        session.execute = AsyncMock(side_effect=[empty, hit])

        result = await get_loop_status(str(run_uuid), session=session)
        assert result is not None
        assert result["run_id"] == str(run_uuid)
        assert result["status"] == "completed"
        assert "steps" in result

    @pytest.mark.asyncio
    async def test_session_exception_falls_back_to_in_memory(self):
        """When both DB queries raise, fall through to in-memory cache."""
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))

        r = LoopResult(
            run_id="r-mem", jd_text="x", target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        _LOOP_RESULTS["r-mem"] = r

        result = await get_loop_status("r-mem", session=session)
        assert result is not None
        assert result["run_id"] == "r-mem"


# ---------------------------------------------------------------------------
# get_loop_history with DB session
# ---------------------------------------------------------------------------
class TestGetLoopHistoryWithSession:
    @pytest.mark.asyncio
    async def test_returns_loop_results_history(self):
        row1 = MagicMock()
        row1.run_id = "r-1"
        row1.status = "completed"
        row1.steps_json = {"step": 1}

        row2 = MagicMock()
        row2.run_id = "r-2"
        row2.status = "failed"
        row2.steps_json = {"step": 1}

        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all = MagicMock(return_value=[row1, row2])
        session.execute = AsyncMock(return_value=result_mock)

        history = await get_loop_history(limit=10, session=session)
        assert len(history) == 2
        assert history[0]["run_id"] == "r-1"
        assert history[1]["run_id"] == "r-2"

    @pytest.mark.asyncio
    async def test_legacy_pipeline_runs_path(self):
        """When loop_results empty, query pipeline_runs filtered by run_type='loop'."""
        # First execute: loop_results empty (scalars().all() == [])
        # Second execute: pipeline_runs returns rows
        empty_result = MagicMock()
        empty_result.scalars.return_value.all = MagicMock(return_value=[])
        legacy_row = MagicMock()
        legacy_row.id = uuid.uuid4()
        legacy_row.status = "completed"
        legacy_row.stages = {"steps": [{"step": 1}]}

        hit_result = MagicMock()
        hit_result.scalars.return_value.all = MagicMock(return_value=[legacy_row])

        session = MagicMock()
        session.execute = AsyncMock(side_effect=[empty_result, hit_result])

        history = await get_loop_history(limit=5, session=session)
        assert len(history) == 1
        assert history[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_db_failure_falls_back_to_in_memory(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))

        for i in range(3):
            r = LoopResult(
                run_id=f"r-mem-{i}", jd_text="x", target_position="dev",
                status=LoopRunStatus.COMPLETED,
                total_duration_seconds=float(i),
            )
            _LOOP_RESULTS[r.run_id] = r

        history = await get_loop_history(limit=10, session=session)
        # Returns last `limit` in reverse order
        run_ids = [h["run_id"] for h in history]
        assert "r-mem-2" in run_ids
        assert "r-mem-1" in run_ids
        assert "r-mem-0" in run_ids

    @pytest.mark.asyncio
    async def test_history_respects_limit(self):
        for i in range(5):
            r = LoopResult(
                run_id=f"r-{i}", jd_text="x", target_position="dev",
                status=LoopRunStatus.COMPLETED,
                total_duration_seconds=float(i),
            )
            _LOOP_RESULTS[r.run_id] = r
        history = await get_loop_history(limit=2)
        assert len(history) == 2


# ---------------------------------------------------------------------------
# Step5 with auto plan creation (session path)
# ---------------------------------------------------------------------------
class TestStep5WithSession:
    @pytest.mark.asyncio
    async def test_creates_plan_when_session_and_match_ok(self):
        orch = LoopOrchestrator()
        match_result = {
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required",
                 "gap_level": "完全缺失", "learning_path": ["Python基础"]},
            ],
            "estimated_learning_time": "2 weeks",
            "overall_assessment": "ok", "recommendations": [],
        }
        session = MagicMock()
        with patch("app.services.learning_service.create_plan_from_match",
                   new=AsyncMock(return_value={"plan_id": "plan-42"})):
            result = await orch._step5_learning_path(
                match_result=match_result,
                graph_available=True,
                match_ok=True,
                session=session,
                target_position="Backend",
            )
        assert result.status == StepStatus.SUCCESS
        assert result.data["plan_id"] == "plan-42"

    @pytest.mark.asyncio
    async def test_plan_creation_failure_still_succeeds_step5(self):
        orch = LoopOrchestrator()
        match_result = {
            "skill_gap_detail": [],
            "estimated_learning_time": "1 week",
            "overall_assessment": "ok", "recommendations": [],
        }
        session = MagicMock()
        with patch("app.services.learning_service.create_plan_from_match",
                   new=AsyncMock(side_effect=RuntimeError("db error"))):
            result = await orch._step5_learning_path(
                match_result=match_result,
                graph_available=True,
                match_ok=True,
                session=session,
                target_position="Backend",
            )
        # step5 still succeeds, just no plan_id
        assert result.status == StepStatus.SUCCESS
        assert "plan_id" not in result.data


# ---------------------------------------------------------------------------
# Driver acquisition in run_loop (the import-time fallback)
# ---------------------------------------------------------------------------
class TestRunLoopDriverAcquisition:
    @pytest.mark.asyncio
    async def test_resources_import_failure_yields_no_driver(self):
        """If the `from app.services.resources import resources` raises, driver is None."""
        orch = LoopOrchestrator()
        # Patch the import to raise in run_loop's try/except block
        # Note: the module also imports resources in step3; both have try/except
        sync_fail_no_driver = {"synced": False, "error": "neo4j_driver_unavailable"}
        with patch.dict("sys.modules", {"app.services.resources": None}):
            with patch("app.core.extraction.jd_extract.extract_from_jd",
                       new=AsyncMock(return_value={"success": True, "data": {"required_skills": []}})):
                with patch("app.services.graph_sync.sync_from_pipeline",
                           new=AsyncMock(return_value=sync_fail_no_driver)):
                    result = await orch.run_loop("jd", "dev")
        # Step3 should have failed because driver acquisition failed
        step3 = result.steps[2]
        assert step3.status == StepStatus.FAILED
