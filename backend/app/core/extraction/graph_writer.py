"""Async Neo4j graph writer for extraction results.

Spec §2.1: 7 node types — Position, Skill, KnowledgeArea, Tool, Certificate, LearningResource, Industry
Spec §2.2: 8 relationship types — REQUIRES, PREREQUISITE, EVOLVES_TO, USES, BELONGS_TO, CERTIFIES, RECOMMENDED_FOR, APPLIES_TO
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

# ---- Node type labels (§2.1: 7类节点) ----
NODE_POSITION = "Position"
NODE_SKILL = "Skill"
NODE_KNOWLEDGE_AREA = "KnowledgeArea"
NODE_TOOL = "Tool"
NODE_CERTIFICATE = "Certificate"
NODE_LEARNING_RESOURCE = "LearningResource"
NODE_INDUSTRY = "Industry"

# ---- Relationship types (§2.2: 8类关系) ----
REL_REQUIRES = "REQUIRES"           # Position -> Skill (required:bool, weight:float)
REL_PREREQUISITE = "PREREQUISITE"   # Skill -> Skill (strength:float)
REL_EVOLVES_TO = "EVOLVES_TO"       # Position -> Position (similarity:float, evidence_count)
REL_USES = "USES"                   # Position/Skill -> Tool
REL_BELONGS_TO = "BELONGS_TO"       # Position -> Industry
REL_CERTIFIES = "CERTIFIES"         # Certificate -> Skill
REL_RECOMMENDED_FOR = "RECOMMENDED_FOR"  # LearningResource -> Skill (rank:float)
REL_APPLIES_TO = "APPLIES_TO"       # KnowledgeArea -> Industry

ALLOWED_NODE_LABELS = {
    NODE_POSITION,
    NODE_SKILL,
    NODE_KNOWLEDGE_AREA,
    NODE_TOOL,
    NODE_CERTIFICATE,
    NODE_LEARNING_RESOURCE,
    NODE_INDUSTRY,
}

ALLOWED_RELATIONSHIP_TYPES = {
    REL_REQUIRES,
    REL_PREREQUISITE,
    REL_EVOLVES_TO,
    REL_USES,
    REL_BELONGS_TO,
    REL_CERTIFIES,
    REL_RECOMMENDED_FOR,
    REL_APPLIES_TO,
}


@dataclass(frozen=True)
class GraphNodeRef:
    """A validated graph node reference used by triple ingestion."""

    label: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphTriple:
    """A graph triple: source node, relationship type, target node, relationship properties."""

    source: GraphNodeRef
    relationship: str
    target: GraphNodeRef
    properties: dict[str, Any] = field(default_factory=dict)


def _validate_node_label(label: str) -> str:
    if label not in ALLOWED_NODE_LABELS:
        raise ValueError(f"Unsupported graph node label: {label}")
    return label


def _validate_relationship_type(relationship: str) -> str:
    if relationship not in ALLOWED_RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported graph relationship type: {relationship}")
    return relationship


def _clean_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Drop empty values before sending properties to Neo4j."""
    cleaned: dict[str, Any] = {}
    for key, value in (properties or {}).items():
        if value is not None:
            cleaned[key] = value
    return cleaned


def _node_ref(label: str, name: str, properties: dict[str, Any] | None = None) -> GraphNodeRef:
    label = _validate_node_label(label)
    name = str(name).strip()
    if not name:
        raise ValueError("Graph node name cannot be empty")
    props = _clean_properties(properties)
    props.setdefault("name", name)
    props.setdefault("category", label)
    return GraphNodeRef(label=label, name=name, properties=props)


def _skill_entry_name(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("name") or entry.get("skill") or entry.get("title") or "").strip()
    return str(entry).strip()


def _skill_entry_level(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("level") or entry.get("proficiency") or "intermediate")
    return "intermediate"


def _normalize_proficiency(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"精通", "expert", "advanced", "senior", "high"}:
        return "精通"
    if raw in {"了解", "beginner", "basic", "junior", "low"}:
        return "了解"
    return "熟悉"


def _skill_entry_category(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("category") or "skill").lower()
    return "skill"


def _skill_entry_years(entry: Any) -> float | None:
    if isinstance(entry, dict):
        value = entry.get("years_of_experience")
        return float(value) if value is not None else None
    return None


def _skill_entry_confidence(entry: Any) -> float:
    if isinstance(entry, dict):
        value = entry.get("confidence")
        return float(value) if value is not None else 0.8
    return 0.8


