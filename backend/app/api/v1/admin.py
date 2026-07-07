"""Admin API.

This file was sanitized to ASCII-only because the original Chinese
docstrings contained non-printable characters that caused runtime
SyntaxError during uvicorn reload.
"""

from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quality import _build_quality_dashboard
from app.config import settings
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
from app.core.matching.constants import ALLOWED_NODE_LABELS
from app.dependencies import get_db_session, get_neo4j_driver
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    ReviewQueue,
    SkillRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class SourceConfig(BaseModel):
    id: int
    name: str
    authority_score: float = Field(ge=0.0, le=1.0)
    source_type: str
    record_count: int = 0


class SourceListResponse(BaseModel):
    items: list[SourceConfig] = Field(default_factory=list)


class AuditItem(BaseModel):
    id: int
    type: str
    name: str
    trust: int = Field(ge=0, le=100)
    status: str


class AuditUpdateRequest(BaseModel):
    """Partial update for a review-queue item."""

    name: str | None = Field(default=None, min_length=1)
    trust: int | None = Field(default=None, ge=0, le=100)


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


_DEMO_REVIEW_SEED = [
    {"entity_type": "skill", "entity_name": "AI Agent Dev", "status": "pending", "payload": {"trust": 58}},
    {"entity_type": "position", "entity_name": "LLM Application Engineer", "status": "pending", "payload": {"trust": 64}},
    {"entity_type": "skill", "entity_name": "Spring AI", "status": "pending", "payload": {"trust": 72}},
    {"entity_type": "skill", "entity_name": "RAG", "status": "pending", "payload": {"trust": 45}},
]

_ALLOWED_LABELS = ALLOWED_NODE_LABELS


async def _build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    dashboard = await _build_quality_dashboard(session)

    try:
        # Run separate queries to avoid cartesian product across 4 unrelated tables.
        total_positions = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(PositionRecord)
            )).scalar() or 0
        )
        total_skills = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(SkillRecord)
            )).scalar() or 0
        )
        total_edges = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(PositionSkillRelation)
            )).scalar() or 0
        )
        avg_value = float(
            (await session.execute(
                sa.select(
                    sa.func.coalesce(
                        sa.func.avg(JDExtractionRecord.confidence), 0.0
                    )
                )
            )).scalar() or 0.0
        )

        # Count pending review items from DB
        pending_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
                .where(ReviewQueue.status == "pending")
            )).scalar() or 0
        )
    except Exception:
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0

    return AdminStatsResponse(
        total_nodes=total_positions + total_skills,
        total_edges=total_edges,
        total_positions=total_positions,
        total_skills=total_skills,
        avg_confidence=avg_value,
        hallucination_rate=dashboard.hallucination_rate,
        pending_review=pending_count,
    )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """Admin overview stats."""
    return await _build_admin_stats(session)


@router.get("/sources", response_model=SourceListResponse)
async def get_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceListResponse:
    """Return data sources from actual crawl data."""
    try:
        result = await session.execute(
            sa.text("SELECT source_platform, COUNT(*) as cnt FROM raw_jd_records GROUP BY source_platform ORDER BY cnt DESC")
        )
        rows = result.fetchall()
        sources = []
        platform_scores = settings.authority_scores
        for idx, (platform, cnt) in enumerate(rows, 1):
            score = platform_scores.get(platform, settings.authority_default_score)
            stype = "official" if score >= 0.85 else "aggregator"
            sources.append(SourceConfig(
                id=idx, name=platform, authority_score=score,
                source_type=stype, record_count=cnt,
            ))
        return SourceListResponse(items=sources)
    except Exception as exc:
        logger.warning("Failed to query data sources: {}", exc)
        return SourceListResponse(items=[])


