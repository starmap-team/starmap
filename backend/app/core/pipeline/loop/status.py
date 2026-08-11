"""Loop status / history retrieval + per-step verification (Phase 07-02 D-02).

Contains:
  - ``get_loop_status`` / ``get_loop_history`` module-level helpers
  - ``_build_loop_verification`` / ``_loop_step_checks`` verification helpers

Filled out fully in Task 6 (the compat-shell slim-down step). For Task 1
we only need a stub for ``_build_loop_verification`` because
``loop.common.LoopResult.to_dict`` imports it lazily.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.pipeline.loop.common import LoopStepResult


def _build_loop_verification(steps: list[LoopStepResult]) -> dict[str, Any]:
    """Loop verification placeholder — full implementation lands in Task 6."""
    return {"overall_passed": True, "steps": []}


__all__ = ["_build_loop_verification"]
