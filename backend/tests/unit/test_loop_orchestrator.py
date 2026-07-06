"""Unit tests for loop orchestrator."""
from __future__ import annotations

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

    def test_empty_target_fails(self):
        orch = LoopOrchestrator()
        result = orch._step1_validate_input("text", "")
        assert result.status == StepStatus.FAILED

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
             patch("app.services.graph_service.sync_from_pipeline", new=AsyncMock(return_value={"synced": False, "error": "test error"})):
            result = await orch._step3_graph_update("run-1", {})
        assert result.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_sync_success(self):
        """Step 3 returns SUCCESS when sync works."""
        from unittest.mock import AsyncMock, patch

        orch = LoopOrchestrator()
        mock_driver = object()
        with patch("app.services.resources.resources", type("R", (), {"neo4j_driver": mock_driver})()), \
             patch("app.services.graph_service.sync_from_pipeline", new=AsyncMock(return_value={"synced": True, "nodes": 5, "edges": 3})):
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
