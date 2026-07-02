"""Closed-Loop Orchestrator — 5-step end-to-end pipeline.

Pipeline:
  Step 1: JD input       — receive raw JD text
  Step 2: Skill extraction — LLM-based extraction (jd_extract pipeline)
  Step 3: Graph update   — sync extracted skills/positions into Neo4j
  Step 4: Match diagnosis — run match engine against target position
  Step 5: Learning path  — derive personalised learning path from match gaps

Error Isolation Strategy (degraded mode):
  - Each step wrapped in independent try/except
  - Step 3 failure  -> Steps 4-5 use existing graph data (marked "based on historical graph")
  - Step 4 failure  -> Step 5 uses generic learning path
  - LoopStepResult.status: "success" | "degraded" | "failed"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger


class StepStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class LoopRunStatus(str, Enum):
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
    target_position: str
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


# In-memory history storage (matches the pattern of match_service._MATCH_RESULTS)
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

    async def run_loop(self, jd_text: str, target_position: str) -> LoopResult:
        """Execute the full 5-step closed-loop pipeline.

        Args:
            jd_text: Raw job description text.
            target_position: Target position name for match diagnosis.

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

        # ---- Step 1: JD Input (validation) ----
        step1 = self._step1_validate_input(jd_text, target_position)
        result.steps.append(step1)
        if step1.status == StepStatus.FAILED:
            result.status = LoopRunStatus.FAILED
            result.total_duration_seconds = time.monotonic() - start
            self._store_result(result)
            return result

        # ---- Step 2: Skill Extraction ----
        step2 = await self._step2_extract_skills(jd_text)
        result.steps.append(step2)
        extraction_data: dict[str, Any] = {}
        if step2.status == StepStatus.SUCCESS:
            extraction_data = step2.data
            result.extracted_skills = extraction_data.get("skills", [])

        # ---- Step 3: Graph Update ----
        step3 = await self._step3_graph_update(run_id, extraction_data)
        result.steps.append(step3)
        graph_ok = step3.status == StepStatus.SUCCESS
        result.graph_update = step3.data

        # ---- Step 4: Match Diagnosis ----
        step4 = await self._step4_match_diagnosis(
            target_position=target_position,
            extracted_skills=result.extracted_skills,
            graph_available=graph_ok,
        )
        result.steps.append(step4)
        if step4.status == StepStatus.SUCCESS:
            result.match_result = step4.data

        # ---- Step 5: Learning Path ----
        step5 = self._step5_learning_path(
            match_result=result.match_result,
            graph_available=graph_ok,
            match_ok=step4.status != StepStatus.FAILED,
        )
        result.steps.append(step5)
        result.learning_path = step5.data

        # Determine overall status
        failed_steps = [s for s in result.steps if s.status == StepStatus.FAILED]
        degraded_steps = [s for s in result.steps if s.status == StepStatus.DEGRADED]
        if failed_steps and all(s.step in (4, 5) for s in failed_steps):
            # Only path/match failed — pipeline is still degraded
            result.status = LoopRunStatus.COMPLETED
        elif len(failed_steps) >= 3:
            result.status = LoopRunStatus.FAILED
        elif degraded_steps or failed_steps:
            result.status = LoopRunStatus.COMPLETED
        else:
            result.status = LoopRunStatus.COMPLETED

        result.total_duration_seconds = time.monotonic() - start
        self._store_result(result)

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
    ) -> LoopStepResult:
        """Step 3: Sync extracted skills/positions into Neo4j graph."""
        start = time.monotonic()
        try:
            from app.services.graph_service import add_node, sync_from_pipeline
            from app.services.resources import AppResources

            driver = AppResources.neo4j_driver
            if driver is None:
                return LoopStepResult(
                    step=3,
                    name=STEP_NAMES[3],
                    status=StepStatus.DEGRADED,
                    data={"error": "neo4j_driver_unavailable"},
                    note="Neo4j driver not available, using historical graph data",
                    duration_seconds=time.monotonic() - start,
                )

            skills = extraction_data.get("skills", [])
            position_name = extraction_data.get("position_name", "")

            new_positions = []
            if position_name:
                new_positions.append({
                    "name": position_name,
                    "industry": extraction_data.get("industry", ""),
                    "description": "",
                })

            new_skills = [
                {"name": s["name"], "category": s.get("category", "hard_skill"), "source_count": 1}
                for s in skills
                if s.get("name")
            ]

            new_edges = [
                {"position_name": position_name, "skill_name": s["name"], "level": s.get("proficiency", "熟悉"), "required": s.get("importance") == "required"}
                for s in skills
                if s.get("name") and position_name
            ]

            sync_result = await sync_from_pipeline(
                driver=driver,
                pipeline_run_id=run_id,
                new_positions=new_positions,
                new_skills=new_skills,
                new_edges=new_edges,
            )

            if sync_result.get("error"):
                return LoopStepResult(
                    step=3,
                    name=STEP_NAMES[3],
                    status=StepStatus.DEGRADED,
                    data=sync_result,
                    note="Graph sync had errors, using historical graph data",
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
                status=StepStatus.DEGRADED,
                data={"error": str(exc)},
                note="Graph update failed, using historical graph data",
                duration_seconds=time.monotonic() - start,
            )

    async def _step4_match_diagnosis(
        self,
        target_position: str,
        extracted_skills: list[dict[str, Any]],
        graph_available: bool,
    ) -> LoopStepResult:
        """Step 4: Run match diagnosis with extracted skills vs target position."""
        start = time.monotonic()
        note = None
        if not graph_available:
            note = "基于历史图谱，新增节点未纳入"

        if not extracted_skills:
            return LoopStepResult(
                step=4,
                name=STEP_NAMES[4],
                status=StepStatus.FAILED,
                error="No skills available for matching",
                note=note,
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
            )

            status = StepStatus.SUCCESS if not note else StepStatus.DEGRADED
            return LoopStepResult(
                step=4,
                name=STEP_NAMES[4],
                status=status,
                data=match_result,
                note=note,
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            logger.error("Step 4 (match diagnosis) failed: {}", exc)
            return LoopStepResult(
                step=4,
                name=STEP_NAMES[4],
                status=StepStatus.FAILED,
                error=str(exc),
                note=note,
                duration_seconds=time.monotonic() - start,
            )

    def _step5_learning_path(
        self,
        match_result: dict[str, Any],
        graph_available: bool,
        match_ok: bool,
    ) -> LoopStepResult:
        """Step 5: Derive learning path from match gaps."""
        start = time.monotonic()
        note_parts: list[str] = []
        if not graph_available:
            note_parts.append("基于历史图谱，新增节点未纳入")
        note = "; ".join(note_parts) if note_parts else None

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

                return LoopStepResult(
                    step=5,
                    name=STEP_NAMES[5],
                    status=StepStatus.DEGRADED if note else StepStatus.SUCCESS,
                    data={
                        "path_items": path_items,
                        "estimated_learning_time": match_result.get("estimated_learning_time", ""),
                        "overall_assessment": match_result.get("overall_assessment", ""),
                        "recommendations": match_result.get("recommendations", []),
                        "source": "match_gaps",
                    },
                    note=note,
                    duration_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                logger.warning("Step 5 path derivation from match failed, using generic: {}", exc)

        # Fallback: generic learning path
        return LoopStepResult(
            step=5,
            name=STEP_NAMES[5],
            status=StepStatus.DEGRADED,
            data=self._generic_learning_path(),
            note="匹配诊断不可用，使用通用学习路径",
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
    # History / status helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _store_result(result: LoopResult) -> None:
        _LOOP_RESULTS[result.run_id] = result
        if len(_LOOP_RESULTS) > _LOOP_HISTORY_MAX:
            excess = len(_LOOP_RESULTS) - _LOOP_HISTORY_MAX
            for old_key in list(_LOOP_RESULTS.keys())[:excess]:
                del _LOOP_RESULTS[old_key]


async def get_loop_status(run_id: str) -> dict[str, Any] | None:
    """Return status of a loop run by ID."""
    result = _LOOP_RESULTS.get(run_id)
    if result is None:
        return None
    return result.to_dict()


async def get_loop_history(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent loop run history."""
    items = list(_LOOP_RESULTS.values())
    items.sort(key=lambda r: r.total_duration_seconds, reverse=False)
    # Return most recent first (insertion order in dict preserves recency)
    return [r.to_dict() for r in list(_LOOP_RESULTS.values())[-limit:]][::-1]
