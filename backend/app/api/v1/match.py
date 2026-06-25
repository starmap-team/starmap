"""匹配诊断 API。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_neo4j_driver
from app.services.match_service import get_match_result, run_match

router = APIRouter(prefix="/match", tags=["匹配诊断"])


class PersonSkillInput(BaseModel):
    """More permissive skill input for current frontend payloads."""

    skill_id: str | None = Field(default=None)
    name: str = Field(..., description="技能名称")
    category: str = Field(default="hard_skill", description="技能分类")
    proficiency: str = Field(default="熟悉", description="熟练度")
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


async def _run_match_request(body: MatchRequestInput, driver: Any) -> MatchResponse:
    result = await run_match(
        target_position=body.target_position,
        person_skills=[item.model_dump() for item in body.person_skills],
        threshold=body.options.threshold,
        driver=driver,
    )
    return MatchResponse(**result)


@router.post("/position", response_model=MatchResponse)
async def match_position(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> MatchResponse:
    """契约端点：简历技能与目标岗位做匹配诊断。"""
    return await _run_match_request(body, driver)


@router.post("/diagnose", response_model=MatchResponse)
async def diagnose_match(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> MatchResponse:
    """阶段 4 别名端点，兼容手册中的 `/match/diagnose`。"""
    return await _run_match_request(body, driver)


@router.get("/result/{match_id}", response_model=MatchResponse)
async def get_match_result_detail(match_id: str) -> MatchResponse:
    """获取之前生成的匹配结果详情。"""
    result = get_match_result(match_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    return MatchResponse(**result)
