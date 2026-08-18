"""Closed-Loop Orchestrator — compat / re-export shell .

All real logic lives in ``app.core.pipeline.loop.{common,status,steps.*}``.
This module re-exports ``LoopOrchestrator`` + ``get_loop_status`` +
``get_loop_history`` and keeps ``LoopOrchestrator`` step methods as thin
delegates so legacy test ``monkeypatch`` paths still resolve.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline.loop.common import (
 _LOOP_HISTORY_MAX, # noqa: F401
 _LOOP_RESULTS, # noqa: F401
 STEP_NAMES, # noqa: F401
 LoopResult,
 LoopRunStatus,
 LoopStepResult,
 StepStatus,
 _complete_loop_run,
 _insert_loop_run,
 _update_steps_json,
)

if TYPE_CHECKING:
 from app.models.pipeline_models import LoopResultRecord
from app.core.pipeline.loop.steps.extract import run_extract_step
from app.core.pipeline.loop.steps.graph_update import run_graph_update_step
from app.core.pipeline.loop.steps.learning_path import generic_learning_path, run_learning_path_step
from app.core.pipeline.loop.steps.match import run_match_step
from app.core.pipeline.loop.steps.validate import resolve_target_position, run_validate_step
from app.exceptions import PipelineStageError, StarMapError

class LoopOrchestrator:
 """5-step closed-loop pipeline (compat shell — )."""

 async def run_loop(
 self,
 jd_text: str,
 target_position: str | None,
 session: AsyncSession | None = None,
 user_id: str = "system", # SEC-04
 ) -> LoopResult:
 """Execute the full 5-step closed-loop pipeline ( fail-fast + degrade).

 QA-FIX (F#10): 增加取消/异常兜底 — 客户端断开取消、asyncio.wait_for 超时或
 任何未捕获异常时，将运行标记为 FAILED 并写入 completed_at，避免 DB 记录
 永久停留在 running（同 的 stuck-running 模式）。
 """
 run_id = str(uuid.uuid4)
 start = time.monotonic
 result = LoopResult(
 run_id=run_id, jd_text=jd_text, target_position=target_position,
 status=LoopRunStatus.RUNNING,
 user_id=user_id, # SEC-04 QA-FIX F#11: in-memory 历史过滤
 )
 db_record = await self._insert_loop_run(run_id, session=session, user_id=user_id)
 try:
 return await self._run_loop_inner(
 jd_text, target_position, session, run_id, start, result, db_record,
 )
 except asyncio.CancelledError:
 result.status = LoopRunStatus.FAILED
 result.total_duration_seconds = time.monotonic - start
 logger.warning("Loop {} cancelled (client disconnect/timeout) — marking failed", run_id)
 try:
 await self._complete_loop_run(db_record, result, session=session)
 except Exception as exc:
 logger.warning("Failed to persist cancelled loop run {}: {}", run_id, exc)
 raise
 except Exception:
 result.status = LoopRunStatus.FAILED
 result.total_duration_seconds = time.monotonic - start
 logger.exception("Loop {} failed with unhandled exception — marking failed", run_id)
 try:
 await self._complete_loop_run(db_record, result, session=session)
 except Exception as exc:
 logger.warning("Failed to persist failed loop run {}: {}", run_id, exc)
 raise

 async def _run_loop_inner(
 self,
 jd_text: str,
 target_position: str | None,
 session: AsyncSession | None,
 run_id: str,
 start: float,
 result: LoopResult,
 db_record: Any,
 ) -> LoopResult:
 """(QA-FIX F#10 提取) 5 步闭环实际执行体 — 成功/按步失败路径与原实现一致。"""
 # Step 1: validation
 step1 = self._step1_validate_input(jd_text, target_position)
 result.steps.append(step1)
 await self._update_steps_json(db_record, result, session=session)
 if step1.status == StepStatus.FAILED:
 result.status = LoopRunStatus.FAILED
 result.total_duration_seconds = time.monotonic - start
 await self._complete_loop_run(db_record, result, session=session)
 return result

 # Step 2: extraction
 step2 = await self._step2_extract_skills(jd_text)
 result.steps.append(step2)
 extraction_data = step2.data if step2.status == StepStatus.SUCCESS else {}
 if extraction_data:
 result.extracted_skills = extraction_data.get("skills", [])
 await self._update_steps_json(db_record, result, session=session)

 effective_target = self._resolve_target_position(target_position, extraction_data)
 result.target_position = effective_target

 # Step 3: graph update — acquire Neo4j driver
 driver = None
 try:
 from app.services.resources import resources as app_resources
 driver = app_resources.neo4j_driver
 except (PipelineStageError, StarMapError):
 raise
 except Exception as exc:
 logger.debug("Neo4j driver not available for step 3/4: {}", exc)

 step3 = await self._step3_graph_update(run_id, extraction_data, target_position=effective_target)
 result.steps.append(step3)
 graph_ok = step3.status == StepStatus.SUCCESS
 result.graph_update = step3.data
 await self._update_steps_json(db_record, result, session=session)

 # Step 4: match diagnosis (LOOP-09: skip if no effective target_position)
 if effective_target:
 step4 = await self._step4_match_diagnosis(
 target_position=effective_target,
 extracted_skills=result.extracted_skills,
 graph_available=graph_ok, driver=driver, db_session=session,
 )
 result.steps.append(step4)
 if step4.status == StepStatus.SUCCESS:
 result.match_result = step4.data
 else:
 step4 = LoopStepResult(step=4, name="Match Diagnosis", status=StepStatus.SKIPPED, data={},
 note="Skipped: no target_position")
 result.steps.append(step4)
 await self._update_steps_json(db_record, result, session=session)

 # Step 5: learning path (LOOP-09: skip if no target or match skipped)
 if effective_target and step4.status != StepStatus.SKIPPED:
 step5 = await self._step5_learning_path(
 match_result=result.match_result, graph_available=graph_ok,
 match_ok=step4.status != StepStatus.FAILED,
 session=session, target_position=effective_target,
 )
 result.steps.append(step5)
 result.learning_path = step5.data
 else:
 step5 = LoopStepResult(step=5, name="Learning Path", status=StepStatus.SKIPPED, data={},
 note="Skipped: no target_position or match skipped")
 result.steps.append(step5)

 # Determine overall status : only path/match failures → COMPLETED; ≥3 failures → FAILED
 failed = [s for s in result.steps if s.status == StepStatus.FAILED]
 if failed and all(s.step in (4, 5) for s in failed):
 result.status = LoopRunStatus.COMPLETED
 elif len(failed) >= 3:
 result.status = LoopRunStatus.FAILED
 else:
 result.status = LoopRunStatus.COMPLETED

 result.total_duration_seconds = time.monotonic - start
 await self._complete_loop_run(db_record, result, session=session)

 logger.info(
 "Loop {} completed: status={} steps=[{}] duration={:.2f}s",
 run_id,
 result.status.value,
 ", ".join(f"s{s.step}={s.status.value}" for s in result.steps),
 result.total_duration_seconds,
 )
 return result

 # ---- Step delegates (compat shell — preserve monkeypatch paths) ----

 def _step1_validate_input(self, jd_text: str, target_position: str | None) -> LoopStepResult:
 """Step 1: compat delegate → ``steps.validate.run_validate_step``."""
 step_result, _ = run_validate_step(jd_text, target_position)
 return step_result

 def _resolve_target_position(self, requested: str | None, extraction_data: dict[str, Any]) -> str | None:
 """Compat delegate → ``steps.validate.resolve_target_position``."""
 return resolve_target_position(requested, extraction_data)

 async def _step2_extract_skills(self, jd_text: str) -> LoopStepResult:
 """Compat delegate → ``steps.extract.run_extract_step`` ( model_used)."""
 return await run_extract_step(jd_text)

 async def _step3_graph_update(self, run_id: str, extraction_data: dict[str, Any], target_position: str = "") -> LoopStepResult:
 """Compat delegate → ``steps.graph_update.run_graph_update_step`` ."""
 return await run_graph_update_step(run_id=run_id, extraction_data=extraction_data, target_position=target_position)

 async def _step4_match_diagnosis(self, target_position: str, extracted_skills: list[dict[str, Any]], graph_available: bool, driver: Any = None, db_session: Any = None) -> LoopStepResult:
 """Compat delegate → ``steps.match.run_match_step`` ( score_breakdown)."""
 return await run_match_step(target_position=target_position, extracted_skills=extracted_skills,
 graph_available=graph_available, driver=driver, db_session=db_session)

 async def _step5_learning_path(self, match_result: dict[str, Any], graph_available: bool, match_ok: bool,
 session: AsyncSession | None = None, target_position: str = "") -> LoopStepResult:
 """Compat delegate → ``steps.learning_path.run_learning_path_step`` ."""
 return await run_learning_path_step(match_result=match_result, match_ok=match_ok,
 target_position=target_position, session=session, graph_available=graph_available)

 @staticmethod
 def _generic_learning_path -> dict[str, Any]:
 """Compat shim → ``steps.learning_path.generic_learning_path``."""
 return generic_learning_path

 # ---- Persistence helper delegates (compat shell) ----

 @staticmethod
 async def _insert_loop_run(run_id: str, session: AsyncSession | None = None, user_id: str = "system") -> LoopResultRecord | None:
 return await _insert_loop_run(run_id, session=session, user_id=user_id)

 @staticmethod
 async def _update_steps_json(db_record: LoopResultRecord | None, result: LoopResult, session: AsyncSession | None = None) -> None:
 await _update_steps_json(db_record, result, session=session)

 @staticmethod
 async def _complete_loop_run(db_record: LoopResultRecord | None, result: LoopResult, session: AsyncSession | None = None) -> None:
 await _complete_loop_run(db_record, result, session=session)

# ---- Module-level helpers re-export (compat shim — ) ----
from app.core.pipeline.loop.status import get_loop_history, get_loop_status, _build_loop_verification, _loop_step_checks # noqa: E402, F401, I001