def _skill_entry_source_count(entry: Any) -> int:
    if isinstance(entry, dict):
        value = entry.get("source_count")
        return int(value) if value is not None else 1
    return 1


def _skill_entry_trend(entry: Any) -> str:
    if isinstance(entry, dict):
        trend = str(entry.get("trend") or "stable")
        if trend in {"rising", "stable", "declining"}:
            return trend
    return "stable"


def _skill_node_properties(entry: Any, category: str, level: str) -> dict[str, Any]:
    return {
        "category": category,
        "source_category": category,
        "proficiency": _normalize_proficiency(level),
        "confidence": _skill_entry_confidence(entry),
        "source_count": _skill_entry_source_count(entry),
        "trend": _skill_entry_trend(entry),
    }


def _node_merge_properties(node: GraphNodeRef) -> dict[str, Any]:
    props = _clean_properties(node.properties)
    if node.label == NODE_SKILL:
        props.pop("source_count", None)
    return props


def _skill_source_count_increment(node: GraphNodeRef) -> int:
    if node.label != NODE_SKILL:
        return 0
    value = node.properties.get("source_count")
    return int(value) if value is not None else 0


def _append_unique(triples: list[GraphTriple], triple: GraphTriple) -> None:
    key = (
        triple.source.label,
        triple.source.name,
        triple.relationship,
        triple.target.label,
        triple.target.name,
    )
    for existing in triples:
        existing_key = (
            existing.source.label,
            existing.source.name,
            existing.relationship,
            existing.target.label,
            existing.target.name,
        )
        if existing_key == key:
            return
    triples.append(triple)


def build_triples_from_extraction(extraction: dict[str, Any]) -> list[GraphTriple]:
    """Convert a normalized extraction result into ontology triples.

    The conversion is intentionally conservative: JD skills become Position->Skill
    REQUIRES edges, tools become Position->Tool USES edges, and optional ontology
    fields such as industry, prerequisites, learning resources, and evolution hints
    are mapped when present.
    """
    position_name = str(extraction.get("position_name") or extraction.get("name") or "").strip()
    if not position_name:
        raise ValueError("Extraction result is missing position_name")

    position = _node_ref(
        NODE_POSITION,
        position_name,
        {
            "experience_required": extraction.get("experience_required"),
            "education_required": extraction.get("education_required"),
        },
    )
    triples: list[GraphTriple] = []

    for required, skills in (
        (True, extraction.get("required_skills", [])),
        (False, extraction.get("preferred_skills", [])),
    ):
        for entry in skills or []:
            skill_name = _skill_entry_name(entry)
            if not skill_name:
                continue

            level = _skill_entry_level(entry)
            category = _skill_entry_category(entry)
            years = _skill_entry_years(entry)
            rel_props = {
                "required": required,
                "level": level,
                "weight": 1.0 if required else 0.6,
                "years_of_experience": years,
            }

            if category == "tool":
                target = _node_ref(NODE_TOOL, skill_name, {"source_category": category})
                _append_unique(triples, GraphTriple(position, REL_USES, target, rel_props))
            elif category == "certificate":
                certificate = _node_ref(NODE_CERTIFICATE, skill_name, {"source_category": category})
                certifies = entry.get("certifies") if isinstance(entry, dict) else None
                if certifies:
                    skill = _node_ref(NODE_SKILL, str(certifies))
                    _append_unique(triples, GraphTriple(certificate, REL_CERTIFIES, skill, {"weight": 1.0}))
            else:
                target = _node_ref(NODE_SKILL, skill_name, _skill_node_properties(entry, category, level))
                _append_unique(triples, GraphTriple(position, REL_REQUIRES, target, rel_props))

    industry_name = extraction.get("industry")
    if industry_name:
        industry = _node_ref(NODE_INDUSTRY, str(industry_name))
        _append_unique(triples, GraphTriple(position, REL_BELONGS_TO, industry, {"weight": 1.0}))
    else:
        industry = None

    for area_name in extraction.get("knowledge_areas", []) or []:
        area = _node_ref(NODE_KNOWLEDGE_AREA, str(area_name))
        if industry is not None:
            _append_unique(triples, GraphTriple(area, REL_APPLIES_TO, industry, {"weight": 1.0}))

    for tool_name in extraction.get("tools", []) or []:
        tool = _node_ref(NODE_TOOL, str(tool_name))
        _append_unique(triples, GraphTriple(position, REL_USES, tool, {"weight": 0.8}))

    for prerequisite in extraction.get("prerequisites", []) or []:
        if not isinstance(prerequisite, dict):
            continue
        skill_name = str(prerequisite.get("skill") or "").strip()
        prerequisite_name = str(prerequisite.get("prerequisite") or "").strip()
        if not skill_name or not prerequisite_name:
            continue
        skill = _node_ref(NODE_SKILL, skill_name)
        required_skill = _node_ref(NODE_SKILL, prerequisite_name)
        strength = float(prerequisite.get("strength") or 0.5)
        _append_unique(triples, GraphTriple(skill, REL_PREREQUISITE, required_skill, {"strength": strength}))

    for resource in extraction.get("learning_resources", []) or []:
        if not isinstance(resource, dict):
            continue
        resource_name = str(resource.get("title") or resource.get("name") or "").strip()
        skill_name = str(resource.get("skill") or "").strip()
        if not resource_name or not skill_name:
            continue
        learning_resource = _node_ref(NODE_LEARNING_RESOURCE, resource_name, {"url": resource.get("url")})
        skill = _node_ref(NODE_SKILL, skill_name)
        rank = float(resource.get("rank") or 0.5)
        _append_unique(triples, GraphTriple(learning_resource, REL_RECOMMENDED_FOR, skill, {"rank": rank}))

    for successor in extraction.get("evolves_to", []) or []:
        if isinstance(successor, dict):
            target_name = str(successor.get("position") or successor.get("name") or "").strip()
            props = {
                "similarity": successor.get("similarity"),
                "evidence_count": successor.get("evidence_count"),
            }
        else:
            target_name = str(successor).strip()
            props = {"similarity": 0.5}
        if target_name:
            target = _node_ref(NODE_POSITION, target_name)
            _append_unique(triples, GraphTriple(position, REL_EVOLVES_TO, target, props))

    return triples


