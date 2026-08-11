"""Closed-Loop Orchestrator — 5-step end-to-end pipeline (compat shell).

Pipeline:
  Step 1: JD input       — receive raw JD text
  Step 2: Skill extraction — LLM-based extraction (jd_extract pipeline)
  Step 3: Graph update   — sync extracted skills/positions into Neo4j
  Step 4: Match diagnosis — run match engine against target position
  Step 5: Learning path  — derive personalised learning path from match gaps

All 5 steps execute for real; there is no degraded mode.
LoopStepResult.status: "success" | "failed"

Phase 07-02 (D-01/D-02): this file is now a **compatibility / re-export
shell**. The 5 step implementations live in :mod:`app.core.pipeline.loop.steps`
and the shared types/persistence helpers in :mod:`app.core.pipeline.loop.common`.
``LoopOrchestrator`` keeps every public method so callers stay zero-diff;
each method body delegates to the corresponding ``run_*_step`` function.

New code should import directly from the ``loop`` package.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import GAP_LEVEL_MASTERED
from app.core.pipeline.loop.common import (
    _LOOP_HISTORY_MAX,  # noqa: F401  (re-export for compat tests)
    _LOOP_RESULTS,
    STEP_NAMES,
    LoopResult,
    LoopRunStatus,
    LoopStepResult,
    StepStatus,
    _complete_loop_run,
    _insert_loop_run,
    _update_steps_json,
)
from app.core.pipeline.loop.steps.extract import run_extract_step
from app.exceptions import PipelineStageError, StarMapError

if TYPE_CHECKING:
    from app.models.pipeline_models import LoopResultRecord


# NOTE: ``StepStatus`` / ``LoopRunStatus`` / ``STEP_NAMES`` / ``LoopStepResult``
# / ``LoopResult`` / ``_LOOP_RESULTS`` / ``_LOOP_HISTORY_MAX`` /
# ``_insert_loop_run`` / ``_update_steps_json`` / ``_complete_loop_run`` all
# live in :mod:`app.core.pipeline.loop.common` and are imported at the top of
# this file.  ``from app.core.pipeline.loop_orchestrator import StepStatus``
# resolves to the same StrEnum object.


class LoopOrchestrator:
    """Coordinate the closed-loop end-to-end pipeline.

    Each step is wrapped in independent try/except for error isolation.
    A failure in one step degrades subsequent steps rather than aborting
    the entire pipeline.

    Usage:
        orchestrator = LoopOrchestrator()
        result = await orchestrator.run_loop(
            jd_text="...",
            target_position="Backend Engineer",
        )
    """

    async def run_loop(
        self,
        jd_text: str,
        target_position: str | None,
        session: AsyncSession | None = None,
        user_id: str = "system",  # SEC-04: defaults to "system" for backward compat
    ) -> LoopResult:
        """Execute the full 5-step closed-loop pipeline.

        Args:
            jd_text: Raw job description text.
            target_position: Target position name for match diagnosis.
            session: Optional async DB session for persisting the result.
            user_id: Authenticated user's sub claim (SEC-04).

        Returns:
            LoopResult with all step outputs and aggregate results.
        """
        run_id = str(uuid.uuid4())
        start = time.monotonic()

        result = LoopResult(
            run_id=run_id,
            jd_text=jd_text,
            target_position=target_position,
            status=LoopRunStatus.RUNNING,
        )

        # Insert initial running record into loop_results
        db_record = await self._insert_loop_run(run_id, session=session, user_id=user_id)

        # ---- Step 1: JD Input (validation) ----
        step1 = self._step1_validate_input(jd_text, target_position)
        result.steps.append(step1)
        await self._update_steps_json(db_record, result, session=session)
        if step1.status == StepStatus.FAILED:
            result.status = LoopRunStatus.FAILED
            result.total_duration_seconds = time.monotonic() - start
            await self._complete_loop_run(db_record, result, session=session)
            return result

        # ---- Step 2: Skill Extraction ----
        step2 = await self._step2_extract_skills(jd_text)
        result.steps.append(step2)
        extraction_data: dict[str, Any] = {}
        if step2.status == StepStatus.SUCCESS:
            extraction_data = step2.data
            result.extracted_skills = extraction_data.get("skills", [])
        await self._update_steps_json(db_record, result, session=session)

        # Resolve effective target_position: caller-supplied wins, else infer
        # from extraction. See _resolve_target_position docstring.
        effective_target = self._resolve_target_position(target_position, extraction_data)
        # Reflect resolution into result metadata so frontend can show what was used.
        result.target_position = effective_target

        # ---- Step 3: Graph Update ----
        # Obtain Neo4j driver for step 3 and step 4
        driver = None
        try:
            from app.services.resources import resources as app_resources
            driver = app_resources.neo4j_driver
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.debug("Neo4j driver not available for step 3/4: {}", exc)

        step3 = await self._step3_graph_update(run_id, extraction_data, target_position=effective_target)
        result.steps.append(step3)
        graph_ok = step3.status == StepStatus.SUCCESS
        result.graph_update = step3.data
        await self._update_steps_json(db_record, result, session=session)

        # ---- Step 4: Match Diagnosis (LOOP-09: skip if no effective target_position) ----
        if effective_target:
            step4 = await self._step4_match_diagnosis(
                target_position=effective_target,
                extracted_skills=result.extracted_skills,
                graph_available=graph_ok,
                driver=driver,
                db_session=session,
            )
            result.steps.append(step4)
            if step4.status == StepStatus.SUCCESS:
                result.match_result = step4.data
        else:
            step4 = LoopStepResult(
                step=4, name="Match Diagnosis", status=StepStatus.SKIPPED,
                data={}, note="Skipped: no target_position (caller did not supply and extraction did not yield position_name)",
            )
            result.steps.append(step4)
        await self._update_steps_json(db_record, result, session=session)

        # ---- Step 5: Learning Path (LOOP-09: skip if no effective target_position) ----
        if effective_target and step4.status != StepStatus.SKIPPED:
            step5 = await self._step5_learning_path(
                match_result=result.match_result,
                graph_available=graph_ok,
                match_ok=step4.status != StepStatus.FAILED,
                session=session,
                target_position=effective_target,
            )
            result.steps.append(step5)
            result.learning_path = step5.data
        else:
            step5 = LoopStepResult(
                step=5, name="Learning Path", status=StepStatus.SKIPPED,
                data={}, note="Skipped: no target_position or match skipped",
            )
            result.steps.append(step5)

        # Determine overall status
        failed_steps = [s for s in result.steps if s.status == StepStatus.FAILED]
        if failed_steps and all(s.step in (4, 5) for s in failed_steps):
            # Only path/match failed — pipeline still completed
            result.status = LoopRunStatus.COMPLETED
        elif len(failed_steps) >= 3:
            result.status = LoopRunStatus.FAILED
        else:
            result.status = LoopRunStatus.COMPLETED

        result.total_duration_seconds = time.monotonic() - start
        await self._complete_loop_run(db_record, result, session=session)

        logger.info(
            "Loop {} completed: status={} steps=[{}] duration={:.2f}s",
            run_id,
            result.status.value,
            ", ".join(f"s{s.step}={s.status.value}" for s in result.steps),
            result.total_duration_seconds,
        )
        return result

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _step1_validate_input(
        self, jd_text: str, target_position: str | None,
    ) -> LoopStepResult:
        """Step 1: Validate JD input.

        target_position is optional per the OpenAPI contract
        (LoopRunRequest.target_position: str | None = None). When omitted,
        Step 2 will infer a position_name from the extracted JD; Steps 4/5
        skip when still missing. We must NOT reject the run here — see QA B1.
        """
        start = time.monotonic()
        if not jd_text or not jd_text.strip():
            return LoopStepResult(
                step=1,
                name=STEP_NAMES[1],
                status=StepStatus.FAILED,
                error="JD text is empty",
                duration_seconds=time.monotonic() - start,
            )
        return LoopStepResult(
            step=1,
            name=STEP_NAMES[1],
            status=StepStatus.SUCCESS,
            data={
                "jd_length": len(jd_text),
                "target_position": (target_position or "").strip(),
            },
            duration_seconds=time.monotonic() - start,
        )

    def _resolve_target_position(
        self,
        requested: str | None,
        extraction_data: dict[str, Any],
    ) -> str | None:
        """Resolve the effective target_position for match diagnosis.

        Priority: caller-supplied non-empty value → LLM-extracted position_name → None.
        A None result lets downstream steps skip gracefully (see Step 4/5 in run_loop).
        """
        if requested and requested.strip():
            return requested.strip()
        inferred = (extraction_data or {}).get("position_name")
        if isinstance(inferred, str) and inferred.strip():
            return inferred.strip()
        return None

    async def _step2_extract_skills(self, jd_text: str) -> LoopStepResult:
        """Step 2: Extract skills from JD using LLM pipeline.

        Thin delegate to :func:`app.core.pipeline.loop.steps.extract.run_extract_step`
        (Phase 07-02 D-01). Kept on the class so ``monkeypatch`` paths from
        tests continue to work.
        """
        return await run_extract_step(jd_text)

    async def _step3_graph_update(
        self,
        run_id: str,
        extraction_data: dict[str, Any],
        target_position: str = "",
    ) -> LoopStepResult:
        """Step 3: Sync extracted skills/positions into Neo4j graph."""
        start = time.monotonic()
        try:
            from app.services.graph_sync import sync_from_pipeline

            driver = None
            try:
                from app.services.resources import resources as app_resources
                driver = app_resources.neo4j_driver
            except PipelineStageError:
                raise
            except StarMapError:
                raise
            except Exception as exc:
                logger.debug("Neo4j driver not available inside step 3: {}", exc)

            if driver is None:
                return LoopStepResult(
                    step=3,
                    name=STEP_NAMES[3],
                    status=StepStatus.FAILED,
                    data={"error": "neo4j_driver_unavailable"},
                    error="Neo4j driver not available",
                    duration_seconds=time.monotonic() - start,
                )

            # Phase 2 SYNC-02: Pass extraction_data for DB-query + graph_writer mode
            try:
                sync_result = await sync_from_pipeline(
                    run_id=run_id,
                    extraction_data=extraction_data,
                    target_position=target_position,
                )
            except PipelineStageError:
                raise
            except StarMapError:
                raise
            except Exception as exc:
                logger.warning("sync_from_pipeline failed: {}", exc)
                sync_result = {"synced": False, "error": str(exc)}

            logger.info(
                "Graph sync step for run {}: synced={}, nodes={}, edges={}",
                run_id,
                sync_result.get("synced", False),
                sync_result.get("nodes_written", sync_result.get("nodes", 0)),
                sync_result.get("edges_written", sync_result.get("edges", 0)),
            )

            if not sync_result.get("synced"):
                return LoopStepResult(
                    step=3,
                    name=STEP_NAMES[3],
                    status=StepStatus.FAILED,
                    data=sync_result,
                    error=sync_result.get("error") or "Graph sync failed",
                    duration_seconds=time.monotonic() - start,
                )

            return LoopStepResult(
                step=3,
                name=STEP_NAMES[3],
                status=StepStatus.SUCCESS,
                data=sync_result,
                duration_seconds=time.monotonic() - start,
            )
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Loop orchestrator error: {}", exc)
            return LoopStepResult(
                step=3,
                name=STEP_NAMES[3],
                status=StepStatus.FAILED,
                data={"error": str(exc)},
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    async def _step4_match_diagnosis(
        self,
        target_position: str,
        extracted_skills: list[dict[str, Any]],
        graph_available: bool,
        driver: Any = None,
        db_session: Any = None,
    ) -> LoopStepResult:
        """Step 4: Run match diagnosis with extracted skills vs target position."""
        start = time.monotonic()

        if not extracted_skills:
            return LoopStepResult(
                step=4,
                name=STEP_NAMES[4],
                status=StepStatus.FAILED,
                error="No skills available for matching",
                duration_seconds=time.monotonic() - start,
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
                duration_seconds=time.monotonic() - start,
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
                duration_seconds=time.monotonic() - start,
            )

    async def _step5_learning_path(
        self,
        match_result: dict[str, Any],
        graph_available: bool,
        match_ok: bool,
        session: AsyncSession | None = None,
        target_position: str = "",
    ) -> LoopStepResult:
        """Step 5: Derive learning path from match gaps and auto-create learning plan."""
        start = time.monotonic()

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
                    duration_seconds=time.monotonic() - start,
                )
            except PipelineStageError:
                raise
            except StarMapError:
                raise
            except Exception as exc:
                logger.exception("Step 5 path derivation from match failed: {}", exc)

        # Fallback: generic learning path
        return LoopStepResult(
            step=5,
            name=STEP_NAMES[5],
            status=StepStatus.FAILED,
            error="Match diagnosis not available for learning path generation",
            data=self._generic_learning_path(),
            duration_seconds=time.monotonic() - start,
        )

    @staticmethod
    def _generic_learning_path() -> dict[str, Any]:
        """Return a generic fallback learning path."""
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

    # ------------------------------------------------------------------
    # PostgreSQL persistence helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # PostgreSQL persistence helpers — thin delegates to loop.common
    # ------------------------------------------------------------------

    @staticmethod
    async def _insert_loop_run(
        run_id: str,
        session: AsyncSession | None = None,
        user_id: str = "system",  # SEC-04
    ) -> LoopResultRecord | None:
        """Compat delegate to ``app.core.pipeline.loop.common._insert_loop_run``."""
        return await _insert_loop_run(run_id, session=session, user_id=user_id)

    @staticmethod
    async def _update_steps_json(
        db_record: LoopResultRecord | None,
        result: LoopResult,
        session: AsyncSession | None = None,
    ) -> None:
        """Compat delegate to ``app.core.pipeline.loop.common._update_steps_json``."""
        await _update_steps_json(db_record, result, session=session)

    @staticmethod
    async def _complete_loop_run(
        db_record: LoopResultRecord | None,
        result: LoopResult,
        session: AsyncSession | None = None,
    ) -> None:
        """Compat delegate to ``app.core.pipeline.loop.common._complete_loop_run``."""
        await _complete_loop_run(db_record, result, session=session)


async def get_loop_status(
    run_id: str,
    session: AsyncSession | None = None,
    user_id: str = "system",      # SEC-04
    is_admin: bool = False,        # SEC-04
) -> dict[str, Any] | None:
    """Return status of a loop run by ID, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            query = select(LoopResultRecord).where(
                LoopResultRecord.run_id == run_id,
            )
            # SEC-04: IDOR guard — non-admin users only see their own runs
            if not is_admin:
                query = query.where(LoopResultRecord.user_id == user_id)

            result = await session.execute(query)
            row = result.scalar_one_or_none()
            if row is not None:
                data = dict(row.steps_json) if row.steps_json else {}
                data["run_id"] = row.run_id
                data["status"] = row.status
                return data
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop status from loop_results, trying pipeline_runs: {}", exc)

        # Secondary: query pipeline_runs table (legacy)
        try:
            from app.models.pipeline_models import PipelineRun

            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
            )
            row = result.scalar_one_or_none()
            if row is not None and row.stages is not None:
                data = dict(row.stages)
                data["run_id"] = str(row.id)
                data["status"] = row.status
                if "steps" not in data:
                    data["steps"] = row.stages.get("steps", [])
                return data
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop status from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    result = _LOOP_RESULTS.get(run_id)
    if result is None:
        return None
    return result.to_dict()


