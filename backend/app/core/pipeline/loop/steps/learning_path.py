"""Step 5 — Learning path derivation .

Extracted from ``loop_orchestrator.py._step5_learning_path`` and
``_generic_learning_path``.

On success the returned ``LoopStepResult.data`` adds a ``path_length`` field
(``len(path_items)`` — used by the frontend ``LoopStepLearning`` card to
render the metric row). ``completed_steps`` is intentionally NOT computed
server-side — the frontend derives it from each ``path_items[].step.status``
to keep the path item as the single source of truth.
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import GAP_LEVEL_MASTERED
from app.core.pipeline.loop.common import (
 STEP_NAMES,
 LoopStepResult,
 StepStatus,
)
from app.exceptions import PipelineStageError, StarMapError

def generic_learning_path -> dict[str, Any]:
 """Return a generic fallback learning path (3 starter items)."""
 return {
 "path_items": [
 {
 "skill": "Python基础",
 "importance": "required",
 "gap_level": "建议学习",
 "learning_path": ["Python基础"],
 },
 {
 "skill": "数据结构与算法",
 "importance": "required",
 "gap_level": "建议学习",
 "learning_path": ["数据结构与算法"],
 },
 {
 "skill": "项目实战",
 "importance": "bonus",
 "gap_level": "建议学习",
 "learning_path": ["项目实战"],
 },
 ],
 "estimated_learning_time": "4-6周（兼职学习）",
 "overall_assessment": "通用学习路径，请根据目标岗位调整。",
 "recommendations": ["请指定明确的目标岗位以获得个性化学习路径。"],
 "source": "generic_fallback",
 }

async def run_learning_path_step(
 match_result: dict[str, Any],
 match_ok: bool,
 target_position: str = "",
 session: AsyncSession | None = None,
 graph_available: bool = False,
) -> LoopStepResult:
 """Step 5: Derive learning path from match gaps and auto-create plan.

 Args:
 match_result: Step 4 output (or empty dict if match skipped/failed).
 match_ok: Whether Step 4 succeeded.
 target_position: Resolved target position name.
 session: Optional async DB session (auto-creates a learning plan row).
 graph_available: Passed through from Step 3 (kept for API parity).

 Returns:
 LoopStepResult — SUCCESS carries ``path_items`` + ``path_length``;
 FAILED with a generic fallback ``data`` payload when match is
 unavailable (the loop still surfaces a degraded path).
 """
 start = time.monotonic

 # If match diagnosis succeeded, derive path from match gaps
 if match_ok and match_result:
 try:
 gap_details = match_result.get("skill_gap_detail", [])
 missing = [g for g in gap_details if g.get("gap_level") != GAP_LEVEL_MASTERED]

 path_items: list[dict[str, Any]] = []
 for gap in missing:
 path_items.append({
 "skill": gap.get("skill", ""),
 "importance": gap.get("importance", "required"),
 "gap_level": gap.get("gap_level", ""),
 "learning_path": gap.get("learning_path", []),
 })

 learning_path_data: dict[str, Any] = {
 "path_items": path_items,
 "path_length": len(path_items), # metric row field
 "estimated_learning_time": match_result.get("estimated_learning_time", ""),
 "overall_assessment": match_result.get("overall_assessment", ""),
 "recommendations": match_result.get("recommendations", []),
 "source": "match_gaps",
 }

 # Auto-create learning plan in DB when session is available
 plan_info = None
 if session is not None and target_position and match_result:
 try:
 from app.services.learning_service import create_plan_from_match

 plan_info = await create_plan_from_match(
 session,
 target_position=target_position,
 match_result=match_result,
 )
 if plan_info and plan_info.get("plan_id"):
 learning_path_data["plan_id"] = plan_info["plan_id"]
 logger.info(
 "Auto-created learning plan {} for target '{}'",
 plan_info["plan_id"], target_position,
 )
 except PipelineStageError:
 raise
 except StarMapError:
 raise
 except Exception as exc:
 logger.exception(
 "Failed to auto-create learning plan for '{}': {}",
 target_position, exc,
 )

 return LoopStepResult(
 step=5,
 name=STEP_NAMES[5],
 status=StepStatus.SUCCESS,
 data=learning_path_data,
 duration_seconds=time.monotonic - start,
 )
 except PipelineStageError:
 raise
 except StarMapError:
 raise
 except Exception as exc:
 logger.exception("Step 5 path derivation from match failed: {}", exc)

 # Fallback: generic learning path
 fallback = generic_learning_path
 # Always include path_length so frontend metric row never has to compute.
 fallback.setdefault("path_length", len(fallback.get("path_items", [])))
 return LoopStepResult(
 step=5,
 name=STEP_NAMES[5],
 status=StepStatus.FAILED,
 error="Match diagnosis not available for learning path generation",
 data=fallback,
 duration_seconds=time.monotonic - start,
 )

__all__ = ["run_learning_path_step", "generic_learning_path"]
