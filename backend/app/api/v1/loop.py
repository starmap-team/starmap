"""Closed-loop demo API — end-to-end pipeline endpoints.

Endpoints:
  POST /loop/run              — trigger closed-loop (input JD text, return full chain result)
  GET  /loop/status/{run_id}  — loop run status
  GET  /loop/history          — loop run history
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline.loop_orchestrator import (
    LoopOrchestrator,
    get_loop_history,
    get_loop_status,
)
from app.dependencies import get_current_user, get_db_session
from app.schemas.loop import (
    LoopHistoryResponse,
    LoopRunRequest,
    LoopRunResponse,
    LoopStepResponse,
)
from app.utils.audit import AuditEntry, AuditEvent, audit_log

router = APIRouter(prefix="/loop", tags=["loop"])

# Module-level orchestrator instance (stateless, no constructor args)
_orchestrator = LoopOrchestrator()






@router.post("/run", response_model=LoopRunResponse)
async def run_loop(
    req: LoopRunRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
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
        user_id=user["sub"],  # SEC-04: pass user identity
    )
    data = result.to_dict()
    return LoopRunResponse(**data)


@router.get("/status/{run_id}")
async def loop_status(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict:
    """Get the status and result of a specific loop run."""
    status = await get_loop_status(
        run_id,
        session=session,
        user_id=user["sub"],
        is_admin=user.get("role") == "admin",
    )
    if status is None:
        # Could be "not found" or "not authorized" — log the attempt (SEC-04)
        audit_log(AuditEntry(
            event=AuditEvent.AUTHZ_DENIED,
            actor=user.get("sub", "unknown"),
            action=f"loop_status:{run_id}",
            detail="Loop run not found or not authorized",
            ip="",
        ))
        raise HTTPException(status_code=404, detail=f"Loop run '{run_id}' not found")
    return status


@router.get("/history", response_model=LoopHistoryResponse)
async def loop_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = 50,
) -> LoopHistoryResponse:
    """Get the history of loop runs."""
    items = await get_loop_history(
        limit=limit,
        session=session,
        user_id=user["sub"],
        is_admin=user.get("role") == "admin",
    )
    return LoopHistoryResponse(items=items)
