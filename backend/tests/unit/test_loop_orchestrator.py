"""Unit tests for loop orchestrator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.pipeline.loop_orchestrator import (
    _LOOP_RESULTS,
    LoopOrchestrator,
    LoopResult,
    LoopRunStatus,
    LoopStepResult,
    StepStatus,
    get_loop_history,
    get_loop_status,
)


class TestStepStatus:
    def test_status_values(self):
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILED.value == "failed"


class TestLoopStepResult:
    def test_construction(self):
        r = LoopStepResult(step=1, name="test", status=StepStatus.SUCCESS)
        assert r.step == 1
        assert r.status == StepStatus.SUCCESS


class TestLoopResult:
    def test_to_dict(self):
        r = LoopResult(
            run_id="r1",
            jd_text="hello world",
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        d = r.to_dict()
        assert d["run_id"] == "r1"
        assert d["target_position"] == "dev"
        assert d["status"] == "completed"

    def test_to_dict_truncates_long_text(self):
        r = LoopResult(
            run_id="r1",
            jd_text="x" * 500,
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        d = r.to_dict()
        assert "..." in d["jd_text"]


class TestStep1Validate:
    def test_empty_jd_fails(self):
        orch = LoopOrchestrator()
        result = orch._step1_validate_input("", "dev")
        assert result.status == StepStatus.FAILED

    def test_empty_target_is_optional(self):
        # QA B1: target_position 可选,空值不拒绝(Step 2 从 JD 推断)。
        orch = LoopOrchestrator()
        result = orch._step1_validate_input("text", "")
        assert result.status == StepStatus.SUCCESS

    def test_whitespace_fails(self):
        orch = LoopOrchestrator()
        result = orch._step1_validate_input("   ", "dev")
        assert result.status == StepStatus.FAILED

    def test_valid_input(self):
        orch = LoopOrchestrator()
        result = orch._step1_validate_input("text", "dev")
        assert result.status == StepStatus.SUCCESS
        assert result.data["jd_length"] == 4


class TestGenericLearningPath:
    def test_returns_path_items(self):
        path = LoopOrchestrator._generic_learning_path()
        assert "path_items" in path
        assert len(path["path_items"]) == 3
        assert path["estimated_learning_time"]


class TestStoreResult:
    def test_in_memory_cache_accepts_entries(self):
        """Verify the in-memory fallback cache can store and retrieve entries."""
        _LOOP_RESULTS.clear()
        r = LoopResult(
            run_id="r-test",
            jd_text="text",
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        _LOOP_RESULTS[r.run_id] = r
        assert "r-test" in _LOOP_RESULTS
        assert _LOOP_RESULTS["r-test"].run_id == "r-test"


@pytest.mark.asyncio
async def test_get_loop_status_not_found():
    result = await get_loop_status("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_loop_status_found():
    _LOOP_RESULTS.clear()
    r = LoopResult(
        run_id="r-test",
        jd_text="text",
        target_position="dev",
        status=LoopRunStatus.COMPLETED,
    )
    _LOOP_RESULTS[r.run_id] = r
    status = await get_loop_status("r-test")
    assert status is not None
    assert status["run_id"] == "r-test"


@pytest.mark.asyncio
async def test_get_loop_history():
    _LOOP_RESULTS.clear()
    for i in range(3):
        r = LoopResult(
            run_id=f"r{i}",
            jd_text="text",
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        _LOOP_RESULTS[r.run_id] = r
    history = await get_loop_history(limit=10)
    assert len(history) == 3


class TestStep5LearningPath:
    @pytest.mark.asyncio
    async def test_with_match_gaps(self):
        orch = LoopOrchestrator()
        match_result = {
            "skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python基础"]},
                {"skill": "Django", "importance": "bonus", "gap_level": "部分掌握", "learning_path": ["Python", "Django"]},
            ],
            "estimated_learning_time": "2 weeks",
            "overall_assessment": "good",
            "recommendations": ["learn Python"],
        }
        result = await orch._step5_learning_path(match_result, graph_available=True, match_ok=True)
        assert result.status == StepStatus.SUCCESS
        assert len(result.data["path_items"]) == 2

    @pytest.mark.asyncio
    async def test_with_match_failed(self):
        orch = LoopOrchestrator()
        result = await orch._step5_learning_path({}, graph_available=False, match_ok=False)
        # When match fails, returns FAILED status with generic fallback path
        assert result.status == StepStatus.FAILED
        assert "path_items" in result.data


# ---------------------------------------------------------------------------
# Tests for LoopOrchestrator async step methods
# ---------------------------------------------------------------------------
class TestStep2ExtractSkills:
    @pytest.mark.asyncio
    async def test_extraction_failure(self):
        """Step 2 returns FAILED when extraction raises an exception."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        with patch("app.core.extraction.jd_extract.extract_from_jd", new=AsyncMock(side_effect=RuntimeError("LLM error"))):
            result = await orch._step2_extract_skills("some jd text")
        assert result.status == StepStatus.FAILED
        assert "LLM error" in result.error


