"""Neo4j-backed graph query helpers for API v1."""
from __future__ import annotations

from typing import Any

WRITE_CYPHER_KEYWORDS = {
    "CREATE",
    "MERGE",
    "SET",
    "DELETE",
    "DETACH",
    "REMOVE",
    "DROP",
    "LOAD",
    "CALL DBMS",
}


def ensure_readonly_cypher(cypher: str) -> None:
    """Reject obvious write/admin Cypher before executing user supplied queries."""
    normalized = " ".join(cypher.upper().split())
    for keyword in WRITE_CYPHER_KEYWORDS:
        if keyword in normalized:
            raise ValueError(f"Cypher contains forbidden keyword: {keyword}")


def _safe_properties(value: Any) -> dict[str, Any]:
    try:
        return dict(value)
    except Exception:
        return {}


def _node_id(node: Any) -> str:
    element_id = getattr(node, "element_id", None)
    if element_id is not None:
        return str(element_id)
    node_id = getattr(node, "id", None)
    if node_id is not None:
        return str(node_id)
    props = _safe_properties(node)
    return str(props.get("id") or props.get("name") or "")


def _relationship_type(rel: Any) -> str:
    rel_type = getattr(rel, "type", None)
    if rel_type is not None:
        return str(rel_type)
    return rel.__class__.__name__


def _relationship_endpoint(rel: Any, attr: str) -> str:
    node = getattr(rel, attr, None)
    if node is not None:
        return _node_id(node)
    value = getattr(rel, f"{attr}_node_id", None)
    return "" if value is None else str(value)


def serialize_node(node: Any) -> dict[str, Any]:
    """Convert a Neo4j Node-like object to the frontend graph node contract."""
    props = _safe_properties(node)
    labels = list(getattr(node, "labels", []) or [])
    category = props.get("category") or (labels[0] if labels else "unknown")
    name = props.get("name") or props.get("title") or _node_id(node)
    props.setdefault("name", name)
    props.setdefault("category", category)
    return {
        "id": _node_id(node),
        "labels": labels,
        "properties": props,
    }


def serialize_relationship(rel: Any) -> dict[str, Any]:
    """Convert a Neo4j Relationship-like object to the frontend graph edge contract."""
    props = _safe_properties(rel)
    props.setdefault("weight", 1.0)
    return {
        "source_id": _relationship_endpoint(rel, "start_node"),
        "target_id": _relationship_endpoint(rel, "end_node"),
        "type": _relationship_type(rel),
        "properties": props,
    }


def dedupe_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Remove duplicate graph elements while preserving first-seen order."""
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id:
            node_map.setdefault(node_id, node)

    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        key = (str(edge.get("source_id", "")), str(edge.get("target_id", "")), str(edge.get("type", "")))
        if all(key):
            edge_map.setdefault(key, edge)

    return {"nodes": list(node_map.values()), "edges": list(edge_map.values())}


def _proficiency_from_level(level: Any) -> str:
    raw = str(level or "").strip().lower()
    if raw in {"精通", "advanced", "expert", "senior", "high"}:
        return "精通"
    if raw in {"了解", "beginner", "basic", "junior", "low"}:
        return "了解"
    return "熟悉"


def _position_item(node: dict[str, Any]) -> dict[str, Any]:
    props = dict(node.get("properties") or {})
    return {
        "position_id": str(props.get("position_id") or node.get("id") or props.get("name") or ""),
        "name": props.get("name") or node.get("id") or "",
        "industry": props.get("industry") or "",
        "description": props.get("description") or "",
        "skills_required": props.get("skills_required") or [],
    }


def _skill_item(node: dict[str, Any], rel: dict[str, Any] | None = None) -> dict[str, Any]:
    props = dict(node.get("properties") or {})
    rel_props = dict((rel or {}).get("properties") or {})
    level = rel_props.get("level")
    required = rel_props.get("required", True)
    category = props.get("category") or props.get("source_category") or "hard_skill"
    if category == "Skill":
        category = props.get("source_category") or "hard_skill"
    return {
        "skill_id": str(props.get("skill_id") or node.get("id") or props.get("name") or ""),
        "name": props.get("name") or node.get("id") or "",
        "category": category,
        "proficiency": props.get("proficiency") or _proficiency_from_level(level),
        "confidence": float(props.get("confidence") or rel_props.get("confidence") or 1.0),
        "source_count": int(props.get("source_count") or 0),
        "trend": props.get("trend") or "stable",
        "importance": "required" if required is not False else "bonus",
    }


async def fetch_panorama(driver: Any, limit: int = 500) -> dict[str, list[dict[str, Any]]]:
    """Fetch the global graph view used by the frontend panorama page."""
    if driver is None:
        return {"nodes": [], "edges": []}

    query = """
    MATCH (source)-[rel]->(target)
    RETURN source, rel, target
    LIMIT $limit
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    async with driver.session() as session:
        result = await session.run(query, limit=limit)
        async for record in result:
            nodes.append(serialize_node(record["source"]))
            nodes.append(serialize_node(record["target"]))
            edges.append(serialize_relationship(record["rel"]))

    return dedupe_graph(nodes, edges)


async def run_readonly_query(driver: Any, cypher: str, limit: int = 500) -> dict[str, list[dict[str, Any]]]:
    """Run a read-only Cypher query and serialize any node/relationship results."""
    ensure_readonly_cypher(cypher)
    if driver is None:
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    async with driver.session() as session:
        result = await session.run(cypher, limit=limit)
        async for record in result:
            for value in record.values():
                labels = getattr(value, "labels", None)
                rel_type = getattr(value, "type", None)
                if labels is not None:
                    nodes.append(serialize_node(value))
                elif rel_type is not None:
                    edges.append(serialize_relationship(value))

    return dedupe_graph(nodes, edges)


async def fetch_position_graph(driver: Any, position_name: str, depth: int = 1) -> dict[str, Any]:
    """Fetch a position and its required skills as a subgraph."""
    if driver is None:
        return {"position": None, "skills": [], "edges": []}

    query = """
    MATCH (position:Position)
    WHERE position.name = $name OR elementId(position) = $name
    OPTIONAL MATCH (position)-[rel:REQUIRES]->(skill:Skill)
    RETURN position, rel, skill
    LIMIT 200
    """
    position: dict[str, Any] | None = None
    skills: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    skill_ids: set[str] = set()

    async with driver.session() as session:
        result = await session.run(query, name=position_name, depth=depth)
        async for record in result:
            if record["position"] is not None and position is None:
                position = _position_item(serialize_node(record["position"]))
            if record["skill"] is not None:
                skill_node = serialize_node(record["skill"])
                rel = serialize_relationship(record["rel"]) if record["rel"] is not None else None
                if skill_node["id"] not in skill_ids:
                    skill_ids.add(skill_node["id"])
                    skills.append(_skill_item(skill_node, rel))
            if record["rel"] is not None:
                edges.append(serialize_relationship(record["rel"]))

    return {"position": position, "skills": skills, "edges": dedupe_graph([], edges)["edges"]}
