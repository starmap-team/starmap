"""Learning progress tracking module.

Manages learning plans and per-skill progress updates using async SQLAlchemy.
Provides CRUD operations for plans and progress records, plus aggregation
queries for overall progress reporting.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning_models import LearningPlan, LearningProgress


async def create_plan(
    session: AsyncSession,
    *,
    position: str,
    skills: list[dict[str, Any]],
    user_id: str = "anonymous",
    match_score: float = 0.0,
    estimated_hours: float = 0.0,
) -> LearningPlan:
    """Create a new learning plan with initial skill progress records.

    Args:
        session: Async database session.
        position: Target position name.
        skills: List of skill dicts from match diagnosis, each with:
            - skill: str
            - importance: str (required|bonus)
            - gap_level: str
            - learning_path: list[str]
            - estimated_hours: float (optional)
        user_id: User identifier.
        match_score: Match score at plan creation time.
        estimated_hours: Total estimated learning hours.

    Returns:
        The created LearningPlan.
    """
    plan = LearningPlan(
        user_id=user_id,
        position=position,
        skills=skills,
        status="active",
        match_score_at_creation=match_score,
        estimated_hours=estimated_hours,
    )
    session.add(plan)
    await session.flush()  # Get the plan ID

    # Create progress records for each skill
    for skill_data in skills:
        skill_name = skill_data.get("skill", "")
        if not skill_name:
            continue

        gap_level = skill_data.get("gap_level", "完全缺失")
        importance = skill_data.get("importance", "required")
        hours = skill_data.get("estimated_hours", 0.0)

        # Determine initial status from gap level
        if gap_level == "已掌握":
            initial_status = "mastered"
            initial_pct = 100.0
        elif gap_level == "部分掌握":
            initial_status = "not_started"
            initial_pct = 0.0
        else:
            initial_status = "not_started"
            initial_pct = 0.0

        progress = LearningProgress(
            plan_id=plan.id,
            skill_name=skill_name,
            status=initial_status,
            progress_pct=initial_pct,
            importance=importance,
            estimated_hours=hours,
        )
        session.add(progress)

    await session.commit()
    await session.refresh(plan)

    logger.info(
        "Created learning plan {} for position '{}' with {} skills",
        plan.id, position, len(skills),
    )
    return plan


async def update_progress(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    skill_name: str,
    status: str | None = None,
    progress_pct: float | None = None,
    notes: str | None = None,
) -> LearningProgress | None:
    """Update progress for a specific skill in a learning plan.

    Args:
        session: Async database session.
        plan_id: The learning plan ID.
        skill_name: The skill to update.
        status: New status (not_started/in_progress/mastered). None to keep current.
        progress_pct: New progress percentage (0-100). None to keep current.
        notes: Optional notes to attach.

    Returns:
        Updated LearningProgress, or None if not found.
    """
    stmt = (
        sa.select(LearningProgress)
        .where(
            LearningProgress.plan_id == plan_id,
            LearningProgress.skill_name == skill_name,
        )
    )
    result = await session.execute(stmt)
    progress = result.scalar_one_or_none()

    if progress is None:
        logger.warning(
            "Progress record not found for plan={} skill='{}'",
            plan_id, skill_name,
        )
        return None

    now = datetime.now(UTC)

    if status is not None:
        progress.status = status
        if status == "in_progress" and progress.started_at is None:
            progress.started_at = now
        elif status == "mastered":
            progress.completed_at = now
            progress.progress_pct = 100.0

    if progress_pct is not None:
        progress.progress_pct = max(0.0, min(100.0, progress_pct))
        # Auto-update status based on percentage
        if progress_pct >= 100.0:
            progress.status = "mastered"
            if progress.completed_at is None:
                progress.completed_at = now
        elif progress_pct > 0.0:
            if progress.status == "not_started":
                progress.status = "in_progress"
                if progress.started_at is None:
                    progress.started_at = now

    if notes is not None:
        progress.notes = notes

    progress.updated_at = now

    # Check if all skills are mastered → auto-complete plan
    all_progress = await get_plan_progress_list(session, plan_id=plan_id)
    all_mastered = all(
        p.status == "mastered" or p.progress_pct >= 100.0
        for p in all_progress
    )
    if all_mastered:
        plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == plan_id)
        plan_result = await session.execute(plan_stmt)
        plan = plan_result.scalar_one_or_none()
        if plan and plan.status == "active":
            plan.status = "completed"
            logger.info("Auto-completed learning plan {}", plan_id)

    await session.commit()
    await session.refresh(progress)

    return progress


async def get_plan_progress_list(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
) -> list[LearningProgress]:
    """Get all progress records for a plan."""
    stmt = (
        sa.select(LearningProgress)
        .where(LearningProgress.plan_id == plan_id)
        .order_by(LearningProgress.importance.desc(), LearningProgress.skill_name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_progress(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
) -> dict[str, Any]:
    """Get aggregated progress for a learning plan.

    Returns:
        Dict with:
        - plan_id: str
        - position: str
        - status: str
        - overall_pct: float (weighted average)
        - skills: list of per-skill progress dicts
        - stats: summary statistics
    """
    # Get the plan
    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == plan_id)
    plan_result = await session.execute(plan_stmt)
    plan = plan_result.scalar_one_or_none()

    if plan is None:
        return {"error": "Plan not found"}

    # Get all progress records
    progress_list = await get_plan_progress_list(session, plan_id=plan_id)

    # Calculate overall progress (weighted by importance)
    weight_map = {"required": 2.0, "bonus": 1.0}
    total_weight = 0.0
    weighted_pct = 0.0
    skills_data = []

    for p in progress_list:
        weight = weight_map.get(p.importance, 1.0)
        total_weight += weight
        weighted_pct += p.progress_pct * weight

        skills_data.append({
            "skill_name": p.skill_name,
            "status": p.status,
            "progress_pct": round(p.progress_pct, 1),
            "importance": p.importance,
            "estimated_hours": p.estimated_hours,
            "started_at": p.started_at.isoformat() if p.started_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "notes": p.notes,
        })

    overall_pct = round(weighted_pct / total_weight, 1) if total_weight > 0 else 0.0

    # Stats
    mastered_count = sum(1 for p in progress_list if p.status == "mastered")
    in_progress_count = sum(1 for p in progress_list if p.status == "in_progress")
    not_started_count = sum(1 for p in progress_list if p.status == "not_started")
    required_count = sum(1 for p in progress_list if p.importance == "required")
    required_mastered = sum(
        1 for p in progress_list
        if p.importance == "required" and p.status == "mastered"
    )

    return {
        "plan_id": str(plan_id),
        "position": plan.position,
        "status": plan.status,
        "match_score_at_creation": plan.match_score_at_creation,
        "overall_pct": overall_pct,
        "skills": skills_data,
        "stats": {
            "total_skills": len(progress_list),
            "mastered": mastered_count,
            "in_progress": in_progress_count,
            "not_started": not_started_count,
            "required_total": required_count,
            "required_mastered": required_mastered,
            "estimated_hours_total": plan.estimated_hours,
            "created_at": plan.created_at.isoformat(),
            "updated_at": plan.updated_at.isoformat(),
        },
    }