async def get_loop_history(
    limit: int = 50,
    session: AsyncSession | None = None,
    user_id: str = "system",      # SEC-04
    is_admin: bool = False,        # SEC-04
) -> list[dict[str, Any]]:
    """Return recent loop run history, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            query = select(LoopResultRecord).order_by(
                LoopResultRecord.created_at.desc()
            )
            # SEC-04: IDOR guard — non-admin users only see their own runs
            if not is_admin:
                query = query.where(LoopResultRecord.user_id == user_id)

            query = query.limit(limit)
            result = await session.execute(query)
            rows = result.scalars().all()
            if rows:
                items = []
                for row in rows:
                    data = dict(row.steps_json) if row.steps_json else {}
                    data["run_id"] = row.run_id
                    data["status"] = row.status
                    items.append(data)
                return items
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop history from loop_results, trying pipeline_runs: {}", exc)

        # Secondary: query pipeline_runs table (legacy)
        try:
            from app.models.pipeline_models import PipelineRun

            result = await session.execute(
                select(PipelineRun)
                .where(PipelineRun.run_type == "loop")
                .order_by(PipelineRun.started_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            if rows:
                items = []
                for row in rows:
                    data = dict(row.stages) if row.stages else {}
                    data["run_id"] = str(row.id)
                    data["status"] = row.status
                    items.append(data)
                return items
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop history from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    items = list(_LOOP_RESULTS.values())
    items.sort(key=lambda r: r.total_duration_seconds, reverse=False)
    return [r.to_dict() for r in list(_LOOP_RESULTS.values())[-limit:]][::-1]


# ---------------------------------------------------------------------------
# Phase 3: 闭环管道逐步核验
# ---------------------------------------------------------------------------

def _build_loop_verification(steps: list[LoopStepResult]) -> dict[str, Any]:
    """为闭环管道构建每步核验摘要。

    Returns:
        {
            "overall_passed": bool,
            "steps": [
                {"step": int, "name": str, "passed": bool, "checks": [...]},
            ]
        }
    """
    step_verifications = []
    for s in steps:
        checks = _loop_step_checks(s)
        step_verifications.append({
            "step": s.step,
            "name": s.name,
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        })
    overall_passed = all(sv["passed"] for sv in step_verifications if sv["checks"])
    return {
        "overall_passed": overall_passed,
        "steps": step_verifications,
    }


def _loop_step_checks(step: LoopStepResult) -> list[dict[str, Any]]:
    """为单个闭环步骤生成验证检查项。"""
    checks: list[dict[str, Any]] = []

    if step.status == StepStatus.FAILED:
        return [{"check": "步骤执行失败", "ok": False, "detail": step.error or "未知错误"}]
    if step.status == StepStatus.SKIPPED:
        return [{"check": "步骤已跳过", "ok": True, "detail": step.note or "无需执行"}]

    # Step 1: JD输入
    if step.step == 1:
        jd_len = step.data.get("jd_length", 0)
        checks.append({
            "check": "JD文本非空",
            "ok": jd_len > 0,
            "detail": f"JD长度: {jd_len} 字符" if jd_len > 0 else "JD为空",
        })
        checks.append({
            "check": "目标岗位已指定",
            "ok": bool(step.data.get("target_position")),
            "detail": f"目标: {step.data.get('target_position')}",
        })

    # Step 2: 技能提取
    elif step.step == 2:
        skills = step.data.get("skills", [])
        checks.append({
            "check": "提取技能数量充足",
            "ok": len(skills) >= 3,
            "detail": f"提取 {len(skills)} 个技能",
        })
        checks.append({
            "check": "岗位名称已识别",
            "ok": bool(step.data.get("position_name")),
            "detail": f"岗位: {step.data.get('position_name', '未识别')}",
        })

    # Step 3: 图谱更新
    elif step.step == 3:
        synced = step.data.get("synced", False)
        checks.append({
            "check": "图谱同步成功",
            "ok": synced,
            "detail": f"写入 {step.data.get('nodes_written', 0)} 节点, {step.data.get('edges_written', 0)} 关系",
        })

    # Step 4: 匹配诊断
    elif step.step == 4:
        match_score = step.data.get("match_score", 0)
        gap_detail = step.data.get("skill_gap_detail", [])
        checks.append({
            "check": "匹配分数合理",
            "ok": match_score > 0,
            "detail": f"匹配度: {match_score:.1%}" if match_score > 0 else "匹配分数为0",
        })
        checks.append({
            "check": "技能差距分析完整",
            "ok": len(gap_detail) > 0,
            "detail": f"分析 {len(gap_detail)} 项技能差距",
        })

    # Step 5: 学习路径
    elif step.step == 5:
        path_items = step.data.get("path_items", [])
        plan_id = step.data.get("plan_id")
        checks.append({
            "check": "学习路径已生成",
            "ok": len(path_items) > 0,
            "detail": f"生成 {len(path_items)} 条学习路径",
        })
        if plan_id:
            checks.append({
                "check": "学习计划已创建",
                "ok": True,
                "detail": f"计划ID: {plan_id}",
            })

    return checks