async def merge_triple(driver: Any, triple: GraphTriple) -> dict[str, Any]:
    """MERGE one validated ontology triple into Neo4j."""
    from neo4j.exceptions import Neo4jError

    source_label = _validate_node_label(triple.source.label)
    target_label = _validate_node_label(triple.target.label)
    relationship = _validate_relationship_type(triple.relationship)
    query = f"""
    MERGE (source:{source_label} {{name: $source_name}})
    SET source += $source_props, source.updated_at = datetime()
    MERGE (target:{target_label} {{name: $target_name}})
    SET target += $target_props, target.updated_at = datetime()
    FOREACH (_ IN CASE WHEN $source_label = 'Skill' THEN [1] ELSE [] END |
        SET source.source_count = coalesce(source.source_count, 0) + $source_count_increment,
            source.proficiency = coalesce(source.proficiency, '熟悉'),
            source.trend = coalesce(source.trend, 'stable')
    )
    FOREACH (_ IN CASE WHEN $target_label = 'Skill' THEN [1] ELSE [] END |
        SET target.source_count = coalesce(target.source_count, 0) + $target_count_increment,
            target.proficiency = coalesce(target.proficiency, '熟悉'),
            target.trend = coalesce(target.trend, 'stable')
    )
    MERGE (source)-[rel:{relationship}]->(target)
    SET rel += $rel_props, rel.updated_at = datetime()
    RETURN source, rel, target
    """
    try:
        async with driver.session() as session:
            result = await session.run(
                query,
                source_name=triple.source.name,
                source_label=source_label,
                source_props=_node_merge_properties(triple.source),
                source_count_increment=_skill_source_count_increment(triple.source),
                target_name=triple.target.name,
                target_label=target_label,
                target_props=_node_merge_properties(triple.target),
                target_count_increment=_skill_source_count_increment(triple.target),
                rel_props=_clean_properties(triple.properties),
            )
            record = await result.single()
            if record is None:
                raise ValueError(
                    f"Failed to merge triple: {triple.source.name} "
                    f"-[{relationship}]-> {triple.target.name}"
                )
            return {"source": dict(record["source"]), "relationship": dict(record["rel"]), "target": dict(record["target"])}
    except Neo4jError as e:
        logger.error("Neo4j merge_triple error: {}", e)
        raise


async def write_triples_to_graph(driver: Any, triples: list[GraphTriple]) -> dict[str, int]:
    """Write ontology triples to Neo4j and return aggregate counts."""
    summary = {
        "triples_merged": 0,
        "nodes_touched": 0,
        "relationships_touched": 0,
    }
    touched_nodes: set[tuple[str, str]] = set()
    for triple in triples:
        await merge_triple(driver, triple)
        summary["triples_merged"] += 1
        summary["relationships_touched"] += 1
        touched_nodes.add((triple.source.label, triple.source.name))
        touched_nodes.add((triple.target.label, triple.target.name))
    summary["nodes_touched"] = len(touched_nodes)
    return summary


