"""管理后台 API。"""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quality import _build_quality_dashboard
from app.core.extraction.prompt import (
    get_ab_test,
    get_active_version,
    get_prompt_template_raw,
    list_prompt_names,
    list_prompt_versions,
    register_prompt_version,
    set_ab_test,
    set_active_version,
    stop_ab_test,
)
from app.dependencies import get_db_session
from app.models.extraction_models import JDExtractionRecord, PositionRecord, PositionSkillRelation, SkillRecord

router = APIRouter(prefix="/admin", tags=["管理后台"])


class SourceConfig(BaseModel):
    id: int
    name: str
    authority_score: float = Field(ge=0.0, le=1.0)
    source_type: str


class SourceListResponse(BaseModel):
    items: list[SourceConfig] = Field(default_factory=list)


class AuditItem(BaseModel):
    id: int
    type: str
    name: str
    trust: int = Field(ge=0, le=100)
    status: str


class AuditQueueResponse(BaseModel):
    items: list[AuditItem] = Field(default_factory=list)


class AdminStatsResponse(BaseModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    total_positions: int = Field(ge=0)
    total_skills: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    pending_review: int = Field(ge=0)


class ResetDemoResponse(BaseModel):
    ok: bool = True
    review_items: int = Field(ge=0)


class SetActiveRequest(BaseModel):
    version: str = Field(..., description="要激活的版本号 (如 v1, v2)")


class ABTestRequest(BaseModel):
    canary_version: str = Field(..., description="候选版本号")
    traffic_fraction: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="分配到 canary 的流量比例 (0.0, 0.5]",
    )


class RegisterVersionRequest(BaseModel):
    template: str = Field(..., description="Prompt 模板内容（含占位符）")
    version: str | None = Field(default=None, description="版本号，如 v4；不传则自动递增")
    activate: bool = Field(default=False, description="是否激活为该 prompt 的当前版本")


_DEMO_SOURCES = [
    SourceConfig(id=1, name="BOSS直聘", authority_score=0.70, source_type="aggregator"),
    SourceConfig(id=2, name="拉勾", authority_score=0.72, source_type="aggregator"),
    SourceConfig(id=3, name="猎聘", authority_score=0.74, source_type="aggregator"),
    SourceConfig(id=4, name="ESCO", authority_score=0.92, source_type="official"),
]
_DEMO_AUDIT_QUEUE_TEMPLATE = [
    AuditItem(id=1, type="skill", name="AI Agent开发", trust=58, status="pending"),
    AuditItem(id=2, type="position", name="大模型应用工程师", trust=64, status="pending"),
    AuditItem(id=3, type="skill", name="Spring AI", trust=72, status="pending"),
    AuditItem(id=4, type="skill", name="RAG", trust=45, status="pending"),
]
_demo_audit_queue = deepcopy(_DEMO_AUDIT_QUEUE_TEMPLATE)


async def _build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    dashboard = await _build_quality_dashboard(session)

    try:
        counts_stmt = sa.select(
            sa.func.count(PositionRecord.id),
            sa.func.count(SkillRecord.id),
            sa.func.count(PositionSkillRelation.id),
            sa.func.coalesce(sa.func.avg(JDExtractionRecord.confidence), 0.0),
        )
        positions, skills, edges, avg_confidence = (await session.execute(counts_stmt)).one()
        total_positions = int(positions or 0)
        total_skills = int(skills or 0)
        total_edges = int(edges or 0)
        avg_value = float(avg_confidence or 0.0)
    except Exception:
        total_positions = len([item for item in _demo_audit_queue if item.type == "position"])
        total_skills = len(_DEMO_SOURCES) * 5
        total_edges = total_skills * 2
        avg_value = 0.78

    return AdminStatsResponse(
        total_nodes=total_positions + total_skills,
        total_edges=total_edges,
        total_positions=total_positions,
        total_skills=total_skills,
        avg_confidence=avg_value,
        hallucination_rate=dashboard.hallucination_rate,
        pending_review=len([item for item in _demo_audit_queue if item.status == "pending"]),
    )


def _find_audit_item(item_id: int) -> AuditItem | None:
    for item in _demo_audit_queue:
        if item.id == item_id:
            return item
    return None


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """后台统计概览。"""
    return await _build_admin_stats(session)


@router.get("/sources", response_model=SourceListResponse)
async def get_sources() -> SourceListResponse:
    """数据源配置列表。"""
    return SourceListResponse(items=_DEMO_SOURCES)


