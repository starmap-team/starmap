"""Match API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver
from app.models.extraction_models import PositionRecord
from app.services.match_service import compute_competitiveness, get_match_result, run_match

router = APIRouter(prefix="/match", tags=["match"])


class PersonSkillInput(BaseModel):
    """More permissive skill input for current frontend payloads."""

    skill_id: str | None = Field(default=None)
    name: str = Field(..., description="Skill name")
    category: str = Field(default="hard_skill", description="Skill category")
    proficiency: str = Field(default="熟悉", description="Proficiency level")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_count: int = Field(default=0, ge=0)


class MatchOptionsInput(BaseModel):
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class MatchRequestInput(BaseModel):
    person_skills: list[PersonSkillInput] = Field(default_factory=list)
    target_position: str = Field(..., min_length=1)
    options: MatchOptionsInput = Field(default_factory=MatchOptionsInput)


# P2 修复 (INJ-02/AUTHZ-03): /match/batch 添加 Pydantic schema
class BatchMatchItem(BaseModel):
    """Single item in a batch match request."""
    position: str = Field(default="", description="Target position name")
    position_name: str = Field(default="", description="Alias for position (legacy)")
    skills: list[PersonSkillInput] = Field(default_factory=list, description="Person skills")


class BatchMatchRequest(BaseModel):
    """Batch match request with validated items."""
    entries: list[BatchMatchItem] = Field(default_factory=list, max_length=20, alias="items")

    model_config = {"populate_by_name": True}


class SkillGapDetail(BaseModel):
    skill: str
    importance: str
    gap_level: Literal["完全缺失", "部分掌握", "已掌握"]
    learning_path: list[str] = Field(default_factory=list)


class MatchResponse(BaseModel):
    match_id: str
    target_position: str
    match_score: float = Field(ge=0.0, le=1.0)
    matched_skills: list[str] = Field(default_factory=list)
    gap_skills: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_bonus: list[str] = Field(default_factory=list)
    skill_gap_detail: list[SkillGapDetail] = Field(default_factory=list)
    overall_assessment: str = Field(default="")
    estimated_learning_time: str = Field(default="")
    cii: float | None = Field(default=None, description="Capability Inflation Index")


async def _run_match_request(body: MatchRequestInput, driver: Any, session: AsyncSession) -> MatchResponse:
    """Execute match and persist result via the service layer.

    The service's run_match() now handles PostgreSQL persistence internally,
    so no duplicate INSERT is needed here.
    """
    result = await run_match(
        target_position=body.target_position,
        person_skills=[item.model_dump() for item in body.person_skills],
        threshold=body.options.threshold,
        driver=driver,
        db_session=session,
    )
    return MatchResponse(**result)


@router.post("/position", response_model=MatchResponse)
async def match_position(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Match resume skills against a target position."""
    if not body.person_skills:
        raise HTTPException(status_code=400, detail="person_skills cannot be empty.")
    return await _run_match_request(body, driver, session)


