"""Health monitor API endpoints .

GET /api/v1/health/sources — 返回每个 data source 的健康度摘要
POST /api/v1/health/probe — 手动触发 startup probe
POST /api/v1/health/sources/{id}/resume — 把 paused source 恢复为 active
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_admin
from app.services.health_monitor import (
 get_health_dashboard,
 probe_sources_at_startup,
)
from app.utils.audit import AuditEntry, AuditEvent, audit_log

router = APIRouter(prefix="/health-monitor", tags=["健康度监控 "])

@router.get("/sources")
async def list_source_health(
 session: Annotated[AsyncSession, Depends(get_db_session)],
 user: Annotated[dict, Depends(require_admin)],
) -> dict:
 """返回每个 data source 的 24h 健康度。"""
 dashboard = await get_health_dashboard(session)
 return {"sources": dashboard, "count": len(dashboard)}

@router.post("/probe", dependencies=[Depends(require_admin)])
async def trigger_probe(
 session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
 """手动触发 startup probe（Fix H1: 自动 disable 4xx/5xx 源）。"""
 results = await probe_sources_at_startup(session)
 auto_paused = [name for name, status in results.items if status.startswith("auto_paused")]
 return {
 "probed": len(results),
 "auto_paused": auto_paused,
 "results": results,
 }

@router.post("/sources/{source_id}/resume", dependencies=[Depends(require_admin)])
async def resume_source(
 source_id: uuid.UUID,
 session: Annotated[AsyncSession, Depends(get_db_session)],
 user: Annotated[dict, Depends(require_admin)],
) -> dict:
 """手动恢复 paused source 为 active（同时重置 auto_paused_reason）。"""
 from sqlalchemy import select

 from app.models.pipeline_models import DataSourceRecord

 result = await session.execute(
 select(DataSourceRecord).where(DataSourceRecord.id == source_id)
 )
 src = result.scalar_one_or_none
 if not src:
 raise HTTPException(404, f"source {source_id} not found")

 if src.status == "active":
 return {"source_id": str(source_id), "status": "active", "message": "already active"}

 src.status = "active"
 # 清除 auto_paused_* 字段
 if src.config:
 src.config = {
 k: v for k, v in src.config.items
 if not k.startswith("auto_paused_")
 }
 await session.commit

 audit_log(
 AuditEntry(
 event=AuditEvent.ADMIN_ACTION,
 actor=user.get("sub", "admin"),
 action="resume_source",
 detail=f"source={src.name}",
 )
 )

 return {
 "source_id": str(source_id),
 "name": src.name,
 "status": "active",
 "message": "source resumed",
 }
