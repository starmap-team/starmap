"""Admin graph-node CRUD service — extracted from admin_graph_nodes.py.

Encapsulates all Neo4j Cypher queries for the admin panel so that
api/v1/admin_graph_nodes.py remains a thin HTTP layer.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.matching.constants import ALLOWED_NODE_LABELS

_ALLOWED_LABELS = ALLOWED_NODE_LABELS


class GraphNodeService:
    """Service for admin graph-node CRUD operations."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_nodes(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str = "",
        node_type: str = "",
    ) -> dict[str, Any]:
        """Return paginated graph nodes with optional filtering."""
        if self._driver is None:
            return {"items": [], "total": 0}

        nodes: list[dict[str, Any]] = []
        total = 0

        async with self._driver.session() as session:
            where_clauses: list[str] = []
            if search:
                where_clauses.append("n.name CONTAINS $search")
            if node_type and node_type in _ALLOWED_LABELS:
                where_clauses.append(f"n:{node_type}")
            elif node_type:
                logger.warning("Ignoring invalid node_type filter: {!r} (not in ALLOWED_LABELS)", node_type)

            where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            count_query = f"MATCH (n){where_str} RETURN count(n) as total"
            count_result = await session.run(
                count_query, {"search": search} if search else {}
            )
            count_record = await count_result.single()
            total = count_record["total"] if count_record else 0

            query = f"MATCH (n){where_str} RETURN n SKIP $offset LIMIT $limit"
            result = await session.run(
                query,
                {"offset": offset, "limit": limit, "search": search}
                if search
                else {"offset": offset, "limit": limit},
            )

            async for record in result:
                node = record["n"]
                if node is None:
                    continue
                labels = list(node.labels)
                valid_labels = [lb for lb in labels if lb in _ALLOWED_LABELS]
                if not valid_labels:
                    continue
                props = dict(node)
                props = {
                    k: str(v)
                    if not isinstance(v, (str, int, float, bool, list, dict, type(None)))
                    else v
                    for k, v in props.items()
                }
                node_type_label = valid_labels[0]
                nodes.append(
                    {
                        # BUG-8 fix: prefer canonical_id (UUID) over Neo4j internal
                        # elementId (opaque hex like 4:xxx:yyy). Fall back to
                        # elementId only if canonical_id is missing (e.g. legacy nodes).
                        "id": str(props.get("canonical_id") or node.element_id),
                        "element_id": str(node.element_id),
                        "type": node_type_label,
                        "name": props.get("name", ""),
                        "properties": props,
                        "status": props.get("review_status", "pending"),
                    }
                )

        return {"items": nodes, "total": total}

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_node(self, *, node_type: str, name: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a new graph node and return its metadata."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        if node_type not in _ALLOWED_LABELS:
            raise ValueError(
                f"Invalid label: {node_type}. Allowed: {sorted(_ALLOWED_LABELS)}"
            )

        # BUG-9 fix: respect caller-provided status if any; otherwise pending.
        # Previously hard-coded "pending" — admins couldn't create pre-approved nodes.
        import uuid as _uuid

        props = {**properties, "name": name}
        if "review_status" not in props:
            props["review_status"] = "pending"
        # BUG-8 fix: stamp canonical_id for round-tripping to PG/UI
        if "canonical_id" not in props:
            props["canonical_id"] = str(_uuid.uuid4())
        async with self._driver.session() as session:
            query = (
                f"CREATE (n:{node_type} {{name: $name}}) SET n += $props "
                "RETURN elementId(n) AS eid"
            )
            result = await session.run(query, {"name": name, "props": props})
            record = await result.single()
            eid = str(record["eid"]) if record else ""
            logger.info("Created graph node: {} ({})", name, node_type)
            return {
                "id": props["canonical_id"],
                "element_id": eid,
                "type": node_type,
                "name": name,
                "properties": props,
                "status": props["review_status"],
            }

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_node(
        self, node_id: str, *, node_type: str, name: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing graph node."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        if node_type not in _ALLOWED_LABELS:
            raise ValueError(
                f"Invalid label: {node_type}. Allowed: {sorted(_ALLOWED_LABELS)}"
            )

        props = {**properties, "name": name}
        # BUG-10 fix: never let `properties` clobber review_status —
        # that's a workflow state and must go through the proper approve/reject
        # endpoint, not the generic edit form.
        props.pop("review_status", None)
        async with self._driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "SET n += $props "
                "RETURN n"
            )
            result = await session.run(query, {"eid": node_id, "props": props})
            record = await result.single()
            if not record:
                raise KeyError(f"Node {node_id} not found")

            original_status = record["n"].get("review_status", "pending")
            logger.info("Updated graph node: {}", node_id)
            return {
                "id": node_id,
                "type": node_type,
                "name": name,
                "properties": props,
                "status": original_status,
            }

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_node(self, node_id: str) -> int:
        """Delete a graph node and its relationships. Returns number of deleted nodes."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        async with self._driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "DETACH DELETE n RETURN count(n) AS deleted"
            )
            result = await session.run(query, {"eid": node_id})
            record = await result.single()
            deleted = record["deleted"] if record else 0
            if deleted == 0:
                raise KeyError(f"Node {node_id} not found")
            logger.info("Deleted graph node: {}", node_id)
            return int(deleted)

    # ------------------------------------------------------------------
    # Review status
    # ------------------------------------------------------------------

    async def set_review_status(self, node_id: str, status: str) -> dict[str, Any]:
        """Set the review_status of a node to 'approved' or 'rejected'."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not available")

        async with self._driver.session() as session:
            query = (
                "MATCH (n) WHERE elementId(n) = $eid "
                "SET n.review_status = $status "
                "RETURN n"
            )
            result = await session.run(query, {"eid": node_id, "status": status})
            record = await result.single()
            if not record:
                raise KeyError(f"Node {node_id} not found")
            return {"ok": True, "status": status}
