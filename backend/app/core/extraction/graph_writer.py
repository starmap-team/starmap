"""Async Neo4j graph writer for extraction results.

Spec §2.1: 7 node types — Position, Skill, KnowledgeArea, Tool, Certificate, LearningResource, Industry
Spec §2.2: 8 relationship types — REQUIRES, PREREQUISITE, EVOLVES_TO, USES, BELONGS_TO, CERTIFIES, RECOMMENDED_FOR, APPLIES_TO
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

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

    query = """
    MERGE (s:Skill {name: $name})
    SET s.updated_at = datetime()
    RETURN s
    """
    try:
        async with driver.session() as session:
            result = await session.run(query, name=skill_name)
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
    summary: dict[str, int] = {
        "positions_merged": 0,
        "skills_merged": 0,
        "requires_created": 0,
    }

    position_name = extraction.get("position_name", extraction.get("name", "Unknown Position"))

    position_data = {
        "name": position_name,
        "experience_required": extraction.get("experience_required"),
        "education_required": extraction.get("education_required"),
    }
    await merge_position(driver, position_data)
    summary["positions_merged"] = 1

    # Required skills: Position -[REQUIRES]-> Skill
    for skill_entry in extraction.get("required_skills", []):
        skill_name = skill_entry["name"] if isinstance(skill_entry, dict) else skill_entry
        level = skill_entry.get("level", "intermediate") if isinstance(skill_entry, dict) else "intermediate"

        await merge_skill(driver, skill_name)
        summary["skills_merged"] += 1

        await create_requires_relationship(
            driver, position_name, skill_name, level, required=True, weight=1.0
        )
        summary["requires_created"] += 1

    # Preferred skills: Position -[REQUIRES {required:false}]-> Skill
    for skill_entry in extraction.get("preferred_skills", []):
        skill_name = skill_entry["name"] if isinstance(skill_entry, dict) else skill_entry
        level = skill_entry.get("level", "intermediate") if isinstance(skill_entry, dict) else "intermediate"

        await merge_skill(driver, skill_name)
        summary["skills_merged"] += 1

        query = """
        MATCH (p:Position {name: $position_name})
        MATCH (s:Skill {name: $skill_name})
        MERGE (p)-[r:REQUIRES {level: $level}]->(s)
        SET r.required = false, r.updated_at = datetime()
        RETURN r
        """
        async with driver.session() as session:
            await session.run(
                query,
                position_name=position_name,
                skill_name=skill_name,
                level=level,
            )

    logger.info(
        "Graph write complete: {} positions, {} skills, {} requires",
        summary["positions_merged"],
        summary["skills_merged"],
        summary["requires_created"],
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
    RETURN s.name AS name, s.updated_at AS updated_at
    ORDER BY s.name
    """
    skills: list[dict[str, Any]] = []

    async with driver.session() as session:
        result = await session.run(query)
        async for record in result:
            skills.append({"name": record["name"], "updated_at": str(record.get("updated_at", ""))})

    return skills
