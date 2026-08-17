"""Step 2 — Skill Extraction (Phase 07-02 D-01/D-06).

Extracted from ``loop_orchestrator.py._step2_extract_skills``. Behaviour is
unchanged; this module adds explicit ``model_used`` propagation in the
returned ``LoopStepResult.data`` so the frontend can render which LLM was
used (cloud Spark X / DeepSeek vs local ``*-fallback``).
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.core.extraction.industry import normalize_industry
from app.core.pipeline.loop.common import (
    STEP_NAMES,
    LoopStepResult,
    StepStatus,
)
from app.exceptions import PipelineStageError, StarMapError


def _avg(values: list[float | int | None]) -> float | None:
    """Average of non-None numerics, else None — keeps 'honest empty' semantics."""
    cleaned = [v for v in values if isinstance(v, (int, float))]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


async def run_extract_step(jd_text: str) -> LoopStepResult:
    """Step 2: Extract skills from JD using LLM pipeline.

    Args:
        jd_text: Raw job description text.

    Returns:
        LoopStepResult with status SUCCESS / FAILED. On success the ``data``
        dict carries ``skills`` (parsed skills list) and ``model_used``
        (the actual model name reported by ``extract_from_jd``), plus an
        aggregate ``skill_confidence_avg`` if confidence values were
        returned by the extraction backend.
    """
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

        skills: list[dict[str, Any]] = []
        for s in required:
            skills.append({
                "name": s.get("name", ""),
                "category": s.get("category", "hard_skill"),
                "proficiency": s.get("level", "熟悉"),
                "importance": "required",
                "confidence": s.get("confidence"),
            })
        for s in preferred:
            skills.append({
                "name": s.get("name", ""),
                "category": s.get("category", "hard_skill"),
                "proficiency": s.get("level", "了解"),
                "importance": "bonus",
                "confidence": s.get("confidence"),
            })

 # D-06: surface the actual model used + aggregate confidence so the
 # frontend LoopStepSkills card can render a cloud/local explanation.
        confidences = [s.get("confidence") for s in skills]
        return LoopStepResult(
            step=2,
            name=STEP_NAMES[2],
            status=StepStatus.SUCCESS,
            data={
                "skills": skills,
                "position_name": data.get("position_name", ""),
                "industry": normalize_industry(data.get("industry")),
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
 # D-06 / Phase 07-02 D-05: explicit model + aggregate confidence
                "model_used": raw.get("model_used"),
                "skill_count": len(skills),
                "skill_confidence_avg": _avg(confidences),
            },
            duration_seconds=time.monotonic() - start,
        )
    except PipelineStageError:
        raise
    except StarMapError:
        raise
    except Exception as exc:
        logger.error("Step 2 (skill extraction) failed: {}", exc)
        return LoopStepResult(
            step=2,
            name=STEP_NAMES[2],
            status=StepStatus.FAILED,
            error=str(exc),
            duration_seconds=time.monotonic() - start,
        )


__all__ = ["run_extract_step"]