@router.get("/review-queue", response_model=AuditQueueResponse)
@router.get("/audit-queue", response_model=AuditQueueResponse, include_in_schema=False)
async def get_review_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditQueueResponse:
    """Return pending review items from DB; auto-seed if table is empty."""


    try:
        # Check if there are any rows at all in the review_queue table
        total_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
            )).scalar() or 0
        )

        if total_count == 0:
            # Auto-seed from template data (only once, when table is empty)
            for seed in _DEMO_REVIEW_SEED:
                session.add(ReviewQueue(**seed))
            await session.commit()

        stmt = (
            sa.select(ReviewQueue)
            .where(ReviewQueue.status == "pending")
            .order_by(ReviewQueue.id.desc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
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
        return AuditQueueResponse(items=[])


@router.post("/audit/{item_id}/approve", response_model=AuditItem)
async def approve_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Approve a review queue item."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
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


@router.post("/audit/{item_id}/reject", response_model=AuditItem)
async def reject_audit(
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Reject a review queue item."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")
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


@router.put("/review-queue/{item_id}", response_model=AuditItem)
@router.patch("/review-queue/{item_id}", response_model=AuditItem, include_in_schema=False)
async def update_review_queue_item(
    item_id: int,
    body: AuditUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditItem:
    """Update name and/or trust of a review queue item (ADMIN-02 save loop)."""


    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit item not found")

    if body.name is not None:
        row.entity_name = body.name
    if body.trust is not None:
        # ponytail: reassign dict so SQLAlchemy JSON dirty-tracking fires
        payload = dict(row.payload or {})
        payload["trust"] = body.trust
        row.payload = payload
    await session.commit()

    trust = int((row.payload or {}).get("trust", 50))
    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=trust,
        status=row.status,
    )


@router.post("/seed/reset", response_model=ResetDemoResponse)
@router.post("/reset-demo", response_model=ResetDemoResponse, include_in_schema=False)
async def reset_demo_seed(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResetDemoResponse:
    """Reset demo review queue state — re-seed the review_queue table."""


    # Clear existing pending review items
    await session.execute(
        sa.delete(ReviewQueue).where(ReviewQueue.status == "pending")
    )

    # Seed default demo items from shared template
    demo_items = [ReviewQueue(**seed) for seed in _DEMO_REVIEW_SEED]
    for item in demo_items:
        session.add(item)
    await session.commit()

    return ResetDemoResponse(ok=True, review_items=len(demo_items))


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

# ── Graph Node CRUD (for Admin panel) ──


class GraphNodeItem(BaseModel):
    id: str = Field(default="")
    type: str = Field(..., description="Node label: Position, Skill, Tool, KnowledgeArea")
    name: str = Field(..., min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="approved")
    created_at: str | None = None


class GraphNodeListResponse(BaseModel):
    items: list[GraphNodeItem] = Field(default_factory=list)
    total: int = 0


@router.get("/graph/nodes", response_model=GraphNodeListResponse)
async def list_graph_nodes(
    driver: Any = Depends(get_neo4j_driver),
    limit: int = Query(200, ge=1, le=1000),
) -> GraphNodeListResponse:
    if driver is None:
        return GraphNodeListResponse(items=[], total=0)
    nodes: list[GraphNodeItem] = []
    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) RETURN n LIMIT $limit",
                {"limit": limit},
            )
            async for record in result:
                node = record["n"]
                if node is None:
                    continue
                labels = list(node.labels)
                # Only include nodes with whitelisted labels
                valid_labels = [lb for lb in labels if lb in _ALLOWED_LABELS]
                if not valid_labels:
                    continue
                props = dict(node)
                props = {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v for k, v in props.items()}
                node_type = valid_labels[0]
                nodes.append(GraphNodeItem(
                    id=str(node.element_id),
                    type=node_type,
                    name=props.get("name", ""),
                    properties=props,
                    status="approved",
                ))
    except Exception as exc:
        logger.error("Failed to list graph nodes: {}", exc)
    return GraphNodeListResponse(items=nodes, total=len(nodes))


@router.post("/graph/nodes", response_model=GraphNodeItem)
async def create_graph_node(
    body: GraphNodeItem,
    driver: Any = Depends(get_neo4j_driver),
) -> GraphNodeItem:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    # Whitelist allowed node labels to prevent Cypher injection
    if body.type not in _ALLOWED_LABELS:
        raise HTTPException(status_code=400, detail=f"Invalid label: {body.type}. Allowed: {sorted(_ALLOWED_LABELS)}")
    label = body.type
    props = {**body.properties, "name": body.name}
    try:
        async with driver.session() as session:
            # Label is safe (validated against whitelist above).
            # Neo4j does not support parameterized labels, so we use
            # f-string for the label only after strict whitelist check.
            # All property values use parameterized queries.
            query = (
                f"CREATE (n:{label} {{name: $name}}) SET n += $props "
                "RETURN elementId(n) AS eid"
            )
            result = await session.run(query, {"name": body.name, "props": props})
            record = await result.single()
            eid = str(record["eid"]) if record else ""
            logger.info("Created graph node: {} ({})", body.name, label)
            return GraphNodeItem(
                id=eid, type=label, name=body.name,
                properties=props, status="pending",
            )
    except Exception as exc:
        logger.error("Failed to create graph node: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/graph/nodes/{node_id:path}", response_model=GraphNodeItem)
async def update_graph_node(
    node_id: str,
    body: GraphNodeItem,
    driver: Any = Depends(get_neo4j_driver),
) -> GraphNodeItem:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    # Validate label against whitelist
    if body.type not in _ALLOWED_LABELS:
        raise HTTPException(status_code=400, detail=f"Invalid label: {body.type}. Allowed: {sorted(_ALLOWED_LABELS)}")
    props = {**body.properties, "name": body.name}
    try:
        async with driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "SET n += $props "
                "RETURN n"
            )
            result = await session.run(query, {"eid": node_id, "props": props})
            record = await result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Node not found")
            logger.info("Updated graph node: {}", node_id)
            return GraphNodeItem(
                id=node_id, type=body.type, name=body.name,
                properties=props, status="approved",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/graph/nodes/{node_id:path}")
async def delete_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    try:
        async with driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "DETACH DELETE n RETURN count(n) AS deleted"
            )
            result = await session.run(query, {"eid": node_id})
            record = await result.single()
            deleted = record["deleted"] if record else 0
            if deleted == 0:
                raise HTTPException(status_code=404, detail="Node not found")
            logger.info("Deleted graph node: {}", node_id)
            return {"ok": True, "deleted": deleted}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph/nodes/{node_id:path}/approve")
async def approve_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    try:
        async with driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "SET n.review_status = $status "
                "RETURN n"
            )
            result = await session.run(query, {"eid": node_id, "status": "approved"})
            record = await result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Node not found")
            return {"ok": True, "status": "approved"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph/nodes/{node_id:path}/reject")
async def reject_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    try:
        async with driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "SET n.review_status = $status "
                "RETURN n"
            )
            result = await session.run(query, {"eid": node_id, "status": "rejected"})
            record = await result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Node not found")
            return {"ok": True, "status": "rejected"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