@router.get("/review-queue", response_model=AuditQueueResponse)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue() -> AuditQueueResponse:
    """人工审核队列。"""
    return AuditQueueResponse(items=[item for item in _demo_audit_queue if item.status == "pending"])


@router.post("/audit/{item_id}/approve", response_model=AuditItem)
async def approve_audit(item_id: int) -> AuditItem:
    """批准某条审核项。"""
    item = _find_audit_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    item.status = "approved"
    return item


@router.post("/audit/{item_id}/reject", response_model=AuditItem)
async def reject_audit(item_id: int) -> AuditItem:
    """拒绝某条审核项。"""
    item = _find_audit_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    item.status = "rejected"
    return item


@router.post("/seed/reset", response_model=ResetDemoResponse)
@router.post("/reset-demo", response_model=ResetDemoResponse, include_in_schema=False)
async def reset_demo_seed() -> ResetDemoResponse:
    """重置演示审核数据。"""
    _demo_audit_queue.clear()
    _demo_audit_queue.extend(deepcopy(_DEMO_AUDIT_QUEUE_TEMPLATE))
    return ResetDemoResponse(ok=True, review_items=len(_demo_audit_queue))


# ──────────────────────────────────────────────
# Prompt 版本管理
# ──────────────────────────────────────────────


@router.get("/prompts")
async def list_prompts() -> dict[str, Any]:
    """列出所有 prompt 模板及其可用版本。"""
    result: dict[str, Any] = {}
    for name in list_prompt_names():
        versions = list_prompt_versions(name)
        active = get_active_version(name)
        ab = get_ab_test(name)
        result[name] = {
            "versions": versions,
            "active": active,
            "ab_test": ab.to_dict() if ab else None,
        }
    return result


@router.get("/prompts/{name}")
async def get_prompt_info(name: str) -> dict[str, Any]:
    """查看指定 prompt 模板的版本详情。"""
    try:
        versions = list_prompt_versions(name)
        active = get_active_version(name)
        ab = get_ab_test(name)
        return {
            "name": name,
            "versions": versions,
            "active": active,
            "ab_test": ab.to_dict() if ab else None,
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/prompts/{name}/versions/{version}")
async def get_prompt_template_content(name: str, version: str) -> dict[str, Any]:
    """查看 prompt 模板的原始内容。"""
    try:
        template = get_prompt_template_raw(name, version)
        return {"name": name, "version": version, "template": template}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/prompts/{name}/versions")
async def create_prompt_version(name: str, req: RegisterVersionRequest) -> dict[str, Any]:
    """注册一个新的 prompt 版本。"""
    try:
        version = register_prompt_version(
            name=name,
            template=req.template,
            version=req.version,
            activate=req.activate,
        )
        logger.info("Admin: registered prompt '{}' version '{}'", name, version)
        return {"name": name, "version": version, "activate": req.activate, "status": "created"}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/prompts/{name}/active")
async def change_active_version(name: str, req: SetActiveRequest) -> dict[str, str]:
    """切换 prompt 模板的 active 版本。"""
    try:
        set_active_version(name, req.version)
        logger.info("Admin: set active version '{}' -> '{}'", name, req.version)
        return {"name": name, "active": req.version, "status": "updated"}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ──────────────────────────────────────────────
# A/B 测试管理
# ──────────────────────────────────────────────


@router.post("/prompts/{name}/ab")
async def start_ab_test(name: str, req: ABTestRequest) -> dict[str, Any]:
    """启动 A/B 测试：canary 版本按比例分流，与 active 版本对比。"""
    try:
        cfg = set_ab_test(
            prompt_name=name,
            canary_version=req.canary_version,
            traffic_fraction=req.traffic_fraction,
        )
        logger.info(
            "Admin: A/B test started '{}' -> canary={} traffic={:.0%}",
            name,
            req.canary_version,
            req.traffic_fraction,
        )
        return {"status": "started", "config": cfg.to_dict()}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/prompts/{name}/ab")
async def remove_ab_test(name: str) -> dict[str, str]:
    """停止 A/B 测试，恢复为全量 active 版本。"""
    stop_ab_test(name)
    logger.info("Admin: A/B test stopped for '{}'", name)
    return {"name": name, "status": "stopped", "message": "Back to active version only"}


@router.get("/prompts/{name}/ab")
async def get_ab_test_config(name: str) -> dict[str, Any]:
    """查看当前 A/B 测试配置（如无则返回 null ab_test）。"""
    ab = get_ab_test(name)
    return {
        "name": name,
        "ab_test": ab.to_dict() if ab else None,
    }
