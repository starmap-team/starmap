"""Learning plan service — auto-generates learning plans from match diagnosis.

Provides:
  - create_plan_from_match: Convert match diagnosis results into a persisted LearningPlan
  - Auto-integrates with the loop orchestrator's Step 5 for seamless pipeline flow
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.learning.path_engine import generate_learning_path
from app.core.learning.progress_tracker import create_plan
from app.services.match_service import PREREQUISITE_MAP


async def create_plan_from_match(
    session: AsyncSession,
    *,
    target_position: str,
    match_result: dict[str, Any],
    user_id: str = "anonymous",
    available_hours_per_week: float = 10.0,
) -> dict[str, Any]:
    """Auto-generate a learning plan from match diagnosis results.

    Extracts skill gaps from the match result, enriches them with
    prerequisite-aware learning paths and time estimates, then persists
    a LearningPlan + LearningProgress records.

    Args:
        session: Async DB session.
        target_position: The position that was matched against.
        match_result: Full result from match_service.run_match (or loop Step 4).
        user_id: Optional user identifier.
        available_hours_per_week: Weekly hours available for learning.

    Returns:
        Dict with plan_id, position, total_hours, phase_count, skills count.

    Raises:
        ValueError: If match_result has no skill gaps.
    """
    gap_details = match_result.get("skill_gap_detail", [])
    if not gap_details:
        msg = f"No skill gaps in match result for '{target_position}'"
        raise ValueError(msg)

    # Filter to only gap skills (not already mastered)
    skill_gaps = [
        {
            "skill": g["skill"],
            "importance": g.get("importance", "required"),
            "gap_level": g.get("gap_level", "完全缺失"),
            "learning_path": g.get("learning_path", []),
            "target_proficiency": "熟悉",
        }
        for g in gap_details
        if g.get("gap_level") != "已掌握"
    ]

    if not skill_gaps:
        logger.info("No skill gaps to learn for '{}' — all skills mastered", target_position)
        return {
            "plan_id": None,
            "position": target_position,
            "status": "no_gaps",
            "message": "所有技能已掌握，无需学习计划",
        }

    # Generate structured learning path with time estimates
    learning_path = await generate_learning_path(
        match_gaps=skill_gaps,
        prerequisites=PREREQUISITE_MAP,
        available_time=available_hours_per_week,
    )

    # Enrich skill data with estimated hours
    enriched_skills = []
    path_hours_map = {s.name: s.estimated_hours for s in learning_path.skills}
    for gap in skill_gaps:
        gap["estimated_hours"] = path_hours_map.get(gap["skill"], 0.0)
        enriched_skills.append(gap)

    # Persist as a LearningPlan
    match_score = match_result.get("match_score", 0.0)
    plan = await create_plan(
        session,
        position=target_position,
        skills=enriched_skills,
        user_id=user_id,
        match_score=match_score,
        estimated_hours=learning_path.total_hours,
    )

    logger.info(
        "Auto-created learning plan {} for '{}': {} skills, {:.0f}h total",
        plan.id,
        target_position,
        len(enriched_skills),
        learning_path.total_hours,
    )

    return {
        "plan_id": str(plan.id),
        "position": target_position,
        "status": plan.status,
        "total_skills": len(enriched_skills),
        "total_hours": learning_path.total_hours,
        "total_weeks": learning_path.total_weeks,
        "phase_count": learning_path.phase_count,
        "match_score": match_score,
    }
