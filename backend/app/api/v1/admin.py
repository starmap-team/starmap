"""Admin API.

This file was sanitized to ASCII-only because the original Chinese
docstrings contained non-printable characters that caused runtime
SyntaxError during uvicorn reload.
"""

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
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])


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
    version: str = Field(..., description="Target prompt version to activate, e.g. v1, v2")


class ABTestRequest(BaseModel):
    canary_version: str = Field(..., description="Candidate version")
    traffic_fraction: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="Traffic fraction sent to canary in (0.0, 0.5]",
    )


class RegisterVersionRequest(BaseModel):
    template: str = Field(..., description="Prompt template content with placeholders")
    version: str | None = Field(default=None, description="Version label, e.g. v4; auto-increment if omitted")
    activate: bool = Field(default=False, description="Activate this version immediately")


_DEMO_SOURCES = [
    SourceConfig(id=1, name="BOSS", authority_score=0.70, source_type="aggregator"),
    SourceConfig(id=2, name="Lagou", authority_score=0.72, source_type="aggregator"),
    SourceConfig(id=3, name="Liepin", authority_score=0.74, source_type="aggregator"),
    SourceConfig(id=4, name="ESCO", authority_score=0.92, source_type="official"),
]

_DEMO_AUDIT_QUEUE_TEMPLATE = [
    AuditItem(id=1, type="skill", name="AI Agent Dev", trust=58, status="pending"),
    AuditItem(id=2, type="position", name="LLM Application Engineer", trust=64, status="pending"),
    AuditItem(id=3, type="skill", name="Spring AI", trust=72, status="pending"),
    AuditItem(id=4, type="skill", name="RAG", trust=45, status="pending"),
]

_demo_audit_queue = deepcopy(_DEMO_AUDIT_QUEUE_TEMPLATE)


