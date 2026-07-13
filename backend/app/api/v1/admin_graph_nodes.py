"""Admin graph node CRUD endpoints — thin HTTP layer over admin_graph_service.

Extracted from admin.py (Phase 7 admin domain split).
Registered to admin.py's main router (prefix="/admin"), final paths like /admin/graph/nodes/{id}.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

import neo4j.exceptions

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from app.core.matching.constants import ALLOWED_NODE_LABELS
from app.dependencies import get_neo4j_driver
from app.services.admin_graph_service import GraphNodeService

_ALLOWED_LABELS = ALLOWED_NODE_LABELS


class GraphNodeItem(BaseModel):
    id: str = Field(default="")
    type: Literal["Position", "Skill", "Tool", "KnowledgeArea", "Domain", "Industry", "Certificate", "LearningResource"] = Field(..., description="Node label")
    name: str = Field(..., min_length=1, max_length=200)
    properties: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="approved")
    created_at: str | None = None


class GraphNodeListResponse(BaseModel):
    items: list[GraphNodeItem] = Field(default_factory=list)
    total: int = 0


router = APIRouter(tags=["graph-nodes"])


def _item_from_dict(data: dict[str, Any]) -> GraphNodeItem:
    return GraphNodeItem(
        id=data.get("id", ""),
        type=data.get("type", ""),
        name=data.get("name", ""),
        properties=data.get("properties", {}),
        status=data.get("status", "approved"),
    )


@router.get("/graph/nodes", response_model=GraphNodeListResponse)
async def list_graph_nodes(
    driver: Any = Depends(get_neo4j_driver),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str, Query(max_length=200)] = "",
    node_type: str = "",
) -> GraphNodeListResponse:
    """List graph nodes with pagination and optional filtering."""
    if driver is None:
        return GraphNodeListResponse(items=[], total=0)

    service = GraphNodeService(driver)
    try:
        result = await service.list_nodes(
            offset=offset, limit=limit, search=search, node_type=node_type
        )
        items = [_item_from_dict(n) for n in result["items"]]
        return GraphNodeListResponse(items=items, total=result["total"])
    except (ValueError, KeyError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to list graph nodes: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to list graph nodes") from exc


@router.post("/graph/nodes", response_model=GraphNodeItem)
async def create_graph_node(
    body: GraphNodeItem,
    driver: Any = Depends(get_neo4j_driver),
) -> GraphNodeItem:
    """Create a new graph node."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    if body.type not in _ALLOWED_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label: {body.type}. Allowed: {sorted(_ALLOWED_LABELS)}",
        )

    service = GraphNodeService(driver)
    try:
        result = await service.create_node(
            node_type=body.type, name=body.name, properties=body.properties
        )
        return _item_from_dict(result)
    except (ValueError, KeyError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to create graph node: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to create graph node") from exc


@router.put("/graph/nodes/{node_id:path}", response_model=GraphNodeItem)
async def update_graph_node(
    node_id: str,
    body: GraphNodeItem,
    driver: Any = Depends(get_neo4j_driver),
) -> GraphNodeItem:
    """Update an existing graph node."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    if body.type not in _ALLOWED_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label: {body.type}. Allowed: {sorted(_ALLOWED_LABELS)}",
        )

    service = GraphNodeService(driver)
    try:
        result = await service.update_node(
            node_id, node_type=body.type, name=body.name, properties=body.properties
        )
        return _item_from_dict(result)
    except KeyError:
        raise HTTPException(status_code=404, detail="Node not found") from None
    except (ValueError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to update graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update graph node") from exc


@router.delete("/graph/nodes/{node_id:path}")
async def delete_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    """Delete a graph node and its relationships."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    service = GraphNodeService(driver)
    try:
        deleted = await service.delete_node(node_id)
        return {"ok": True, "deleted": deleted}
    except KeyError:
        raise HTTPException(status_code=404, detail="Node not found") from None
    except (ValueError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to delete graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete graph node") from exc


@router.post("/graph/nodes/{node_id:path}/approve")
async def approve_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    """Approve a graph node (set review_status to 'approved')."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    service = GraphNodeService(driver)
    try:
        return await service.set_review_status(node_id, "approved")
    except KeyError:
        raise HTTPException(status_code=404, detail="Node not found") from None
    except (ValueError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to approve graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail="Failed to approve graph node") from exc


@router.post("/graph/nodes/{node_id:path}/reject")
async def reject_graph_node(
    node_id: str,
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    """Reject a graph node (set review_status to 'rejected')."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    service = GraphNodeService(driver)
    try:
        return await service.set_review_status(node_id, "rejected")
    except KeyError:
        raise HTTPException(status_code=404, detail="Node not found") from None
    except (ValueError, RuntimeError, neo4j.exceptions.Neo4jError) as exc:
        logger.error("Failed to reject graph node {}: {}", node_id, exc)
        raise HTTPException(status_code=500, detail="Failed to reject graph node") from exc
