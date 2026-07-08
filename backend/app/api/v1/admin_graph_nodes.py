"""Admin graph node CRUD endpoints — extracted from admin.py (Phase 7 admin domain split).

业务说明：图谱节点管理 API（CRUD + 审核），依赖 Neo4j driver。
注册到 admin.py 的主 router（prefix="/admin"），最终路径形如 /admin/graph/nodes/{id}。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from app.core.matching.constants import ALLOWED_NODE_LABELS
from app.dependencies import get_neo4j_driver

# ponytail: alias matches the pre-existing local name used in admin.py
_ALLOWED_LABELS = ALLOWED_NODE_LABELS


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


router = APIRouter(tags=["graph-nodes"])


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