class TestStep4MatchDiagnosis:
    @pytest.mark.asyncio
    async def test_no_skills_returns_failed(self):
        """Step 4 returns FAILED when no skills are available."""
        orch = LoopOrchestrator()
        result = await orch._step4_match_diagnosis(
            target_position="Backend",
            extracted_skills=[],
            graph_available=True,
        )
        assert result.status == StepStatus.FAILED
        assert "No skills" in result.error

    @pytest.mark.asyncio
    async def test_match_exception_returns_failed(self):
        """Step 4 returns FAILED when match raises an exception."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        with patch("app.services.match_service.run_match", new=AsyncMock(side_effect=RuntimeError("match error"))):
            result = await orch._step4_match_diagnosis(
                target_position="Backend",
                extracted_skills=[{"name": "Python", "category": "hard_skill", "proficiency": "熟悉"}],
                graph_available=True,
            )
        assert result.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_match_success(self):
        """Step 4 returns SUCCESS when match works."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_result = {"match_id": "test", "match_score": 0.8, "target_position": "Backend"}
        with patch("app.services.match_service.run_match", new=AsyncMock(return_value=mock_result)):
            result = await orch._step4_match_diagnosis(
                target_position="Backend",
                extracted_skills=[{"name": "Python", "category": "hard_skill", "proficiency": "熟悉"}],
                graph_available=True,
            )
        assert result.status == StepStatus.SUCCESS
        assert result.data["match_score"] == 0.8


class TestStep3GraphUpdate:
    @pytest.mark.asyncio
    async def test_no_driver_returns_failed(self):
        """Step 3 returns FAILED when Neo4j driver is unavailable."""
        from unittest.mock import patch

        orch = LoopOrchestrator()
        with patch("app.services.resources.resources", type("R", (), {"neo4j_driver": None})()):
            result = await orch._step3_graph_update("run-1", {})
        assert result.status == StepStatus.FAILED
        assert "neo4j" in result.error.lower() or "unavailable" in result.error.lower()


# ---------------------------------------------------------------------------
# Additional coverage for loop_orchestrator
# ---------------------------------------------------------------------------
class TestStep3GraphUpdateWithDriver:
    @pytest.mark.asyncio
    async def test_sync_failure_returns_failed(self):
        """Step 3 returns FAILED when sync_from_pipeline fails."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_driver = object()
        with patch("app.services.resources.resources", type("R", (), {"neo4j_driver": mock_driver})()), \
             patch("app.services.graph_sync.sync_from_pipeline", new=AsyncMock(return_value={"synced": False, "error": "test error"})):
            result = await orch._step3_graph_update("run-1", {})
        assert result.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_sync_success(self):
        """Step 3 returns SUCCESS when sync works."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_driver = object()
        with patch("app.services.resources.resources", type("R", (), {"neo4j_driver": mock_driver})()), \
             patch("app.services.graph_sync.sync_from_pipeline", new=AsyncMock(return_value={"synced": True, "nodes": 5, "edges": 3})):
            result = await orch._step3_graph_update("run-1", {"skills": [{"name": "Python"}]})
        assert result.status == StepStatus.SUCCESS


class TestStep2ExtractSkillsSuccess:
    @pytest.mark.asyncio
    async def test_extraction_success(self):
        """Step 2 returns SUCCESS when extraction works."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_result = {
            "success": True,
            "data": {
                "required_skills": [{"name": "Python", "category": "hard_skill", "level": "熟悉"}],
                "preferred_skills": [{"name": "Docker", "category": "tool", "level": "了解"}],
                "position_name": "Backend",
            },
        }
        with patch("app.core.extraction.jd_extract.extract_from_jd", new=AsyncMock(return_value=mock_result)):
            result = await orch._step2_extract_skills("Python developer needed")
        assert result.status == StepStatus.SUCCESS
        assert len(result.data["skills"]) == 2

    @pytest.mark.asyncio
    async def test_extraction_returns_false(self):
        """Step 2 returns FAILED when extraction returns success=false."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_result = {"success": False, "error": "LLM timeout"}
        with patch("app.core.extraction.jd_extract.extract_from_jd", new=AsyncMock(return_value=mock_result)):
            result = await orch._step2_extract_skills("some text")
        assert result.status == StepStatus.FAILED


