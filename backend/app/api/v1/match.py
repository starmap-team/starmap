"""Match API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver
from app.services.match_service import get_match_result, run_match

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


class SkillGapDetail(BaseModel):
    skill: str
    importance: str
    gap_level: str
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


async def _run_match_request(body: MatchRequestInput, driver: Any, session: AsyncSession) -> MatchResponse:
    result = await run_match(
        target_position=body.target_position,
        person_skills=[item.model_dump() for item in body.person_skills],
        threshold=body.options.threshold,
        driver=driver,
    )
    response = MatchResponse(**result)

    try:
        await session.execute(
            text(
                """
                INSERT INTO match_results (
                    match_id,
                    target_position,
                    person_skills,
                    match_score,
                    matched_skills,
                    missing_required,
                    missing_bonus,
                    gap_report,
                    learning_path,
                    created_at
                ) VALUES (
                    :match_id,
                    :target_position,
                    CAST(:person_skills AS jsonb),
                    :match_score,
                    CAST(:matched_skills AS jsonb),
                    CAST(:missing_required AS jsonb),
                    CAST(:missing_bonus AS jsonb),
                    CAST(:gap_report AS jsonb),
                    CAST(:learning_path AS jsonb),
                    now()
                )
                """
            ),
            {
                "match_id": response.match_id,
                "target_position": response.target_position,
                "person_skills": __import__("json").dumps([item.model_dump() for item in body.person_skills]),
                "match_score": response.match_score,
                "matched_skills": __import__("json").dumps(response.matched_skills),
                "missing_required": __import__("json").dumps(response.missing_required),
                "missing_bonus": __import__("json").dumps(response.missing_bonus),
                "gap_report": __import__("json").dumps([d.model_dump() for d in response.skill_gap_detail]),
                "learning_path": __import__("json").dumps([d.learning_path for d in response.skill_gap_detail]),
            },
        )
        await session.commit()
    except Exception as exc:
        logger.exception("Failed to persist match result: %s", exc)

    return response


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
    """Alias for /match/position — delegates to match_position."""
    return await match_position(body, driver, session)


@router.get("/result/{match_id}", response_model=MatchResponse)
async def get_match_result_detail(match_id: str) -> MatchResponse:
    """Return a previously generated match result."""
    result = await get_match_result(match_id)
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
