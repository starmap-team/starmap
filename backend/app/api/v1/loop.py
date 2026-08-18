"""Closed-loop demo API — end-to-end pipeline endpoints.

Endpoints:
  POST /loop/run              — trigger closed-loop (input JD text, return full chain result)
  GET  /loop/status/{run_id}  — loop run status
  GET  /loop/history          — loop run history
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_session
from app.schemas.loop import (
    LoopHistoryResponse,
    LoopRunRequest,
    LoopRunResponse,
)
from app.services.loop_service import LoopOrchestrator, get_loop_history, get_loop_status
from app.utils.audit import AuditEntry, AuditEvent, audit_log

router = APIRouter(prefix="/loop", tags=["loop"])

# Module-level orchestrator instance (stateless, no constructor args)
_orchestrator = LoopOrchestrator()

# QA-FIX (F#10): 闭环运行顶层超时（秒）。LLM 链路 + 图谱匹配正常情况下数秒~1 分钟完成；
# 超时即取消内层任务，run_loop 的 CancelledError 兜底会将该运行标记为失败。
LOOP_RUN_TIMEOUT_SECONDS = 600






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
 # QA-FIX (F#10): 顶层超时兜底 — run_loop 内部对 CancelledError/未捕获异常
 # 标记失败；wait_for 超时即取消内层任务，触发该兜底，防止运行永久 running。
    try:
        result = await asyncio.wait_for(
            _orchestrator.run_loop(
                jd_text=req.jd_text,
                target_position=req.target_position,
                session=session,
                user_id=user["sub"],  # SEC-04: pass user identity
            ),
            timeout=LOOP_RUN_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="闭环运行超时，已标记为失败（可在历史记录中查看）",
        ) from exc
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
