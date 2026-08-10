"""Learning plan service — auto-generates learning plans from match diagnosis.

Provides:
  - create_plan_from_match: Convert match diagnosis results into a persisted LearningPlan
  - Auto-integrates with the loop orchestrator's Step 5 for seamless pipeline flow
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PROFICIENCY, GAP_LEVEL_MASTERED, GAP_LEVEL_MISSING
from app.core.learning.path_engine import generate_learning_path
from app.core.learning.progress_tracker import create_plan, get_progress, update_progress
from app.exceptions import PlanNotFoundError, PlanOwnershipError
from app.models.learning_models import LearningPlan
from app.services.match_service import PREREQUISITE_MAP, ensure_prerequisite_map


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
            "gap_level": g.get("gap_level", GAP_LEVEL_MISSING),
            "learning_path": g.get("learning_path", []),
            "target_proficiency": DEFAULT_PROFICIENCY,
        }
        for g in gap_details
        if g.get("gap_level") != GAP_LEVEL_MASTERED
    ]

    if not skill_gaps:
        logger.info("No skill gaps to learn for '{}' — all skills mastered", target_position)
        return {
            "plan_id": None,
            "position": target_position,
            "status": "no_gaps",
            "message": "所有技能已掌握，无需学习计划",
        }

    # NEW-03: 确保前置关系已从 Neo4j 加载（不可用时降级为空）
    await ensure_prerequisite_map()

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


# ─── 学习中心 plan CRUD(layer_boundary 重构:业务逻辑下沉,路由只编排)───


async def _build_plan_view(session: AsyncSession, plan: LearningPlan) -> dict[str, Any]:
    """组装单个计划的完整视图(progress + 学习路径),返回 PlanResponse 所需字段。

    学习路径生成失败时降级到计划自身估时(M3),不让单个计划拖垮整个响应。
    """
    progress_data = await get_progress(session, plan_id=plan.id)

    skill_gaps: list[Any] = plan.skills if isinstance(plan.skills, list) else []
    if skill_gaps:
        try:
            path = await generate_learning_path(match_gaps=skill_gaps, available_time=10.0)
            total_hours = path.total_hours
            total_weeks = path.total_weeks
            phases = list(path.phases)
            phase_count = path.phase_count
        except Exception as exc:  # noqa: BLE001
            logger.warning("Learning path generation failed for plan {}, degrading: {}", plan.id, exc)
            total_hours = plan.estimated_hours
            total_weeks = 0
            phases = []
            phase_count = 0
    else:
        total_hours = plan.estimated_hours
        total_weeks = 0
        phases = []
        phase_count = 0

    return {
        "plan_id": str(plan.id),
        "position": plan.position,
        "status": plan.status,
        "match_score_at_creation": plan.match_score_at_creation,
        "overall_pct": progress_data.get("overall_pct", 0.0),
        "total_hours": total_hours,
        "total_weeks": total_weeks,
        "phase_count": phase_count,
        "phases": phases,
        "skills": progress_data.get("skills", []),
        "stats": progress_data.get("stats", {}),
    }


async def list_plans_for_user(
    session: AsyncSession, user_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    """列出用户全部学习计划(最新优先),每个含进度与路径视图。"""
    stmt = (
        sa.select(LearningPlan)
        .where(LearningPlan.user_id == user_id)
        .order_by(LearningPlan.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    plans = result.scalars().all()
    return [await _build_plan_view(session, plan) for plan in plans]


async def create_plan_from_diagnosis(
    session: AsyncSession,
    *,
    user_id: str,
    position: str,
    skill_gaps: list[dict[str, Any]],
    match_score: float = 0.0,
    available_hours_per_week: float = 10.0,
) -> dict[str, Any]:
    """从技能差距创建学习计划,返回完整视图。"""
    # NEW-03: 确保前置关系已从 Neo4j 加载（不可用时降级为空）
    await ensure_prerequisite_map()

    learning_path = await generate_learning_path(
        match_gaps=skill_gaps,
        prerequisites=PREREQUISITE_MAP,
        available_time=available_hours_per_week,
    )

    # 用路径引擎的小时数富化技能数据
    enriched_skills = []
    path_hours_map = {s.name: s.estimated_hours for s in learning_path.skills}
    for gap in skill_gaps:
        gap["estimated_hours"] = path_hours_map.get(gap["skill"], 0.0)
        enriched_skills.append(gap)

    plan = await create_plan(
        session,
        position=position,
        skills=enriched_skills,
        match_score=match_score,
        estimated_hours=learning_path.total_hours,
        user_id=user_id,
    )

    progress_data = await get_progress(session, plan_id=plan.id)
    return {
        "plan_id": str(plan.id),
        "position": plan.position,
        "status": plan.status,
        "match_score_at_creation": plan.match_score_at_creation,
        "overall_pct": progress_data.get("overall_pct", 0.0),
        "total_hours": learning_path.total_hours,
        "total_weeks": learning_path.total_weeks,
        "phase_count": learning_path.phase_count,
        "phases": list(learning_path.phases),
        "skills": progress_data.get("skills", []),
        "stats": progress_data.get("stats", {}),
    }


async def get_plan_for_user(
    session: AsyncSession, *, user_id: str, plan_id: uuid.UUID
) -> dict[str, Any]:
    """获取单个计划视图;计划不存在抛 PlanNotFoundError,非本人抛 PlanOwnershipError。"""
    progress_data = await get_progress(session, plan_id=plan_id)
    if "error" in progress_data:
        raise PlanNotFoundError(plan_id=str(plan_id))

    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == plan_id)
    plan = (await session.execute(plan_stmt)).scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError(plan_id=str(plan_id))
    # AUTHZ-02: IDOR 校验 — 用户只能访问自己的计划
    if plan.user_id != user_id:
        raise PlanOwnershipError(plan_id=str(plan_id), user_id=user_id)

    return await _build_plan_view(session, plan)


async def update_skill_progress_for_user(
    session: AsyncSession,
    *,
    user_id: str,
    plan_id: uuid.UUID,
    skill_name: str,
    status: str | None = None,
    progress_pct: float | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """更新某技能进度;计划不存在/非本人抛域异常;技能不在计划内返回 None。"""
    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == plan_id)
    plan = (await session.execute(plan_stmt)).scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError(plan_id=str(plan_id))
    if plan.user_id != user_id:
        raise PlanOwnershipError(plan_id=str(plan_id), user_id=user_id)

    progress = await update_progress(
        session,
        plan_id=plan_id,
        skill_name=skill_name,
        status=status,
        progress_pct=progress_pct,
        notes=notes,
    )
    if progress is None:
        return None
    return {
        "skill_name": progress.skill_name,
        "status": progress.status,
        "progress_pct": round(progress.progress_pct, 1),
        "importance": progress.importance,
        "estimated_hours": progress.estimated_hours,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
        "notes": progress.notes,
    }
