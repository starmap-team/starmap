"""Closed-loop demo API — end-to-end pipeline endpoints.

Endpoints:
  POST /loop/run              — trigger closed-loop (input JD text, return full chain result)
  GET  /loop/status/{run_id}  — loop run status
  GET  /loop/history          — loop run history
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline.loop_orchestrator import (
    LoopOrchestrator,
    get_loop_history,
    get_loop_status,
)
from app.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/loop", tags=["loop"])

# Module-level orchestrator instance (stateless, no constructor args)
_orchestrator = LoopOrchestrator()


class LoopRunRequest(BaseModel):
    """Request body for POST /loop/run."""

    jd_text: str = Field(..., min_length=1, description="Raw JD text to process")
    target_position: str | None = Field(
        default=None, description="Target position name for match diagnosis (optional, LOOP-09)"
    )


class LoopStepResponse(BaseModel):
    """Single step result in the loop timeline."""

    step: int
    name: str
    status: str
    data: dict = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    note: str | None = None


class LoopRunResponse(BaseModel):
    """Response for POST /loop/run."""

    run_id: str
    jd_text: str
    target_position: str | None
    status: str
    steps: list[LoopStepResponse] = Field(default_factory=list)
    extracted_skills: list[dict] = Field(default_factory=list)
    graph_update: dict = Field(default_factory=dict)
    match_result: dict = Field(default_factory=dict)
    learning_path: dict = Field(default_factory=dict)
    total_duration_seconds: float = 0.0


class LoopHistoryResponse(BaseModel):
    """Response for GET /loop/history."""

    items: list[dict] = Field(default_factory=list)


@router.post("/run", response_model=LoopRunResponse)
async def run_loop(
    req: LoopRunRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> LoopRunResponse:
    """Trigger the closed-loop end-to-end pipeline.

    Runs 5 steps with error isolation:
      1. JD input validation
      2. Skill extraction (LLM)
      3. Graph update (Neo4j)
      4. Match diagnosis
      5. Learning path generation

    Each step degrades independently on failure.
    """
    result = await _orchestrator.run_loop(
        jd_text=req.jd_text,
        target_position=req.target_position,
        session=session,
    )
    data = result.to_dict()
    return LoopRunResponse(**data)


@router.get("/status/{run_id}")
async def loop_status(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict:
    """Get the status and result of a specific loop run."""
    status = await get_loop_status(run_id, session=session)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Loop run '{run_id}' not found")
    return status


@router.get("/history", response_model=LoopHistoryResponse)
async def loop_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = 50,
) -> LoopHistoryResponse:
    """Get the history of loop runs."""
    items = await get_loop_history(limit=limit, session=session)
    return LoopHistoryResponse(items=items)
