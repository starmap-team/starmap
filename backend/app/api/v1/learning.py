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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import GAP_LEVEL_MISSING, GAP_LEVEL_PARTIAL
from app.dependencies import get_current_user, get_db_session
from app.exceptions import LearningPathError, StarMapError
from app.models.learning_models import LearningPlan, LearningProgress
from app.schemas.learning import (
    AddSkillRequest,
    CreatePlanRequest,
    PlanResponse,
    RecommendationItem,
    RecommendationsResponse,
    SkillProgressItem,
    UpdateProgressRequest,
)
from app.services import learning_service
from app.services.match_service import PREREQUISITE_MAP, ensure_prerequisite_map

router = APIRouter(prefix="/learning", tags=["学习中心"])


# ─── Endpoints ───
# 请求/响应模型已迁至 backend/app/schemas/learning.py(闭环审计 C2),路由层只引用。


@router.get("/plans", response_model=list[PlanResponse])
async def list_learning_plans(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
) -> list[PlanResponse]:
    """List all learning plans for the current user, newest first."""
    # NEW-02 修复：必须与 create/get/update/add 同口径（sub=username，
    # 即 LearningPlan.user_id 的存储值）；此前用 uid 查询导致真实用户
    # 查不到自己创建的计划。
    user_id = user["sub"]
    views = await learning_service.list_plans_for_user(session, user_id, limit)
    return [PlanResponse(**v) for v in views]


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
    skill_gaps = [s.model_dump() for s in body.skills]
    view = await learning_service.create_plan_from_diagnosis(
        session,
        user_id=user_id,
        position=body.position,
        skill_gaps=skill_gaps,
        match_score=body.match_score,
        available_hours_per_week=body.available_hours_per_week,
    )
    return PlanResponse(**view)


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
    # 业务逻辑在 learning_service;PlanNotFoundError→404 / PlanOwnershipError→403 由全局处理器映射。
    view = await learning_service.get_plan_for_user(session, user_id=user_id, plan_id=pid)
    return PlanResponse(**view)


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
    # PlanNotFoundError→404 / PlanOwnershipError→403 由全局处理器映射;返回 None 表示技能不在计划内。
    progress = await learning_service.update_skill_progress_for_user(
        session,
        user_id=user_id,
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
    return SkillProgressItem(**progress)


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
        "gap_level": GAP_LEVEL_MISSING,
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
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    plan_id: str | None = Query(default=None, description="Plan ID for context"),
    position: str | None = Query(default=None, description="Target position for context"),
) -> RecommendationsResponse:
    """Get personalized learning recommendations.

    If plan_id is provided, recommendations are based on the plan's gap skills.
    If position is provided, recommendations are based on the position's requirements.
    Otherwise, returns general trending skill recommendations.
    """
    # NEW-03: 首次调用时从 Neo4j 加载前置关系（不可用时降级为空）
    await ensure_prerequisite_map()

    items: list[RecommendationItem] = []

    if plan_id:
        try:
            pid = uuid.UUID(plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid plan_id format") from exc

        # NEW-21 修复：plan_id 分支须属主校验，防他人计划技能缺口泄漏（IDOR）
        plan_row = (
            await session.execute(sa.select(LearningPlan).where(LearningPlan.id == pid))
        ).scalar_one_or_none()
        if plan_row is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan_row.user_id != user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this plan")

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
                gap_level=GAP_LEVEL_PARTIAL if p.progress_pct > 0 else GAP_LEVEL_MISSING,
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
            except LearningPathError as exc:
                logger.exception("Learning path operation failed: {}", exc)
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            except StarMapError:
                raise
            except Exception as exc:
                logger.exception("Unexpected error in learning path: {}", exc)
                raise HTTPException(status_code=500, detail="学习路径处理异常") from exc

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
        except LearningPathError as exc:
            logger.exception("Learning path operation failed: {}", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in learning path: {}", exc)
            raise HTTPException(status_code=500, detail="学习路径处理异常") from exc

    return RecommendationsResponse(
        items=items,
        total_items=len(items),
    )