@router.post("/diagnose", response_model=MatchResponse)
async def diagnose_match(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Alias for /match/position — delegates to match_position.

    x-audit-note: L1 — This is a convenience alias; /match/position is the canonical endpoint.
    """
    return await match_position(body, driver, session)


@router.get("/result/{match_id}", response_model=MatchResponse)
async def get_match_result_detail(
    match_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Return a previously generated match result."""
    result = await get_match_result(match_id, db_session=session)
    if result is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    return MatchResponse(**result)


@router.get("/history")
async def match_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Return recent match results."""
    try:
        result = await session.execute(
            text("""
                SELECT match_id, target_position, match_score, matched_skills, created_at
                FROM match_results
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        items = []
        for row in rows:
            items.append({
                "match_id": row[0],
                "target_position": row[1],
                "match_score": float(row[2] or 0),
                "matched_skills": row[3] if isinstance(row[3], list) else [],
                "created_at": str(row[4]) if row[4] else None,
            })
        return {"items": items}
    except Exception as exc:
        logger.warning("Failed to fetch match history: {}", exc)
        return {"items": []}


@router.get("/competitiveness/{position}")
async def get_competitiveness(
    position: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Return competitiveness analysis for a target position."""
    return await compute_competitiveness(
        target_position=position,
        driver=driver,
        db_session=session,
    )


@router.post("/batch")
async def batch_match(
    body: BatchMatchRequest,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Batch match: run match for multiple items at once.

    Payload compatibility: accepts both ``position`` (frontend learning store)
    and ``position_name`` (legacy contract) as the target position field.
    Each item: ``{ "skills": [...], "position": "..." }``.
    """
    items = body.entries
    results = []
    for item in items[:20]:
        # 兼容前端 {position} 与历史契约 {position_name} 两种字段命名
        position = item.position_name or item.position or ""
        skills = [s.model_dump() if isinstance(s, PersonSkillInput) else s for s in item.skills]
        try:
            result = await run_match(
                target_position=position,
                person_skills=skills,
                driver=driver,
                db_session=session,
            )
            results.append({"position_name": position, "result": result})
        except Exception as e:
            results.append({"position_name": position, "error": str(e)})
    return {"results": results, "total": len(results)}


# ── FE-04: Reverse match (skills → position recommendations) ──


class ReverseMatchRequest(BaseModel):
    """Request body for reverse matching: given user skills, find suitable positions."""

    person_skills: list[PersonSkillInput] = Field(..., min_length=1, description="User's current skills")
    top_k: int = Field(default=10, ge=1, le=50, description="Max positions to return")
    min_score: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum match score threshold")


class PositionRecommendation(BaseModel):
    """A single position recommendation from reverse matching."""

    position_name: str
    match_score: float = Field(ge=0.0, le=1.0)
    matched_skills: list[str] = Field(default_factory=list)
    gap_skills: list[str] = Field(default_factory=list)
    skill_coverage: float = Field(ge=0.0, le=1.0, description="Fraction of position's required skills the user has")


class ReverseMatchResponse(BaseModel):
    """Response for reverse matching."""

    recommendations: list[PositionRecommendation] = Field(default_factory=list)
    total_positions_scanned: int = Field(ge=0)
    skills_provided: int = Field(ge=0)


@router.post("/recommend", response_model=ReverseMatchResponse)
async def recommend_positions(
    body: ReverseMatchRequest,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReverseMatchResponse:
    """FE-04: Reverse match — given user skills, recommend suitable positions.

    Scans available positions, computes match score for each,
    and returns the top-k positions ranked by match score.
    """
    from app.core.matching.service import MatchService

    # Get distinct position names from the database
    try:
        result = await session.execute(
            sa_select(PositionRecord.name).distinct().limit(200)
        )
        position_names = [row[0] for row in result.fetchall()]
    except Exception as exc:
        logger.warning("Failed to query positions for reverse match: {}", exc)
        position_names = []

    if not position_names:
        # Fallback: try Neo4j
        if driver is not None:
            try:
                async with driver.session() as neo_session:
                    cypher_result = await neo_session.run(
                        "MATCH (p:Position) RETURN p.name AS name LIMIT 200"
                    )
                    position_names = []
                    async for rec in cypher_result:
                        if rec.get("name"):
                            position_names.append(rec["name"])
            except Exception as exc:
                logger.warning("Neo4j fallback for reverse match failed: {}", exc)

    if not position_names:
        return ReverseMatchResponse(
            recommendations=[],
            total_positions_scanned=0,
            skills_provided=len(body.person_skills),
        )

    # Run match for each position and collect scores
    match_svc = MatchService()
    person_skills_dicts = [s.model_dump() for s in body.person_skills]

    recommendations: list[PositionRecommendation] = []
    for pos_name in position_names:
        try:
            result = await match_svc.run_match(
                target_position=pos_name,
                person_skills=person_skills_dicts,
                threshold=body.min_score,
                driver=driver,
                db_session=session,
            )
            score = result.get("match_score", 0.0)
            if score >= body.min_score:
                matched = result.get("matched_skills", [])
                gap = result.get("gap_skills", [])
                # Compute skill coverage: what fraction of position's total skills does user cover?
                total_position_skills = len(matched) + len(gap)
                coverage = len(matched) / total_position_skills if total_position_skills > 0 else 1.0
                recommendations.append(PositionRecommendation(
                    position_name=pos_name,
                    match_score=round(score, 4),
                    matched_skills=matched,
                    gap_skills=gap,
                    skill_coverage=round(coverage, 4),
                ))
        except Exception:
            continue  # skip positions that fail

    # Sort by match_score descending, take top_k
    recommendations.sort(key=lambda r: r.match_score, reverse=True)
    recommendations = recommendations[: body.top_k]

    return ReverseMatchResponse(
        recommendations=recommendations,
        total_positions_scanned=len(position_names),
        skills_provided=len(body.person_skills),
    )
