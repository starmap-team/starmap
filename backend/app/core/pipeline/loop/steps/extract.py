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
        # 2026-08-26: 补全 trust/hallucination 聚合 — 供前端 LoopStepSkills 卡片展示。
        # hallucination_score = 1 - 幻觉占比(anti_hallucination 校验的 hallucinated_skills);
        # trust_score_avg 取 validation.confidence(模型对抽取的置信度)。
        # 2026-08-27 (BUG#L1): hallucination_score 曾为负数 (如 -700%) ——
        # hallucinated 数量可能超过 total_skills (LLM 把未提取技能也算入),
        # 1 - 8/1 = -7。修复: 分母取 max(total, hallucinated), 结果 clamp [0,1]。
        # 2026-08-27 (BUG#L2 final): LLM 的 hallucinated_skills 语义是
        # "JD 中提及但提取遗漏/多提的技能"(含漏提取, 实测 24 项全是未提取的),
        # 真幻觉应只统计"提取了但 JD 中无依据"的 —— 即 hallucinated ∩ extracted。
        # 漏提取的属于 missing(已有 missing_skills 承载), 不应拉低提取准确度。
        validation = raw.get("validation") or {}
        hallucinated_all = validation.get("hallucinated_skills") or []
        extracted_names = {s.get("name", "").strip().lower() for s in skills if s.get("name")}
        hallucinated = [
            h for h in hallucinated_all
            if str(h).strip().lower() in extracted_names
        ]
        total_skills = len(skills)
        hallucination_score = (
            round(1.0 - len(hallucinated) / total_skills, 4) if total_skills else 1.0
        )
        hallucination_score = max(0.0, min(1.0, hallucination_score))
        trust_score_avg = validation.get("confidence")
        if not isinstance(trust_score_avg, (int, float)):
            trust_score_avg = None
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
                # D-06 / Phase 07-02 D-05: explicit model + aggregate confidence
                "model_used": raw.get("model_used"),
                "skill_count": len(skills),
                "skill_confidence_avg": _avg(confidences),
                # 2026-08-26: 信任度/幻觉评分(前端 LoopStepSkills 卡片)
                "trust_score_avg": trust_score_avg,
                "hallucination_score": hallucination_score,
                "hallucinated_skills": hallucinated,
                "missing_skills": validation.get("missing_skills") or [],
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
