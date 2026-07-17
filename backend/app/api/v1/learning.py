"""Learning center API.

Endpoints:
- POST /learning/plan              — Create learning plan from match diagnosis
- GET  /learning/plan/{plan_id}    — Get plan details with progress
- PUT  /learning/plan/{plan_id}/progress — Update skill progress
- GET  /learning/recommendations   — Personalized learning recommendations
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.learning.path_engine import generate_learning_path
from app.core.learning.progress_tracker import (
    create_plan,
    get_progress,
    update_progress,
)
from app.dependencies import get_current_user, get_db_session
from app.models.learning_models import LearningPlan, LearningProgress
from app.services.match_service import PREREQUISITE_MAP

router = APIRouter(prefix="/learning", tags=["学习中心"])


# ─── Request / Response Models ───


class SkillGapInput(BaseModel):
    """Skill gap from match diagnosis."""

    skill: str = Field(..., description="技能名称")
    importance: str = Field(default="required", description="required | bonus")
    gap_level: str = Field(default="完全缺失", description="完全缺失 | 部分掌握 | 已掌握")
    learning_path: list[str] = Field(default_factory=list, description="前置技能链")
    target_proficiency: str = Field(default="熟悉", description="目标熟练度")


class CreatePlanRequest(BaseModel):
    """Request to create a learning plan."""

    position: str = Field(..., min_length=1, description="目标岗位")
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="匹配分")
    skills: list[SkillGapInput] = Field(..., min_length=1, description="技能缺口列表")
    available_hours_per_week: float = Field(default=10.0, ge=1.0, le=40.0)


class SkillProgressItem(BaseModel):
    """Per-skill progress in plan response."""

    skill_name: str
    status: str
    progress_pct: float = Field(ge=0.0, le=100.0)
    importance: str = "required"
    estimated_hours: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    notes: str | None = None


class PhaseInfo(BaseModel):
    """Learning phase info."""

    phase: int
    skills: list[str]
    estimated_hours: float
    estimated_weeks: float


class PlanResponse(BaseModel):
    """Learning plan response."""

    plan_id: str
    position: str
    status: str
    match_score_at_creation: float = 0.0
    overall_pct: float = 0.0
    total_hours: float = 0.0
    total_weeks: float = 0.0
    phase_count: int = 0
    phases: list[PhaseInfo] = Field(default_factory=list)
    skills: list[SkillProgressItem] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class UpdateProgressRequest(BaseModel):
    """Request to update skill progress."""

    skill_name: str = Field(..., min_length=1)
    status: str | None = Field(default=None, description="not_started | in_progress | mastered")
    progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    notes: str | None = None


class RecommendationItem(BaseModel):
    """A personalized learning recommendation."""

    skill: str
    importance: str
    gap_level: str
    estimated_hours: float
    prerequisites: list[str] = Field(default_factory=list)
    reason: str


class RecommendationsResponse(BaseModel):
    """Response for personalized recommendations."""

    items: list[RecommendationItem] = Field(default_factory=list)
    total_items: int = 0


# ─── Endpoints ───


@router.get("/plans", response_model=list[PlanResponse])
async def list_learning_plans(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
) -> list[PlanResponse]:
    """List all learning plans for the current user, newest first."""
    user_id = user.get("uid") or user["sub"]  # ponytail: prefer uid (DB UUID), fallback sub
    stmt = (
        sa.select(LearningPlan)
        .where(LearningPlan.user_id == user_id)
        .order_by(LearningPlan.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    plans = result.scalars().all()

    responses: list[PlanResponse] = []
    for plan in plans:
        progress_data = await get_progress(session, plan_id=plan.id)

        skill_gaps: list[Any] = plan.skills if isinstance(plan.skills, list) else []
        if skill_gaps:
            try:
                path = await generate_learning_path(
                    match_gaps=skill_gaps,
                    available_time=10.0,
                )
                total_hours = path.total_hours
                total_weeks = path.total_weeks
                phases = [PhaseInfo(**p) for p in path.phases]
                phase_count = path.phase_count
            except Exception:
                total_hours = plan.estimated_hours
                total_weeks = 0
                phases = []
                phase_count = 0
        else:
            total_hours = plan.estimated_hours
            total_weeks = 0
            phases = []
            phase_count = 0

        responses.append(PlanResponse(
            plan_id=str(plan.id),
            position=plan.position,
            status=plan.status,
            match_score_at_creation=plan.match_score_at_creation,
            overall_pct=progress_data.get("overall_pct", 0.0),
            total_hours=total_hours,
            total_weeks=total_weeks,
            phase_count=phase_count,
            phases=phases,
            skills=[SkillProgressItem(**s) for s in progress_data.get("skills", [])],
            stats=progress_data.get("stats", {}),
        ))

    return responses


@router.post("/plan", response_model=PlanResponse)
async def create_learning_plan(
    body: CreatePlanRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PlanResponse:
    """Create a learning plan from match diagnosis results.

    Accepts skill gap data from a match diagnosis and generates a
    personalized, prerequisite-aware learning path with time estimates.
    """
    user_id = user["sub"]
    # Generate learning path
    skill_gaps = [s.model_dump() for s in body.skills]
    learning_path = await generate_learning_path(
        match_gaps=skill_gaps,
        prerequisites=PREREQUISITE_MAP,
        available_time=body.available_hours_per_week,
    )

    # Enrich skill data with estimated hours from path engine
    enriched_skills = []
    path_hours_map = {s.name: s.estimated_hours for s in learning_path.skills}
    for gap in skill_gaps:
        gap["estimated_hours"] = path_hours_map.get(gap["skill"], 0.0)
        enriched_skills.append(gap)

    # Create plan in DB
    plan = await create_plan(
        session,
        position=body.position,
        skills=enriched_skills,
        match_score=body.match_score,
        estimated_hours=learning_path.total_hours,
        user_id=user_id,
    )

    # Fetch full progress data
    progress_data = await get_progress(session, plan_id=plan.id)

    return PlanResponse(
        plan_id=str(plan.id),
        position=plan.position,
        status=plan.status,
        match_score_at_creation=plan.match_score_at_creation,
        overall_pct=progress_data.get("overall_pct", 0.0),
        total_hours=learning_path.total_hours,
        total_weeks=learning_path.total_weeks,
        phase_count=learning_path.phase_count,
        phases=[PhaseInfo(**p) for p in learning_path.phases],
        skills=[SkillProgressItem(**s) for s in progress_data.get("skills", [])],
        stats=progress_data.get("stats", {}),
    )


@router.get("/plan/{plan_id}", response_model=PlanResponse)
async def get_learning_plan(
    plan_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PlanResponse:
    """Get learning plan details with current progress."""
    user_id = user["sub"]
    try:
        pid = uuid.UUID(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid plan_id format") from exc

    progress_data = await get_progress(session, plan_id=pid)
    if "error" in progress_data:
        raise HTTPException(status_code=404, detail=progress_data["error"])

    # Fetch plan for extra fields
    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == pid)
    plan_result = await session.execute(plan_stmt)
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    # P1 修复 (AUTHZ-02): IDOR 校验 — 用户只能访问自己的计划
    if plan.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    # Reconstruct phases from skill data
    skill_gaps: list[Any] = plan.skills if isinstance(plan.skills, list) else []
    if skill_gaps:
        path = await generate_learning_path(
            match_gaps=skill_gaps,
            available_time=10.0,
        )
        total_hours = path.total_hours
        total_weeks = path.total_weeks
        phases = [PhaseInfo(**p) for p in path.phases]
        phase_count = path.phase_count
    else:
        total_hours = plan.estimated_hours
        total_weeks = 0
        phases = []
        phase_count = 0

    return PlanResponse(
        plan_id=str(plan.id),
        position=plan.position,
        status=plan.status,
        match_score_at_creation=plan.match_score_at_creation,
        overall_pct=progress_data.get("overall_pct", 0.0),
        total_hours=total_hours,
        total_weeks=total_weeks,
        phase_count=phase_count,
        phases=phases,
        skills=[SkillProgressItem(**s) for s in progress_data.get("skills", [])],
        stats=progress_data.get("stats", {}),
    )


@router.put("/plan/{plan_id}/progress", response_model=SkillProgressItem)
async def update_skill_progress(
    plan_id: str,
    body: UpdateProgressRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SkillProgressItem:
    """Update learning progress for a specific skill."""
    user_id = user["sub"]
    try:
        pid = uuid.UUID(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid plan_id format") from exc

    # IDOR guard: verify plan ownership before allowing mutation
    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == pid)
    plan_result = await session.execute(plan_stmt)
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this plan")

    progress = await update_progress(
        session,
        plan_id=pid,
        skill_name=body.skill_name,
        status=body.status,
        progress_pct=body.progress_pct,
        notes=body.notes,
    )

    if progress is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{body.skill_name}' not found in plan",
        )

    return SkillProgressItem(
        skill_name=progress.skill_name,
        status=progress.status,
        progress_pct=round(progress.progress_pct, 1),
        importance=progress.importance,
        estimated_hours=progress.estimated_hours,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
        notes=progress.notes,
    )


class AddSkillRequest(BaseModel):
    """Request to add a new skill to an existing plan."""

    skill_name: str = Field(..., min_length=1)
    importance: str = Field(default="bonus", description="required | bonus")
    estimated_hours: float = Field(default=20.0, ge=0.0)


@router.post("/plan/{plan_id}/skills", response_model=SkillProgressItem)
async def add_skill_to_plan(
    plan_id: str,
    body: AddSkillRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SkillProgressItem:
    """Add a new skill to an existing learning plan."""
    user_id = user["sub"]
    try:
        pid = uuid.UUID(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid plan_id format") from exc

    # Fetch the plan
    plan_stmt = sa.select(LearningPlan).where(LearningPlan.id == pid)
    plan_result = await session.execute(plan_stmt)
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    # IDOR guard: verify plan ownership
    if plan.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this plan")

    # Check if skill already exists in plan
    existing_stmt = sa.select(LearningProgress).where(
        LearningProgress.plan_id == pid,
        LearningProgress.skill_name == body.skill_name,
    )
    existing_result = await session.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        # Skill already in plan — return existing progress
        return SkillProgressItem(
            skill_name=existing.skill_name,
            status=existing.status,
            progress_pct=round(existing.progress_pct, 1),
            importance=existing.importance,
            estimated_hours=existing.estimated_hours,
            started_at=existing.started_at.isoformat() if existing.started_at else None,
            completed_at=existing.completed_at.isoformat() if existing.completed_at else None,
            notes=existing.notes,
        )

    # Create new progress record
    progress = LearningProgress(
        plan_id=pid,
        skill_name=body.skill_name,
        status="not_started",
        progress_pct=0.0,
        importance=body.importance,
        estimated_hours=body.estimated_hours,
    )
    session.add(progress)

    # Also add skill to plan's skills JSON
    skills_list: list[Any] = plan.skills if isinstance(plan.skills, list) else []
    skills_list.append({
        "skill": body.skill_name,
        "importance": body.importance,
        "gap_level": "完全缺失",
        "learning_path": [],
        "estimated_hours": body.estimated_hours,
    })
    plan.skills = skills_list

    await session.commit()
    await session.refresh(progress)

    logger.info("Added skill '{}' to plan {}", body.skill_name, plan_id)

    return SkillProgressItem(
        skill_name=progress.skill_name,
        status=progress.status,
        progress_pct=round(progress.progress_pct, 1),
        importance=progress.importance,
        estimated_hours=progress.estimated_hours,
        started_at=None,
        completed_at=None,
        notes=None,
    )


@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    plan_id: str | None = Query(default=None, description="Plan ID for context"),
    position: str | None = Query(default=None, description="Target position for context"),
) -> RecommendationsResponse:
    """Get personalized learning recommendations.

    If plan_id is provided, recommendations are based on the plan's gap skills.
    If position is provided, recommendations are based on the position's requirements.
    Otherwise, returns general trending skill recommendations.
    """
    items: list[RecommendationItem] = []

    if plan_id:
        try:
            pid = uuid.UUID(plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid plan_id format") from exc

        # Get plan's gap skills sorted by priority
        stmt = (
            sa.select(LearningProgress)
            .where(
                LearningProgress.plan_id == pid,
                LearningProgress.status != "mastered",
            )
            .order_by(
                LearningProgress.importance.desc(),
                LearningProgress.progress_pct.asc(),
            )
            .limit(10)
        )
        result = await session.execute(stmt)
        progress_records = result.scalars().all()

        for p in progress_records:
            prereqs = PREREQUISITE_MAP.get(p.skill_name, [])
            reason = f"该技能在你的学习计划中状态为「{p.status}」，进度 {p.progress_pct:.0f}%"
            if p.importance == "required":
                reason += "，且为必备技能"

            items.append(RecommendationItem(
                skill=p.skill_name,
                importance=p.importance,
                gap_level="部分掌握" if p.progress_pct > 0 else "完全缺失",
                estimated_hours=p.estimated_hours,
                prerequisites=prereqs,
                reason=reason,
            ))

    elif position:
        # Generate recommendations based on position requirements from graph
        from app.services.graph_service import fetch_position_graph
        from app.services.resources import resources as app_resources

        driver = app_resources.neo4j_driver
        profile = None

        if driver is not None:
            try:
                graph = await fetch_position_graph(driver, position, depth=1)
                skills = graph.get("skills", [])
                if skills:
                    required_skills = []
                    bonus_skills = []
                    for item in skills:
                        props = item.get("properties", {})
                        skill_name = props.get("name", item.get("name", ""))
                        importance = props.get("importance", "required")
                        if importance == "bonus":
                            bonus_skills.append(skill_name)
                        else:
                            required_skills.append(skill_name)
                    profile = {"required": required_skills, "bonus": bonus_skills}
            except Exception as exc:
                logger.warning("Failed to load position profile from graph for \"{}\": {}", position, exc)

        if profile is None:
            # Fallback: return empty with message
            return RecommendationsResponse(items=[], total_items=0)

        for skill_name in profile.get("required", []):
            prereqs = PREREQUISITE_MAP.get(skill_name, [])
            items.append(RecommendationItem(
                skill=skill_name,
                importance="required",
                gap_level="完全缺失",
                estimated_hours=40.0,
                prerequisites=prereqs,
                reason=f"「{position}」岗位的必备技能",
            ))

        for skill_name in profile.get("bonus", []):
            prereqs = PREREQUISITE_MAP.get(skill_name, [])
            items.append(RecommendationItem(
                skill=skill_name,
                importance="bonus",
                gap_level="完全缺失",
                estimated_hours=20.0,
                prerequisites=prereqs,
                reason=f"「{position}」岗位的加分技能",
            ))

    else:
        # General trending recommendations from SkillRecord
        try:
            from app.models.extraction_models import SkillRecord

            trending_stmt = (
                sa.select(SkillRecord)
                .where(SkillRecord.source_count > 3)
                .order_by(SkillRecord.source_count.desc())
                .limit(10)
            )
            trending_result = await session.execute(trending_stmt)
            trending_records = trending_result.scalars().all()

            for tr in trending_records:
                prereqs = PREREQUISITE_MAP.get(tr.name, [])
                items.append(RecommendationItem(
                    skill=tr.name,
                    importance="bonus",
                    gap_level="完全缺失",
                    estimated_hours=20.0,
                    prerequisites=prereqs,
                    reason=f"市场热门技能（出现 {tr.source_count} 次）",
                ))
        except Exception as exc:
            logger.warning("Failed to load trending skills: {}", exc)

    return RecommendationsResponse(
        items=items,
        total_items=len(items),
    )
