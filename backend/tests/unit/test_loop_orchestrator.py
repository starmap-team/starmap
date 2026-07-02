"""Unit tests for loop orchestrator."""
from __future__ import annotations

import pytest

from app.core.pipeline.loop_orchestrator import (
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
        assert StepStatus.DEGRADED.value == "degraded"
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
    def test_store_result_limits_history(self):
        from app.core.pipeline import loop_orchestrator as lo
        lo._LOOP_RESULTS.clear()

        # Add over limit
        for i in range(lo._LOOP_HISTORY_MAX + 10):
            r = LoopResult(
                run_id=f"r{i}",
                jd_text="text",
                target_position="dev",
                status=LoopRunStatus.COMPLETED,
            )
            LoopOrchestrator._store_result(r)

        assert len(lo._LOOP_RESULTS) <= lo._LOOP_HISTORY_MAX


@pytest.mark.asyncio
async def test_get_loop_status_not_found():
    result = await get_loop_status("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_loop_status_found():
    from app.core.pipeline import loop_orchestrator as lo
    lo._LOOP_RESULTS.clear()
    r = LoopResult(
        run_id="r-test",
        jd_text="text",
        target_position="dev",
        status=LoopRunStatus.COMPLETED,
    )
    LoopOrchestrator._store_result(r)
    status = await get_loop_status("r-test")
    assert status is not None
    assert status["run_id"] == "r-test"


@pytest.mark.asyncio
async def test_get_loop_history():
    from app.core.pipeline import loop_orchestrator as lo
    lo._LOOP_RESULTS.clear()
    for i in range(3):
        r = LoopResult(
            run_id=f"r{i}",
            jd_text="text",
            target_position="dev",
            status=LoopRunStatus.COMPLETED,
        )
        LoopOrchestrator._store_result(r)
    history = await get_loop_history(limit=10)
    assert len(history) == 3


class TestStep5LearningPath:
    def test_with_match_gaps(self):
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
        result = orch._step5_learning_path(match_result, graph_available=True, match_ok=True)
        assert result.status == StepStatus.SUCCESS
        assert len(result.data["path_items"]) == 2

    def test_with_match_failed(self):
        orch = LoopOrchestrator()
        result = orch._step5_learning_path({}, graph_available=False, match_ok=False)
        assert result.status == StepStatus.DEGRADED
        assert "path_items" in result.data

    def test_with_graph_unavailable_note(self):
        orch = LoopOrchestrator()
        match_result = {
            "skill_gap_detail": [{"skill": "Python", "importance": "required", "gap_level": "完全缺失"}],
        }
        result = orch._step5_learning_path(match_result, graph_available=False, match_ok=True)
        assert "历史图谱" in result.note or result.note is not None