# ---------------------------------------------------------------------------
# Phase 07-02 D-03 / D-06: degradation判定 + model_used 透传 (T7)
# ---------------------------------------------------------------------------
class TestModelUsedPropagation:
    """Step 2 (extract) must surface the actual LLM model name in data so the
    frontend LoopStepSkills card can render cloud vs local fallback (D-06)."""

    @pytest.mark.asyncio
    async def test_model_used_passed_through(self):
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_result = {
            "success": True,
            "model_used": "deepseek-chat",
            "data": {
                "required_skills": [
                    {"name": "Python", "category": "hard_skill", "level": "熟悉", "confidence": 0.92},
                ],
                "preferred_skills": [],
                "position_name": "Backend",
            },
        }
        with patch("app.core.extraction.jd_extract.extract_from_jd",
                   new=AsyncMock(return_value=mock_result)):
            result = await orch._step2_extract_skills("some jd")
        assert result.data["model_used"] == "deepseek-chat"
        # D-05 metric row fields also surfaced
        assert result.data["skill_count"] == 1
        assert result.data["skill_confidence_avg"] == 0.92

    @pytest.mark.asyncio
    async def test_model_used_none_when_not_in_response(self):
        """When extraction doesn't return model_used, data key is present but None
        (honest empty state — Phase 1 / M6 '未评估' pattern)."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_result = {
            "success": True,
            "data": {"required_skills": [], "preferred_skills": [], "position_name": ""},
        }
        with patch("app.core.extraction.jd_extract.extract_from_jd",
                   new=AsyncMock(return_value=mock_result)):
            result = await orch._step2_extract_skills("text")
        assert result.data["model_used"] is None
        assert result.data["skill_confidence_avg"] is None


class TestStepLevelDirectInvocation:
    """Steps modules can be called directly without going through LoopOrchestrator
    (regression for the split — D-01)."""

    @pytest.mark.asyncio
    async def test_run_extract_step_success(self):
        from app.core.pipeline.loop.steps.extract import run_extract_step
        from unittest.mock import AsyncMock, patch

        with patch("app.core.extraction.jd_extract.extract_from_jd",
                   new=AsyncMock(return_value={
                       "success": True,
                       "model_used": "spark-x",
                       "data": {"required_skills": [], "preferred_skills": [], "position_name": ""},
                   })):
            result = await run_extract_step("hello jd")
        assert result.status == StepStatus.SUCCESS
        assert result.data["model_used"] == "spark-x"

    @pytest.mark.asyncio
    async def test_run_extract_step_exception(self):
        from app.core.pipeline.loop.steps.extract import run_extract_step
        from unittest.mock import AsyncMock, patch

        with patch("app.core.extraction.jd_extract.extract_from_jd",
                   new=AsyncMock(side_effect=RuntimeError("LLM down"))):
            result = await run_extract_step("hello jd")
        assert result.status == StepStatus.FAILED
        assert "LLM down" in result.error

    @pytest.mark.asyncio
    async def test_run_graph_update_step_no_driver(self):
        from app.core.pipeline.loop.steps.graph_update import run_graph_update_step
        from unittest.mock import patch

        with patch("app.services.resources.resources", type("R", (), {"neo4j_driver": None})()):
            result = await run_graph_update_step("run-1", {})
        assert result.status == StepStatus.FAILED
        assert "Neo4j" in result.error or "unavailable" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_match_step_no_skills(self):
        from app.core.pipeline.loop.steps.match import run_match_step
        result = await run_match_step(target_position="Backend", extracted_skills=[], graph_available=False)
        assert result.status == StepStatus.FAILED
        assert "No skills" in result.error

    @pytest.mark.asyncio
    async def test_run_learning_path_step_match_ok(self):
        from app.core.pipeline.loop.steps.learning_path import run_learning_path_step
        result = await run_learning_path_step(
            match_result={"skill_gap_detail": [
                {"skill": "Python", "importance": "required", "gap_level": "完全缺失",
                 "learning_path": ["Python基础"]},
            ], "estimated_learning_time": "2 weeks", "overall_assessment": "ok",
             "recommendations": []},
            match_ok=True, target_position="Backend",
        )
        assert result.status == StepStatus.SUCCESS
        assert result.data["path_length"] == 1

    @pytest.mark.asyncio
    async def test_run_learning_path_step_match_failed(self):
        from app.core.pipeline.loop.steps.learning_path import run_learning_path_step
        result = await run_learning_path_step(
            match_result={}, match_ok=False, target_position="Backend",
        )
        assert result.status == StepStatus.FAILED
        # Fallback path still has path_length key (D-05 metric row contract)
        assert "path_length" in result.data
        assert len(result.data["path_items"]) >= 1


class TestDegradationJudgment:
    """D-03 fail-fast + 降级判定:
    - step3 失败 → 整体仍 COMPLETED（degraded）
    - step4 失败 + step5 失败 → 整体仍 COMPLETED
    - ≥3 步失败 → 整体 FAILED
    Per-step 异常仍记 FAILED（不扩展 StepStatus enum）。"""

    @staticmethod
    def _patches(sync_return=None, match_return=None, plan_return=None, driver=object()):
        """Stack of patches used by D-03 degradation tests."""
        from contextlib import ExitStack
        sync = sync_return if sync_return is not None else {"synced": True, "nodes": 1, "edges": 0}
        match = match_return if match_return is not None else {
            "match_score": 0.5, "skill_gap_detail": [],
            "estimated_learning_time": "", "overall_assessment": "", "recommendations": [],
        }
        plan = plan_return if plan_return is not None else {"plan_id": "p-1"}
        stack = ExitStack()
        stack.enter_context(patch("app.services.resources.resources",
                                   type("R", (), {"neo4j_driver": driver})()))
        stack.enter_context(patch("app.core.extraction.jd_extract.extract_from_jd",
                                   new=AsyncMock(return_value={
                                       "success": True,
                                       "data": {"required_skills": [
                                           {"name": "Python", "category": "hard_skill", "level": "熟悉"},
                                       ], "preferred_skills": [], "position_name": "Backend"},
                                   })))
        stack.enter_context(patch("app.services.graph_sync.sync_from_pipeline",
                                   new=AsyncMock(return_value=sync)))
        stack.enter_context(patch("app.services.match_service.run_match",
                                   new=AsyncMock(return_value=match)))
        stack.enter_context(patch("app.services.learning_service.create_plan_from_match",
                                   new=AsyncMock(return_value=plan)))
        return stack

    @pytest.mark.asyncio
    async def test_step3_fail_keeps_run_completed(self):
        orch = LoopOrchestrator()
        with self._patches(sync_return={"synced": False, "error": "neo4j down"}):
            result = await orch.run_loop("jd", "Backend")
        step3_status = next(s.status for s in result.steps if s.step == 3)
        assert step3_status == StepStatus.FAILED
        # D-03: only 1 failure (step3) → overall COMPLETED
        assert result.status == LoopRunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_step4_step5_both_fail_still_completed(self):
        orch = LoopOrchestrator()
        with self._patches():
            with patch("app.services.match_service.run_match",
                       new=AsyncMock(side_effect=RuntimeError("match boom"))):
                result = await orch.run_loop("jd", "Backend")
        step4 = next(s for s in result.steps if s.step == 4)
        step5 = next(s for s in result.steps if s.step == 5)
        assert step4.status == StepStatus.FAILED
        assert step5.status == StepStatus.FAILED
        # D-03: only step 4/5 failed → overall COMPLETED
        assert result.status == LoopRunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_three_failures_means_failed(self):
        orch = LoopOrchestrator()
        # step2 raises + step3 fails + step4 fails
        with self._patches(sync_return={"synced": False, "error": "neo4j down"}):
            with patch("app.core.extraction.jd_extract.extract_from_jd",
                       new=AsyncMock(side_effect=RuntimeError("LLM down"))), \
                 patch("app.services.match_service.run_match",
                       new=AsyncMock(side_effect=RuntimeError("match boom"))):
                result = await orch.run_loop("jd", "Backend")
        failed = [s for s in result.steps if s.status == StepStatus.FAILED]
        assert len(failed) >= 3
        assert result.status == LoopRunStatus.FAILED
