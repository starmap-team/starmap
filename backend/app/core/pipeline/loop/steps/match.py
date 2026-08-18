"""Step 4 — Match diagnosis (/).

Extracted from ``loop_orchestrator.py._step4_match_diagnosis``.

The match service (``app.services.match_service.run_match``) already returns
a ``score_breakdown`` block per M5 — see
``app/core/matching/service.py:349-354``:

 score_breakdown: {
 required_avg: float, # 必备技能平均得分
 bonus_avg: float, # 加分技能平均得分
 weight_required: 0.7, # 必备权重
 weight_bonus: 0.3, # 加分权重
 inflated: bool, # CII 通胀修正触发标记
 }

The frontend ``LoopStepMatch`` card consumes these flat keys (no nested
``weights`` object) — / M5 口径.
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.core.pipeline.loop.common import (
 STEP_NAMES,
 LoopStepResult,
 StepStatus,
)
from app.exceptions import PipelineStageError, StarMapError

async def run_match_step(
 target_position: str,
 extracted_skills: list[dict[str, Any]],
 graph_available: bool,
 driver: Any = None,
 db_session: Any = None,
) -> LoopStepResult:
 """Step 4: Run match diagnosis with extracted skills vs target position.

 Args:
 target_position: Resolved target position name.
 extracted_skills: Step 2 output (list of skill dicts).
 graph_available: Whether Step 3 succeeded (passed through, kept for
 future graph-augmented matching).
 driver: Optional Neo4j driver (kept for API parity).
 db_session: Optional async DB session for match persistence.

 Returns:
 LoopStepResult — SUCCESS carries the full ``match_result`` (including
 ``score_breakdown``) so the frontend can render the M5 breakdown row.
 FAILED on empty skills or any match exception.
 """
 start = time.monotonic

 if not extracted_skills:
 return LoopStepResult(
 step=4,
 name=STEP_NAMES[4],
 status=StepStatus.FAILED,
 error="No skills available for matching",
 duration_seconds=time.monotonic - start,
 )

 try:
 from app.services.match_service import run_match

 person_skills = [
 {
 "name": s["name"],
 "category": s.get("category", "hard_skill"),
 "proficiency": s.get("proficiency", "熟悉"),
 }
 for s in extracted_skills
 if s.get("name")
 ]

 match_result = await run_match(
 target_position=target_position,
 person_skills=person_skills,
 driver=driver,
 db_session=db_session,
 )

 return LoopStepResult(
 step=4,
 name=STEP_NAMES[4],
 status=StepStatus.SUCCESS,
 data=match_result,
 duration_seconds=time.monotonic - start,
 )
 except PipelineStageError:
 raise
 except StarMapError:
 raise
 except Exception as exc:
 logger.exception("Step 4 (match diagnosis) failed: {}", exc)
 return LoopStepResult(
 step=4,
 name=STEP_NAMES[4],
 status=StepStatus.FAILED,
 error=str(exc),
 duration_seconds=time.monotonic - start,
 )

__all__ = ["run_match_step"]