async def _build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    dashboard = await _build_quality_dashboard(session)

    try:
        counts_stmt = sa.select(
            sa.func.count(PositionRecord.id.distinct()),
            sa.func.count(SkillRecord.id.distinct()),
            sa.func.count(PositionSkillRelation.id.distinct()),
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
    """Admin overview stats."""
    return await _build_admin_stats(session)


@router.get("/sources", response_model=SourceListResponse)
async def get_sources() -> SourceListResponse:
    """Return configured data sources."""
    return SourceListResponse(items=_DEMO_SOURCES)


@router.get("/review-queue", response_model=AuditQueueResponse)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditQueueResponse:
    """Return pending review items from DB when available, otherwise demo queue."""
    try:
        from app.models.extraction_models import ReviewQueue as ReviewQueueModel

        stmt = (
            sa.select(ReviewQueueModel)
            .where(ReviewQueueModel.status == "pending")
            .order_by(ReviewQueueModel.id.desc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if rows:
            items = []
            for r in rows:
                trust = int((r.payload or {}).get("trust", 50))
                items.append(
                    AuditItem(
                        id=r.id,
                        type=r.entity_type,
                        name=r.entity_name,
                        trust=trust,
                        status=r.status,
                    )
                )
            return AuditQueueResponse(items=items)
    except Exception:
        pass

    return AuditQueueResponse(items=[item for item in _demo_audit_queue if item.status == "pending"])


@router.post("/audit/{item_id}/approve", response_model=AuditItem)
async def approve_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Approve a review queue item."""
    try:
        from app.models.extraction_models import ReviewQueue as ReviewQueueModel

        result = await session.execute(
            sa.select(ReviewQueueModel).where(ReviewQueueModel.id == item_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.status = "approved"
            await session.commit()
            trust = int((row.payload or {}).get("trust", 50))
            return AuditItem(
                id=row.id,
                type=row.entity_type,
                name=row.entity_name,
                trust=trust,
                status="approved",
            )
    except Exception:
        pass

    item = _find_audit_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    item.status = "approved"
    return item


@router.post("/audit/{item_id}/reject", response_model=AuditItem)
async def reject_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Reject a review queue item."""
    try:
        from app.models.extraction_models import ReviewQueue as ReviewQueueModel

        result = await session.execute(
            sa.select(ReviewQueueModel).where(ReviewQueueModel.id == item_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.status = "rejected"
            await session.commit()
            trust = int((row.payload or {}).get("trust", 50))
            return AuditItem(
                id=row.id,
                type=row.entity_type,
                name=row.entity_name,
                trust=trust,
                status="rejected",
            )
    except Exception:
        pass

    item = _find_audit_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
    item.status = "rejected"
    return item


@router.post("/seed/reset", response_model=ResetDemoResponse)
@router.post("/reset-demo", response_model=ResetDemoResponse, include_in_schema=False)
async def reset_demo_seed() -> ResetDemoResponse:
    """Reset demo review queue state."""
    _demo_audit_queue.clear()
    _demo_audit_queue.extend(deepcopy(_DEMO_AUDIT_QUEUE_TEMPLATE))
    return ResetDemoResponse(ok=True, review_items=len(_demo_audit_queue))


# Prompt management
@router.get("/prompts")
async def list_prompts() -> dict[str, Any]:
    """List all prompt templates and versions."""
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
    """Return prompt metadata for a specific template."""
    versions = list_prompt_versions(name)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    active = get_active_version(name)
    ab = get_ab_test(name)
    return {
        "name": name,
        "versions": versions,
        "active": active,
        "ab_test": ab.to_dict() if ab else None,
    }


@router.get("/prompts/{name}/template")
async def get_prompt_template_content(name: str) -> dict[str, Any]:
    """Return raw prompt template content."""
    raw = get_prompt_template_raw(name)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found")
    return {"name": name, "template": raw}


@router.post("/prompts/{name}/versions")
async def create_prompt_version(
    name: str,
    req: RegisterVersionRequest,
) -> dict[str, Any]:
    """Register a new prompt version."""
    version = register_prompt_version(
        prompt_name=name,
        template=req.template,
        version=req.version,
        activate=req.activate,
    )
    logger.info(
        "Prompt '{}' registered version {} activate={}",
        name,
        version,
        req.activate,
    )
    return {
        "prompt": name,
        "registered_version": version,
        "active": get_active_version(name),
    }


@router.put("/prompts/{name}/active")
async def change_active_version(
    name: str,
    req: SetActiveRequest,
) -> dict[str, Any]:
    """Change the active prompt version."""
    set_active_version(name, req.version)
    logger.info("Prompt '{}' active version set to {}", name, req.version)
    return {
        "prompt": name,
        "active": get_active_version(name),
    }


@router.post("/prompts/{name}/ab-test")
async def start_ab_test(
    name: str,
    req: ABTestRequest,
) -> dict[str, Any]:
    """Start an A/B test for a prompt."""
    cfg = set_ab_test(
        prompt_name=name,
        canary_version=req.canary_version,
        traffic_fraction=req.traffic_fraction,
    )
    logger.info(
        "Prompt '{}' A/B test started with canary={} traffic={}",
        name,
        req.canary_version,
        req.traffic_fraction,
    )
    return {
        "prompt": name,
        "active": get_active_version(name),
        "ab_test": cfg.to_dict(),
    }


@router.delete("/prompts/{name}/ab-test")
async def remove_ab_test(name: str) -> dict[str, Any]:
    """Stop an A/B test for a prompt."""
    stop_ab_test(name)
    logger.info("Prompt '{}' A/B test removed", name)
    return {"prompt": name, "ab_test": None}


@router.get("/prompts/{name}/ab-test")
async def get_ab_test_config(name: str) -> dict[str, Any]:
    """Return current A/B test configuration, or null if none."""
    ab = get_ab_test(name)
    return {
        "prompt": name,
        "ab_test": ab.to_dict() if ab else None,
    }
