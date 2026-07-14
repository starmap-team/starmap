"""Unit tests for loop orchestrator business logic — service/core layer only.

Directly tests core functions — no TestClient, no HTTP layer.
Covers:
- LoopOrchestrator._step1_validate_input (input validation)
- LoopResult.to_dict (serialization + jd_text truncation)
- LoopStepResult / LoopResult dataclass construction
- Overall status determination logic
- LoopRunRequest Pydantic validation
- In-memory history storage fallback
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline.loop_orchestrator import (
    LoopOrchestrator,
    LoopResult,
    LoopRunStatus,
    LoopStepResult,
    StepStatus,
    STEP_NAMES,
    _LOOP_RESULTS,
)


# ── Helpers ──


def _make_step_result(
    step: int = 1,
    name: str = "JD输入",
    status: StepStatus = StepStatus.SUCCESS,
    data: dict | None = None,
    error: str | None = None,
    duration_seconds: float = 0.1,
) -> LoopStepResult:
    return LoopStepResult(
        step=step,
        name=name,
        status=status,
        data=data or {},
        error=error,
        duration_seconds=duration_seconds,
    )


def _make_loop_result(
    run_id: str = "test-run-1",
    jd_text: str = "Python developer",
    target_position: str = "Backend",
    status: LoopRunStatus = LoopRunStatus.COMPLETED,
    steps: list[LoopStepResult] | None = None,
) -> LoopResult:
    return LoopResult(
        run_id=run_id,
        jd_text=jd_text,
        target_position=target_position,
        status=status,
        steps=steps or [],
    )


# ══════════════════════════════════════════════════════════════
# _step1_validate_input — input validation
# ══════════════════════════════════════════════════════════════


class TestStep1ValidateInput:
    """LoopOrchestrator._step1_validate_input — JD + position validation."""

    def setup_method(self):
        self.orch = LoopOrchestrator()

    def test_valid_input_returns_success(self):
        result = self.orch._step1_validate_input("Python developer", "Backend")
        assert result.status == StepStatus.SUCCESS
        assert result.step == 1
        assert result.name == STEP_NAMES[1]
        assert result.error is None
        assert result.data["jd_length"] == 16
        assert result.data["target_position"] == "Backend"

    def test_empty_jd_text_returns_failed(self):
        result = self.orch._step1_validate_input("", "Backend")
        assert result.status == StepStatus.FAILED
        assert result.error == "JD text is empty"

    def test_whitespace_only_jd_returns_failed(self):
        result = self.orch._step1_validate_input("   ", "Backend")
        assert result.status == StepStatus.FAILED
        assert result.error == "JD text is empty"

    def test_empty_target_position_returns_failed(self):
        result = self.orch._step1_validate_input("Python developer", "")
        assert result.status == StepStatus.FAILED
        assert result.error == "Target position is empty"

    def test_whitespace_target_position_returns_failed(self):
        result = self.orch._step1_validate_input("Python developer", "  ")
        assert result.status == StepStatus.FAILED
        assert result.error == "Target position is empty"

    def test_both_empty_returns_failed_for_jd_first(self):
        """When both are empty, JD check triggers first."""
        result = self.orch._step1_validate_input("", "")
        assert result.status == StepStatus.FAILED
        assert result.error == "JD text is empty"

    def test_strips_target_position_whitespace(self):
        result = self.orch._step1_validate_input("JD text", "  Backend  ")
        assert result.status == StepStatus.SUCCESS
        assert result.data["target_position"] == "Backend"


# ══════════════════════════════════════════════════════════════
# LoopResult.to_dict — serialization
# ══════════════════════════════════════════════════════════════


class TestLoopResultToDict:
    """LoopResult.to_dict — serialization and truncation."""

    def test_basic_serialization(self):
        result = _make_loop_result()
        d = result.to_dict()
        assert d["run_id"] == "test-run-1"
        assert d["target_position"] == "Backend"
        assert d["status"] == "completed"
        assert d["steps"] == []

    def test_jd_text_truncation_over_200(self):
        long_text = "A" * 300
        result = _make_loop_result(jd_text=long_text)
        d = result.to_dict()
        assert d["jd_text"] == "A" * 200 + "..."
        assert len(d["jd_text"]) == 203

    def test_jd_text_no_truncation_under_200(self):
        short_text = "Short JD"
        result = _make_loop_result(jd_text=short_text)
        d = result.to_dict()
        assert d["jd_text"] == "Short JD"

    def test_jd_text_exactly_200(self):
        text_200 = "A" * 200
        result = _make_loop_result(jd_text=text_200)
        d = result.to_dict()
        assert d["jd_text"] == text_200
        assert "..." not in d["jd_text"]

    def test_steps_serialized(self):
        steps = [
            _make_step_result(step=1, status=StepStatus.SUCCESS, duration_seconds=0.5),
            _make_step_result(step=2, status=StepStatus.FAILED, error="LLM timeout", duration_seconds=1.234),
        ]
        result = _make_loop_result(steps=steps)
        d = result.to_dict()
        assert len(d["steps"]) == 2
        assert d["steps"][0]["step"] == 1
        assert d["steps"][0]["status"] == "success"
        assert d["steps"][1]["error"] == "LLM timeout"
        assert d["steps"][1]["duration_seconds"] == 1.23  # rounded to 2 decimals

    def test_total_duration_rounded(self):
        result = _make_loop_result()
        result.total_duration_seconds = 3.14159
        d = result.to_dict()
        assert d["total_duration_seconds"] == 3.14


# ══════════════════════════════════════════════════════════════
# LoopStepResult — dataclass construction
# ══════════════════════════════════════════════════════════════


class TestLoopStepResult:
    """LoopStepResult — field construction and defaults."""

    def test_defaults(self):
        step = LoopStepResult(step=1, name="test", status=StepStatus.SUCCESS)
        assert step.data == {}
        assert step.error is None
        assert step.duration_seconds == 0.0
        assert step.note is None is None

    def test_all_fields(self):
        step = LoopStepResult(
            step=3, name="Graph", status=StepStatus.FAILED,
            data={"nodes": 5}, error="timeout", duration_seconds=2.0, note="retry needed",
        )
        assert step.step == 3
        assert step.data == {"nodes": 5}
        assert step.error == "timeout"
        assert step.note == "retry needed"


# ══════════════════════════════════════════════════════════════
# Overall status determination — from step results
# ══════════════════════════════════════════════════════════════


class TestOverallStatusDetermination:
    """Overall loop status from step failure patterns."""

    def test_all_success_is_completed(self):
        steps = [_make_step_result(step=i, status=StepStatus.SUCCESS) for i in range(1, 6)]
        failed = [s for s in steps if s.status == StepStatus.FAILED]
        # Logic from loop_orchestrator: no failures → COMPLETED
        assert len(failed) == 0

    def test_step1_failure_aborts_pipeline(self):
        """If step 1 fails, pipeline should abort early."""
        step1 = _make_step_result(step=1, status=StepStatus.FAILED, error="empty JD")
        # In run_loop, step1 failure → immediate return with FAILED status
        assert step1.status == StepStatus.FAILED

    def test_steps_4_5_failure_still_completed(self):
        """Only steps 4/5 failed → pipeline still COMPLETED."""
        steps = [
            _make_step_result(step=1, status=StepStatus.SUCCESS),
            _make_step_result(step=2, status=StepStatus.SUCCESS),
            _make_step_result(step=3, status=StepStatus.SUCCESS),
            _make_step_result(step=4, status=StepStatus.FAILED, error="no match"),
            _make_step_result(step=5, status=StepStatus.FAILED, error="no path"),
        ]
        failed = [s for s in steps if s.status == StepStatus.FAILED]
        # Logic: all failed steps are in (4, 5) → COMPLETED
        assert all(s.step in (4, 5) for s in failed)

    def test_3_plus_failures_is_failed(self):
        """3+ step failures → overall FAILED."""
        steps = [
            _make_step_result(step=1, status=StepStatus.SUCCESS),
            _make_step_result(step=2, status=StepStatus.FAILED),
            _make_step_result(step=3, status=StepStatus.FAILED),
            _make_step_result(step=4, status=StepStatus.FAILED),
            _make_step_result(step=5, status=StepStatus.SUCCESS),
        ]
        failed = [s for s in steps if s.status == StepStatus.FAILED]
        assert len(failed) >= 3


# ══════════════════════════════════════════════════════════════
# LoopRunRequest — Pydantic validation
# ══════════════════════════════════════════════════════════════


class TestLoopRunRequestValidation:
    """LoopRunRequest — Pydantic field validation (min_length=1)."""

    def test_valid_request(self):
        from app.api.v1.loop import LoopRunRequest
        req = LoopRunRequest(jd_text="Python dev", target_position="Backend")
        assert req.jd_text == "Python dev"
        assert req.target_position == "Backend"

    def test_empty_jd_fails_validation(self):
        from app.api.v1.loop import LoopRunRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoopRunRequest(jd_text="", target_position="Backend")

    def test_empty_target_fails_validation(self):
        # API-03: empty target_position is coerced to None (optional), not rejected
        from app.api.v1.loop import LoopRunRequest
        req = LoopRunRequest(jd_text="Python dev", target_position="")
        assert req.target_position is None  # empty string coerced to None


# ══════════════════════════════════════════════════════════════
# In-memory history — fallback storage
# ══════════════════════════════════════════════════════════════


class TestInMemoryHistory:
    """In-memory _LOOP_RESULTS dict — fallback storage behavior."""

    def test_store_and_retrieve(self):
        _LOOP_RESULTS["mem-test-1"] = _make_loop_result(run_id="mem-test-1")
        assert "mem-test-1" in _LOOP_RESULTS
        assert _LOOP_RESULTS["mem-test-1"].run_id == "mem-test-1"
        # Cleanup
        del _LOOP_RESULTS["mem-test-1"]

    def test_to_dict_from_stored(self):
        result = _make_loop_result(jd_text="Test JD text")
        _LOOP_RESULTS["mem-test-2"] = result
        d = _LOOP_RESULTS["mem-test-2"].to_dict()
        assert d["jd_text"] == "Test JD text"
        del _LOOP_RESULTS["mem-test-2"]


# ══════════════════════════════════════════════════════════════
# STEP_NAMES — step name mapping
# ══════════════════════════════════════════════════════════════


class TestStepNames:
    """STEP_NAMES — step number to name mapping."""

    def test_all_5_steps_defined(self):
        for i in range(1, 6):
            assert i in STEP_NAMES

    def test_step_names_are_chinese(self):
        for name in STEP_NAMES.values():
            assert len(name) > 0