@dataclass
class GraphConfig:
    """Neo4j database configuration.

    Reads credentials from app.config.settings by default.
    """

    uri: str = field(default_factory=lambda: settings.neo4j_uri)
    user: str = field(default_factory=lambda: settings.neo4j_user)
    password: str = field(default_factory=lambda: settings.neo4j_password)
    max_connection_pool_size: int = 50
    connection_timeout: int = 30

    @asynccontextmanager
    async def get_driver(self) -> AsyncIterator[Any]:
        """Context manager that yields a neo4j async driver.

        Usage:
            async with config.get_driver() as driver:
                async with driver.session() as session:
                    ...
        """
        from neo4j import AsyncGraphDatabase

        driver = None
        try:
            driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
            )
            await driver.verify_connectivity()
            logger.info("Neo4j connected: {}", self.uri)
            yield driver
        finally:
            if driver is not None:
                await driver.close()
                logger.debug("Neo4j driver closed")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def merge_position(driver: Any, position_data: dict[str, Any]) -> dict[str, Any]:
    """MERGE a Position node from extraction data.

    Args:
        driver: Neo4j async driver.
        position_data: Dict with 'name' (required) and optional fields.

    Returns:
        The created/merged node properties dict.
    """
    from neo4j.exceptions import Neo4jError

    name = position_data.get("name", position_data.get("position_name", "Unknown"))
    query = """
    MERGE (p:Position {name: $name})
    SET p.updated_at = datetime(),
        p.experience_required = $experience_required,
        p.education_required = $education_required
    RETURN p
    """
    try:
        async with driver.session() as session:
            result = await session.run(
                query,
                name=name,
                experience_required=position_data.get("experience_required"),
                education_required=position_data.get("education_required"),
            )
            record = await result.single()
            if record is None:
                raise ValueError(f"Failed to merge Position: {name}")
            props = dict(record["p"])
            logger.debug("Merged Position: {}", name)
            return props
    except Neo4jError as e:
        logger.error("Neo4j merge_position error: {}", e)
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def merge_skill(driver: Any, skill_name: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """MERGE a Skill node.

    Args:
        driver: Neo4j async driver.
        skill_name: Standardized skill name.
        metadata: Optional extra properties.

    Returns:
        The created/merged node properties dict.
    """
    from neo4j.exceptions import Neo4jError

    props = _clean_properties(
        {
            **(metadata or {}),
            "proficiency": _normalize_proficiency((metadata or {}).get("proficiency") or (metadata or {}).get("level")),
            "source_count": int((metadata or {}).get("source_count") or 1),
            "trend": (metadata or {}).get("trend") or "stable",
        }
    )
    merge_props = {key: value for key, value in props.items() if key != "source_count"}
    query = """
    MERGE (s:Skill {name: $name})
    SET s += $props,
        s.source_count = coalesce(s.source_count, 0) + $source_count,
        s.updated_at = datetime()
    RETURN s
    """
    try:
        async with driver.session() as session:
            result = await session.run(query, name=skill_name, props=merge_props, source_count=props["source_count"])
            record = await result.single()
            if record is None:
                raise ValueError(f"Failed to merge Skill: {skill_name}")
            props = dict(record["s"])
            logger.debug("Merged Skill: {}", skill_name)
            return props
    except Neo4jError as e:
        logger.error("Neo4j merge_skill error: {}", e)
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def create_requires_relationship(
    driver: Any,
    position_name: str,
    skill_name: str,
    level: str = "intermediate",
    required: bool = True,
    weight: float = 1.0,
) -> dict[str, Any]:
    """Create a REQUIRES relationship between Position and Skill (§2.2).

    Args:
        driver: Neo4j async driver.
        position_name: Position node name.
        skill_name: Skill node name.
        level: Required proficiency level.
        required: Whether this skill is strictly required.
        weight: Weight/importance of this skill for the position.

    Returns:
        Relationship properties dict.
    """
    from neo4j.exceptions import Neo4jError

    query = """
    MATCH (p:Position {name: $position_name})
    MATCH (s:Skill {name: $skill_name})
    MERGE (p)-[r:REQUIRES {level: $level}]->(s)
    SET r.required = $required, r.weight = $weight, r.updated_at = datetime()
    RETURN r
    """
    try:
        async with driver.session() as session:
            result = await session.run(
                query,
                position_name=position_name,
                skill_name=skill_name,
                level=level,
                required=required,
                weight=weight,
            )
            record = await result.single()
            if record is None:
                raise ValueError(f"Failed to create REQUIRES: {position_name} -> {skill_name}")
            props = dict(record["r"])
            logger.debug("Created REQUIRES: {} -> {} ({})", position_name, skill_name, level)
            return props
    except Neo4jError as e:
        logger.error("Neo4j create_requires error: {}", e)
        raise


async def write_extraction_to_graph(
    extraction: dict[str, Any],
    driver: Any,
) -> dict[str, Any]:
    """Write a full extraction result to Neo4j (§2.1/§2.2).

    Creates/merges:
        - Position node
        - Skill nodes (required + preferred)
        - REQUIRES relationships (Position -> Skill)

    Args:
        extraction: Extraction dict from jd_extract pipeline.
        driver: Neo4j async driver.

    Returns:
        Summary dict with counts of created nodes/relationships.
    """
    triples = build_triples_from_extraction(extraction)
    triple_summary = await write_triples_to_graph(driver, triples)

    touched_positions = {
        (triple.source.label, triple.source.name)
        for triple in triples
        if triple.source.label == NODE_POSITION
    } | {
        (triple.target.label, triple.target.name)
        for triple in triples
        if triple.target.label == NODE_POSITION
    }
    touched_skills = {
        (triple.source.label, triple.source.name)
        for triple in triples
        if triple.source.label == NODE_SKILL
    } | {
        (triple.target.label, triple.target.name)
        for triple in triples
        if triple.target.label == NODE_SKILL
    }
    requires_count = sum(1 for triple in triples if triple.relationship == REL_REQUIRES)

    summary: dict[str, int] = {
        "positions_merged": 0,
        "skills_merged": 0,
        "requires_created": 0,
        "triples_merged": triple_summary["triples_merged"],
        "nodes_touched": triple_summary["nodes_touched"],
        "relationships_touched": triple_summary["relationships_touched"],
    }
    summary["positions_merged"] = len(touched_positions)
    summary["skills_merged"] = len(touched_skills)
    summary["requires_created"] = requires_count

    logger.info(
        "Graph write complete: {} positions, {} skills, {} requires, {} triples",
        summary["positions_merged"],
        summary["skills_merged"],
        summary["requires_created"],
        summary["triples_merged"],
    )
    return summary


async def batch_write_extractions(
    extractions: list[dict[str, Any]],
    driver: Any,
) -> list[dict[str, Any]]:
    """Write multiple extractions to Neo4j.

    Args:
        extractions: List of extraction dicts.
        driver: Neo4j async driver.

    Returns:
        List of summary dicts per extraction.
    """
    summaries = []
    for extraction in extractions:
        summary = await write_extraction_to_graph(extraction, driver)
        summaries.append(summary)
    return summaries


async def get_position_skills(driver: Any, position_name: str) -> dict[str, list[dict[str, Any]]]:
    """Get all skills associated with a position.

    Args:
        driver: Neo4j async driver.
        position_name: Position node name.

    Returns:
        Dict with 'required' and 'preferred' skill lists.
    """
    query = """
    MATCH (p:Position {name: $name})-[r:REQUIRES]->(s:Skill)
    RETURN s.name AS skill_name, r.level AS level, r.required AS required
    """
    required = []
    preferred = []

    async with driver.session() as session:
        result = await session.run(query, name=position_name)
        async for record in result:
            entry = {"name": record["skill_name"], "level": record.get("level", "intermediate")}
            is_required = record.get("required", True)
            if is_required is not False:
                required.append(entry)
            else:
                preferred.append(entry)

    return {"required": required, "preferred": preferred}


async def get_all_skills(driver: Any) -> list[dict[str, Any]]:
    """Get all Skill nodes from the graph.

    Args:
        driver: Neo4j async driver.

    Returns:
        List of skill dicts with name and metadata.
    """
    query = """
    MATCH (s:Skill)
    RETURN s.name AS name,
           s.category AS category,
           s.proficiency AS proficiency,
           s.source_count AS source_count,
           s.trend AS trend,
           s.updated_at AS updated_at
    ORDER BY s.name
    """
    skills: list[dict[str, Any]] = []

    async with driver.session() as session:
        result = await session.run(query)
        async for record in result:
            skills.append(
                {
                    "name": record["name"],
                    "category": record.get("category") or "hard_skill",
                    "proficiency": record.get("proficiency") or "熟悉",
                    "source_count": int(record.get("source_count") or 0),
                    "trend": record.get("trend") or "stable",
                    "updated_at": str(record.get("updated_at", "")),
                }
            )

    return skills
