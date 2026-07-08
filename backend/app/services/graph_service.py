"""Neo4j-backed graph query helpers for API v1.

业务说明：
    本模块封装了与 Neo4j 图数据库交互的查询逻辑（fetch_position_graph、overview）。
    序列化与计数逻辑已拆分至 graph_serializers.py（m7）。
    同步逻辑（sync_from_pipeline）已拆分至 graph_sync.py（m7）。
    本模块 re-export graph_serializers 的公共符号以保持向后兼容。
"""
from __future__ import annotations

from typing import Any

from app.core.extraction.normalize import normalize_proficiency
from app.services.graph_overview import (  # noqa: F401  (re-export)
    LEVEL_COLORS,
    TECH_STACK_COLORS,
    TECH_STACK_KEYWORDS,
    _classify_level,
    _classify_tech_stack,
    fetch_overview_by_level,
    fetch_overview_by_tech_stack,
)
from app.services.graph_serializers import (  # noqa: F401  (re-export)
    _node_id,
    _relationship_endpoint,
    _relationship_type,
    _safe_properties,
    count_edges_neo4j,
    count_positions_neo4j,
    count_skills_neo4j,
    dedupe_graph,
    serialize_node,
    serialize_relationship,
)

# ── count/serializer 详见 graph_serializers.py ──
# ── overview 详见 graph_overview.py ──


def _position_item(node: dict[str, Any]) -> dict[str, Any]:
    # 业务说明：将图谱中的 Position 节点转换为 API 响应中职位列表的标准数据结构。
    # 技术说明：从 node.properties 中提取职位 ID、名称、行业、描述及所需技能列表。
    props = dict(node.get("properties") or {})
    return {
        "position_id": str(props.get("position_id") or node.get("id") or props.get("name") or ""),
        "name": props.get("name") or node.get("id") or "",
        "industry": props.get("industry") or "",
        "description": props.get("description") or "",
        "skills_required": props.get("skills_required") or [],
    }


def _skill_item(node: dict[str, Any], rel: dict[str, Any] | None = None) -> dict[str, Any]:
    # 业务说明：将图谱中的 Skill 节点（及可选的关联关系）转换为 API 响应中技能列表的标准数据结构。
    # 技术说明：结合节点属性与关系属性（如 level、required）生成 proficiency、importance 等字段。
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
        "proficiency": props.get("proficiency") or normalize_proficiency(level),
        "confidence": float(props.get("confidence") or rel_props.get("confidence") or 1.0),
        "source_count": int(props.get("source_count") or 0),
        "trend": props.get("trend") or "stable",
        "importance": "required" if required is not False else "bonus",
    }


async def _resolve_position_name(driver: Any, position_name: str) -> str:
    # 业务说明：根据用户输入的职位名称，在 Neo4j 中模糊匹配最接近的正式职位名称，
    # 支持精确匹配、子串匹配和双向包含匹配，提升搜索容错率。
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
    # 业务说明：以指定职位为中心，按深度（depth）向外抓取子图，包含职位节点、关联技能节点及边关系。
    # 技术说明：
    #   - depth=1 时仅抓取直接 REQUIRES 关系；
    #   - depth>1 时支持可变长度路径（REQUIRES*1..depth），并递归抓取 PREREQUISITE 和 EVOLVES_TO 关系；
    #   - depth 被限制在 [1, 5] 范围内，防止查询爆炸。
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
from app.services.graph_sync import sync_from_pipeline  # noqa: E402,F401
