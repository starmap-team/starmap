"""Neo4j-backed graph query helpers for API v1."""
from __future__ import annotations

from typing import Any


async def count_positions_neo4j(driver: Any) -> int:
    """Count Position nodes in Neo4j."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN count(p) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except Exception:
        return 0


async def count_skills_neo4j(driver: Any) -> int:
    """Count Skill nodes in Neo4j (source of truth)."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (s:Skill) RETURN count(s) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except Exception:
        return 0


async def count_edges_neo4j(driver: Any) -> int:
    """Count REQUIRES relationships in Neo4j."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
            result = await session.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except Exception:
        return 0


def _safe_properties(value: Any) -> dict[str, Any]:
    # ponytail: dict() works for Neo4j ≥5.x; iso_format guard for temporal types
    try:
        return {k: (v.iso_format() if hasattr(v, 'iso_format') else v) for k, v in dict(value).items()}
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
    # Default to False (bonus) when no explicit required property exists
    required = rel_props.get("required", False)
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


async def _resolve_position_name(driver: Any, position_name: str) -> str:
    """Resolve the closest Neo4j Position name."""
    async with driver.session() as session:
        exact = await session.run("MATCH (p:Position) WHERE p.name = $name RETURN p.name AS name LIMIT 1", name=position_name)
        rec = await exact.single()
        if rec and rec["name"]:
            return rec["name"]
        rows = await session.run("MATCH (p:Position) RETURN p.name AS name")
        target = position_name.strip().lower()
        async for row in rows:
            candidate = str(row["name"] or "").strip()
            if candidate.lower() == target or target in candidate.lower() or candidate.lower() in target:
                return candidate
    return position_name


async def fetch_position_graph(driver: Any, position_name: str, depth: int = 1) -> dict[str, Any]:
    """Fetch a position and its required skills as a subgraph."""
    if driver is None:
        return {"position": None, "skills": [], "edges": []}

    position_name = await _resolve_position_name(driver, position_name)
    depth = max(1, min(depth, 5))
    position = None
    skills = []
    edges = []
    skill_ids = set()

    async with driver.session() as session:
        pos_query = """
        MATCH (position:Position)
        WHERE position.name = $name
        RETURN position
        LIMIT 1
        """
        pos_result = await session.run(pos_query, name=position_name)
        pos_record = await pos_result.single()
        if pos_record and pos_record["position"] is not None:
            position = _position_item(serialize_node(pos_record["position"]))
        if position is None:
            return {"position": None, "skills": [], "edges": []}

        if depth <= 1:
            direct_query = """
            MATCH (position:Position)-[rel:REQUIRES]->(skill:Skill)
            WHERE position.name = $name
            RETURN position, rel, skill
            """
            direct_result = await session.run(direct_query, name=position_name)
            async for record in direct_result:
                if record["skill"] is not None:
                    skill_node = serialize_node(record["skill"])
                    rel = serialize_relationship(record["rel"]) if record["rel"] is not None else None
                    if skill_node["id"] not in skill_ids:
                        skill_ids.add(skill_node["id"])
                        skills.append(_skill_item(skill_node, rel))
                if record["rel"] is not None:
                    edges.append(serialize_relationship(record["rel"]))
        else:
            multi_query = (
                "MATCH (position:Position)-[rel:REQUIRES*1.." + str(depth) + "]->(skill:Skill) "
                "WHERE position.name = $name RETURN position, rel, skill"
            )
            multi_result = await session.run(multi_query, name=position_name)
            async for record in multi_result:
                if record["skill"] is not None:
                    skill_node = serialize_node(record["skill"])
                    rel_raw = record["rel"]
                    if isinstance(rel_raw, (list, tuple)) and rel_raw:
                        rel = serialize_relationship(rel_raw[-1])
                        for r in rel_raw:
                            edges.append(serialize_relationship(r))
                    elif rel_raw is not None:
                        rel = serialize_relationship(rel_raw)
                        edges.append(serialize_relationship(rel_raw))
                    else:
                        rel = None
                    if skill_node["id"] not in skill_ids:
                        skill_ids.add(skill_node["id"])
                        skills.append(_skill_item(skill_node, rel))

        if depth > 1:
            current_skill_ids = set(skill_ids)
            for _ in range(1, depth):
                if not current_skill_ids:
                    break

                prereq_query = """
                MATCH (s:Skill)-[rel:PREREQUISITE]->(prereq:Skill)
                WHERE elementId(s) IN $skill_ids
                RETURN s, rel, prereq
                """
                prereq_result = await session.run(prereq_query, skill_ids=list(current_skill_ids))
                next_skill_ids = set()
                async for record in prereq_result:
                    if record["prereq"] is not None:
                        prereq_node = serialize_node(record["prereq"])
                        rel = serialize_relationship(record["rel"]) if record["rel"] is not None else None
                        if prereq_node["id"] not in skill_ids:
                            skill_ids.add(prereq_node["id"])
                            next_skill_ids.add(prereq_node["id"])
                            skills.append(_skill_item(prereq_node, rel))
                    if record["rel"] is not None:
                        edges.append(serialize_relationship(record["rel"]))

                evolves_query = """
                MATCH (s:Skill)-[rel:EVOLVES_TO]->(evolved:Skill)
                WHERE elementId(s) IN $skill_ids
                RETURN s, rel, evolved
                """
                evolves_result = await session.run(evolves_query, skill_ids=list(current_skill_ids))
                async for record in evolves_result:
                    if record["evolved"] is not None:
                        evolved_node = serialize_node(record["evolved"])
                        rel = serialize_relationship(record["rel"]) if record["rel"] is not None else None
                        if evolved_node["id"] not in skill_ids:
                            skill_ids.add(evolved_node["id"])
                            next_skill_ids.add(evolved_node["id"])
                            skills.append(_skill_item(evolved_node, rel))
                    if record["rel"] is not None:
                        edges.append(serialize_relationship(record["rel"]))
                current_skill_ids = next_skill_ids

    return {"position": position, "skills": skills, "edges": edges}


# ── 技术栈分组映射 ──
TECH_STACK_KEYWORDS: dict[str, list[str]] = {
    "人工智能": ["AI", "人工智能", "机器学习", "深度学习", "NLP", "CV", "算法", "大模型", "LLM", "MLOps"],
    "大数据": ["大数据", "数据", "Hadoop", "Spark", "Flink", "ETL", "数据仓库", "数据分析师"],
    "智能系统": ["智能系统", "智能制造", "自动化", "机器人", "嵌入式"],
    "物联网": ["物联网", "IoT", "嵌入式", "边缘计算", "传感器"],
    "云计算/DevOps": ["云", "DevOps", "运维", "SRE", "Kubernetes", "Docker", "CI/CD", "容器"],
    "网络安全": ["安全", "网络安全", "渗透测试", "安全工程师", "密码学"],
}

TECH_STACK_COLORS = {
    "人工智能": "#9B59B6",
    "大数据": "#E6A23C",
    "智能系统": "#409EFF",
    "物联网": "#67C23A",
    "云计算/DevOps": "#36CFC9",
    "网络安全": "#F56C6C",
    "其他": "#909399",
}

LEVEL_COLORS = {
    "初级": "#67C23A",
    "中级": "#E6A23C",
    "高级": "#F56C6C",
}


def _classify_tech_stack(industry: str, name: str) -> str:
    """Classify a position into a tech stack group."""
    text = f"{industry} {name}".lower()
    for stack, keywords in TECH_STACK_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return stack
    return "其他"


def _classify_level(name: str, props: dict) -> str:
    """Classify a position into a level group."""
    level = str(props.get("level", "")).strip()
    if level in ("初级", "junior", "entry"):
        return "初级"
    if level in ("高级", "senior", "expert", "高级工程师", "资深"):
        return "高级"
    if level in ("中级", "mid", "intermediate"):
        return "中级"
    # Infer from name
    name_lower = name.lower()
    if any(kw in name_lower for kw in ("高级", "资深", "senior", "专家", "架构师", "首席")):
        return "高级"
    if any(kw in name_lower for kw in ("初级", "实习", "junior", "助理", "入门")):
        return "初级"
    return "中级"


async def fetch_overview_by_tech_stack(driver: Any) -> dict[str, Any]:
    """Overview grouped by tech stack (AI/大数据/IoT/etc)."""
    from collections import defaultdict
    groups: dict[str, dict] = {}
    for stack, color in TECH_STACK_COLORS.items():
        groups[stack] = {"positions": [], "skills": set(), "color": color}

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Position) RETURN p"
            )
            async for record in result:
                node = record["p"]
                if node is None:
                    continue
                props = _safe_properties(node)
                name = props.get("name", "")
                industry = props.get("industry", "")
                stack = _classify_tech_stack(industry, name)
                groups[stack]["positions"].append({
                    "id": _node_id(node),
                    "name": name,
                    "industry": industry,
                })

            # Count skills per group
            skill_result = await session.run(
                "MATCH (p:Position)-[:REQUIRES]->(s:Skill) "
                "RETURN p.name AS pos_name, p.industry AS pos_industry, collect(DISTINCT s.name) AS skills"
            )
            async for record in skill_result:
                pos_name = record["pos_name"] or ""
                pos_industry = record["pos_industry"] or ""
                skills = record["skills"] or []
                stack = _classify_tech_stack(pos_industry, pos_name)
                for s in skills:
                    groups[stack]["skills"].add(s)

            # Build connections between tech stacks (shared skills)
            conn_result = await session.run(
                "MATCH (p1:Position)-[:REQUIRES]->(s:Skill)<-[:REQUIRES]-(p2:Position) "
                "WHERE p1.name < p2.name "
                "RETURN p1.name AS n1, p1.industry AS i1, p2.name AS n2, p2.industry AS i2, count(s) AS shared "
                "ORDER BY shared DESC LIMIT 100"
            )
            stack_connections: dict[tuple[str, str], int] = defaultdict(int)
            async for record in conn_result:
                s1 = _classify_tech_stack(record["i1"] or "", record["n1"] or "")
                s2 = _classify_tech_stack(record["i2"] or "", record["n2"] or "")
                if s1 != s2:
                    key = tuple(sorted([s1, s2]))
                    stack_connections[key] += record["shared"] or 0
    except Exception as exc:
        from loguru import logger
        logger.error("Tech stack overview failed: {}", exc)
        return {"domains": [], "connections": [], "total_positions": 0, "total_skills": 0}

    # Build response
    # ponytail: literal IDs instead of hashlib.md5 — deterministic, readable, no import
    stack_id_prefix = {"人工智能": "ts-ai", "大数据": "ts-bigdata", "智能系统": "ts-sys",
                       "物联网": "ts-iot", "云计算/DevOps": "ts-cloud", "网络安全": "ts-sec", "其他": "ts-other"}
    domains = []
    total_pos = 0
    total_skill = 0
    for stack, data in groups.items():
        if not data["positions"] and not data["skills"]:
            continue
        pc = len(data["positions"])
        sc = len(data["skills"])
        total_pos += pc
        total_skill += sc
        domains.append({
            "id": stack_id_prefix.get(stack, f"ts-{stack}"),
            "name": stack,
            "position_count": pc,
            "skill_count": sc,
            "color": data["color"],
        })

    connections = []
    for (s1, s2), weight in stack_connections.items():
        connections.append({
            "source_id": stack_id_prefix.get(s1, f"ts-{s1}"),
            "target_id": stack_id_prefix.get(s2, f"ts-{s2}"),
            "type": "SHARES_SKILLS",
            "properties": {"weight": min(1.0, weight / 20.0)},
        })

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
    }


async def fetch_overview_by_level(driver: Any) -> dict[str, Any]:
    """Overview grouped by level (初级/中级/高级)."""
    groups: dict[str, dict] = {}
    for level, color in LEVEL_COLORS.items():
        groups[level] = {"positions": [], "skills": set(), "color": color}

    try:
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN p")
            async for record in result:
                node = record["p"]
                if node is None:
                    continue
                props = _safe_properties(node)
                name = props.get("name", "")
                level = _classify_level(name, props)
                groups[level]["positions"].append({
                    "id": _node_id(node),
                    "name": name,
                    "level": level,
                })

            # Count skills per level
            skill_result = await session.run(
                "MATCH (p:Position)-[:REQUIRES]->(s:Skill) "
                "RETURN p.name AS pos_name, p.level AS pos_level, collect(DISTINCT s.name) AS skills"
            )
            async for record in skill_result:
                pos_name = record["pos_name"] or ""
                pos_level = record.get("pos_level") or ""
                skills = record["skills"] or []
                level = _classify_level(pos_name, {"level": pos_level})
                for s in skills:
                    groups[level]["skills"].add(s)

            # Build evolution connections between levels
            level_connections = [
                {"source": "初级", "target": "中级", "weight": 0.8},
                {"source": "中级", "target": "高级", "weight": 0.8},
            ]
    except Exception as exc:
        from loguru import logger
        logger.error("Level overview failed: {}", exc)
        return {"domains": [], "connections": [], "total_positions": 0, "total_skills": 0}

    # ponytail: literal IDs instead of hashlib.md5
    level_id = {"初级": "lv-junior", "中级": "lv-mid", "高级": "lv-senior"}
    domains = []
    total_pos = 0
    total_skill = 0
    for level, data in groups.items():
        if not data["positions"] and not data["skills"]:
            continue
        pc = len(data["positions"])
        sc = len(data["skills"])
        total_pos += pc
        total_skill += sc
        domains.append({
            "id": level_id.get(level, f"lv-{level}"),
            "name": level,
            "position_count": pc,
            "skill_count": sc,
            "color": data["color"],
        })

    connections = []
    for conn in level_connections:
        connections.append({
            "source_id": level_id.get(conn["source"], f"lv-{conn['source']}"),
            "target_id": level_id.get(conn["target"], f"lv-{conn['target']}"),
            "type": "EVOLVES_TO",
            "properties": {"weight": conn["weight"]},
        })

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
    }
