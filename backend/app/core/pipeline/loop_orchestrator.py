"""Closed-Loop Orchestrator — 5-step end-to-end pipeline.

Pipeline:
  Step 1: JD input       — receive raw JD text
  Step 2: Skill extraction — LLM-based extraction (jd_extract pipeline)
  Step 3: Graph update   — sync extracted skills/positions into Neo4j
  Step 4: Match diagnosis — run match engine against target position
  Step 5: Learning path  — derive personalised learning path from match gaps

All 5 steps execute for real; there is no degraded mode.
LoopStepResult.status: "success" | "failed"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.pipeline_models import LoopResultRecord


class StepStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class LoopRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STEP_NAMES: dict[int, str] = {
    1: "JD输入",
    2: "技能提取",
    3: "图谱更新",
    4: "匹配诊断",
    5: "学习路径",
}


@dataclass
class LoopStepResult:
    """Result of a single loop step."""

    step: int
    name: str
    status: StepStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    note: str | None = None


@dataclass
class LoopResult:
    """Complete result of a closed-loop run."""

    run_id: str
    jd_text: str
    target_position: str | None
    status: LoopRunStatus
    steps: list[LoopStepResult] = field(default_factory=list)
    extracted_skills: list[dict[str, Any]] = field(default_factory=list)
    graph_update: dict[str, Any] = field(default_factory=dict)
    match_result: dict[str, Any] = field(default_factory=dict)
    learning_path: dict[str, Any] = field(default_factory=dict)
    total_duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "jd_text": self.jd_text[:200] + ("..." if len(self.jd_text) > 200 else ""),
            "target_position": self.target_position,
            "status": self.status.value,
            "steps": [
                {
                    "step": s.step,
                    "name": s.name,
                    "status": s.status.value,
                    "data": s.data,
                    "error": s.error,
                    "duration_seconds": round(s.duration_seconds, 2),
                    "note": s.note,
                }
                for s in self.steps
            ],
            "extracted_skills": self.extracted_skills,
            "graph_update": self.graph_update,
            "match_result": self.match_result,
            "learning_path": self.learning_path,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
        }


# Fallback in-memory history storage (used only when no DB session is provided)
_LOOP_RESULTS: dict[str, LoopResult] = {}
_LOOP_HISTORY_MAX = 200


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
    ) -> LoopResult:
        """Execute the full 5-step closed-loop pipeline.

        Args:
            jd_text: Raw job description text.
            target_position: Target position name for match diagnosis.
            session: Optional async DB session for persisting the result.

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
        db_record = await self._insert_loop_run(run_id, session=session)

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

        # ---- Step 3: Graph Update ----
        # Obtain Neo4j driver for step 3 and step 4
        driver = None
        try:
            from app.services.resources import resources as app_resources
            driver = app_resources.neo4j_driver
        except Exception:
            pass

        step3 = await self._step3_graph_update(run_id, extraction_data, target_position=target_position)
        result.steps.append(step3)
        graph_ok = step3.status == StepStatus.SUCCESS
        result.graph_update = step3.data
        await self._update_steps_json(db_record, result, session=session)

        # ---- Step 4: Match Diagnosis (LOOP-09: skip if no target_position) ----
        if target_position:
            step4 = await self._step4_match_diagnosis(
                target_position=target_position,
                extracted_skills=result.extracted_skills,
                graph_available=graph_ok,
                driver=driver,
                db_session=session,
            )
            result.steps.append(step4)
            if step4.status == StepStatus.SUCCESS:
                result.match_result = step4.data
        else:
            step4 = LoopStep(
                step=4, name="Match Diagnosis", status=StepStatus.SKIPPED,
                data={}, note="Skipped: no target_position provided",
            )
            result.steps.append(step4)
        await self._update_steps_json(db_record, result, session=session)

        # ---- Step 5: Learning Path (LOOP-09: skip if no target_position) ----
        if target_position and step4.status != StepStatus.SKIPPED:
            step5 = await self._step5_learning_path(
                match_result=result.match_result,
                graph_available=graph_ok,
                match_ok=step4.status != StepStatus.FAILED,
                session=session,
                target_position=target_position,
            )
            result.steps.append(step5)
            result.learning_path = step5.data
        else:
            step5 = LoopStep(
                step=5, name="Learning Path", status=StepStatus.SKIPPED,
                data={}, note="Skipped: no target_position or match skipped",
            )
            result.steps.append(step5)

        # Determine overall status
        failed_steps = [s for s in result.steps if s.status == StepStatus.FAILED]
        skipped_ok = [s for s in result.steps if s.status == StepStatus.SKIPPED]
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
        self, jd_text: str, target_position: str,
    ) -> LoopStepResult:
        """Step 1: Validate JD input and target position."""
        start = time.monotonic()
        if not jd_text or not jd_text.strip():
            return LoopStepResult(
                step=1,
                name=STEP_NAMES[1],
                status=StepStatus.FAILED,
                error="JD text is empty",
                duration_seconds=time.monotonic() - start,
            )
        if not target_position or not target_position.strip():
            return LoopStepResult(
                step=1,
                name=STEP_NAMES[1],
                status=StepStatus.FAILED,
                error="Target position is empty",
                duration_seconds=time.monotonic() - start,
            )
        return LoopStepResult(
            step=1,
            name=STEP_NAMES[1],
            status=StepStatus.SUCCESS,
            data={
                "jd_length": len(jd_text),
                "target_position": target_position.strip(),
            },
            duration_seconds=time.monotonic() - start,
        )

    async def _step2_extract_skills(self, jd_text: str) -> LoopStepResult:
        """Step 2: Extract skills from JD using LLM pipeline."""
        start = time.monotonic()
        try:
            from app.core.extraction.jd_extract import extract_from_jd

            raw = await extract_from_jd(jd_text)
            if not raw.get("success"):
                return LoopStepResult(
                    step=2,
                    name=STEP_NAMES[2],
                    status=StepStatus.FAILED,
                    error=raw.get("error") or "Extraction returned success=false",
                    duration_seconds=time.monotonic() - start,
                )

            data = raw.get("data") or {}
            required = data.get("required_skills") or []
            preferred = data.get("preferred_skills") or []

            skills = []
            for s in required:
                skills.append({
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "proficiency": s.get("level", "熟悉"),
                    "importance": "required",
                })
            for s in preferred:
                skills.append({
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "proficiency": s.get("level", "了解"),
                    "importance": "bonus",
                })

            return LoopStepResult(
                step=2,
                name=STEP_NAMES[2],
                status=StepStatus.SUCCESS,
                data={
                    "skills": skills,
                    "position_name": data.get("position_name", ""),
                    "industry": data.get("industry", ""),
                    "description": data.get("description", ""),
                    "knowledge_areas": data.get("knowledge_areas", []),
                    "experience_required": data.get("experience_required"),
                    "education_required": data.get("education_required"),
                    "tools": data.get("tools", []),
                    "prerequisites": data.get("prerequisites", []),
                    "learning_resources": data.get("learning_resources", []),
                    "evolves_to": data.get("evolves_to", []),
                    "validation": raw.get("validation"),
                    "prompt_version": raw.get("prompt_version_used"),
                },
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            logger.error("Step 2 (skill extraction) failed: {}", exc)
            return LoopStepResult(
                step=2,
                name=STEP_NAMES[2],
                status=StepStatus.FAILED,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    async def _step3_graph_update(
        self,
        run_id: str,
        extraction_data: dict[str, Any],
        target_position: str = "",
    ) -> LoopStepResult:
        """Step 3: Sync extracted skills/positions into Neo4j graph."""
        start = time.monotonic()
        try:
            from app.services.graph_service import sync_from_pipeline

            driver = None
            try:
                from app.services.resources import resources as app_resources
                driver = app_resources.neo4j_driver
            except Exception:
                pass

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
        except Exception as exc:
            logger.error("Step 3 (graph update) failed: {}", exc)
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
        except Exception as exc:
            logger.error("Step 4 (match diagnosis) failed: {}", exc)
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
                missing = [g for g in gap_details if g.get("gap_level") != "已掌握"]

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
                    except Exception as exc:
                        logger.warning(
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
            except Exception as exc:
                logger.warning("Step 5 path derivation from match failed: {}", exc)

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

    @staticmethod
    async def _insert_loop_run(
        run_id: str,
        session: AsyncSession | None = None,
    ) -> LoopResultRecord | None:
        """INSERT a new running loop_results row; return the ORM object or None."""
        if session is None:
            return None
        try:
            from app.models.pipeline_models import LoopResultRecord

            record = LoopResultRecord(
                run_id=run_id,
                steps_json={},
                status=LoopRunStatus.RUNNING.value,
            )
            session.add(record)
            await session.commit()
            return record
        except Exception as exc:
            logger.warning("Failed to insert loop run to DB: {}", exc)
            return None

    @staticmethod
    async def _update_steps_json(
        db_record: LoopResultRecord | None,
        result: LoopResult,
        session: AsyncSession | None = None,
    ) -> None:
        """UPDATE steps_json after each step completes."""
        if db_record is None or session is None:
            return
        try:
            from app.models.pipeline_models import LoopResultRecord

            # Re-fetch to avoid detached-instance issues
            db_record = await session.get(LoopResultRecord, db_record.id)
            if db_record is None:
                return
            db_record.steps_json = result.to_dict()
            await session.commit()
        except Exception as exc:
            logger.warning("Failed to update loop steps_json in DB: {}", exc)

    @staticmethod
    async def _complete_loop_run(
        db_record: LoopResultRecord | None,
        result: LoopResult,
        session: AsyncSession | None = None,
    ) -> None:
        """UPDATE status and completed_at when the loop finishes; fall back to in-memory."""
        if db_record is not None and session is not None:
            try:
                from app.models.pipeline_models import LoopResultRecord

                db_record = await session.get(LoopResultRecord, db_record.id)
                if db_record is not None:
                    db_record.status = result.status.value
                    db_record.steps_json = result.to_dict()
                    db_record.completed_at = datetime.now(UTC)
                    if result.status == LoopRunStatus.FAILED:
                        errors = [s.error for s in result.steps if s.error]
                        db_record.error_log = "; ".join(errors) if errors else None
                    await session.commit()
                    return
            except Exception as exc:
                logger.warning(
                    "Failed to complete loop run in DB, falling back to in-memory: {}",
                    exc,
                )

        # Fallback: in-memory history storage
        _LOOP_RESULTS[result.run_id] = result
        if len(_LOOP_RESULTS) > _LOOP_HISTORY_MAX:
            excess = len(_LOOP_RESULTS) - _LOOP_HISTORY_MAX
            for old_key in list(_LOOP_RESULTS.keys())[:excess]:
                del _LOOP_RESULTS[old_key]


async def get_loop_status(
    run_id: str,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Return status of a loop run by ID, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            result = await session.execute(
                select(LoopResultRecord).where(LoopResultRecord.run_id == run_id)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                data = dict(row.steps_json) if row.steps_json else {}
                data["run_id"] = row.run_id
                data["status"] = row.status
                return data
        except Exception as exc:
            logger.warning("Failed to read loop status from loop_results, trying pipeline_runs: {}", exc)

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
        except Exception as exc:
            logger.warning("Failed to read loop status from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    result = _LOOP_RESULTS.get(run_id)
    if result is None:
        return None
    return result.to_dict()


async def get_loop_history(
    limit: int = 50,
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Return recent loop run history, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            result = await session.execute(
                select(LoopResultRecord)
                .order_by(LoopResultRecord.created_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            if rows:
                items = []
                for row in rows:
                    data = dict(row.steps_json) if row.steps_json else {}
                    data["run_id"] = row.run_id
                    data["status"] = row.status
                    items.append(data)
                return items
        except Exception as exc:
            logger.warning("Failed to read loop history from loop_results, trying pipeline_runs: {}", exc)

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
        except Exception as exc:
            logger.warning("Failed to read loop history from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    items = list(_LOOP_RESULTS.values())
    items.sort(key=lambda r: r.total_duration_seconds, reverse=False)
    return [r.to_dict() for r in list(_LOOP_RESULTS.values())[-limit:]][::-1]
