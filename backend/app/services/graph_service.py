"""Neo4j-backed graph query helpers for API v1.

业务说明：
    本模块封装了所有与 Neo4j 图数据库交互的查询、序列化、统计及同步逻辑，
    是 StarMap 后端服务中图谱数据层的核心组件。职责包括：
    1. 提供职位（Position）与技能（Skill）节点的统计查询；
    2. 将 Neo4j 原生节点/关系对象序列化为前端图可视化所需的统一数据结构；
    3. 按技术栈（Tech Stack）和职级（Level）聚合生成数据概览；
    4. 支持从 Pipeline 提取结果向 Neo4j 进行幂等同步（MERGE），
       兼容 Inline 直接写入与 DB-Query 批量写入两种模式。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.extraction.normalize import normalize_proficiency


async def count_positions_neo4j(driver: Any) -> int:
    # 业务说明：统计 Neo4j 图谱中职位（Position）节点的总数量，用于仪表盘或健康检查。
    # 技术说明：当 driver 未初始化或查询异常时返回 0，保证服务降级不中断。
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
    # 业务说明：统计 Neo4j 图谱中技能（Skill）节点的总数量，作为技能库规模的权威来源。
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
    # 业务说明：统计职位与技能之间 REQUIRES 关系的总数量，反映图谱连接密度。
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
    # 技术说明：Neo4j 节点/关系的属性字典化辅助函数，兼容 Neo4j ≥5.x 的 temporal 类型（如 DateTime），
    # 通过 iso_format() 将时间对象转为字符串，避免 JSON 序列化异常。
    # ponytail: dict() works for Neo4j ≥5.x; iso_format guard for temporal types
    try:
        return {k: (v.iso_format() if hasattr(v, 'iso_format') else v) for k, v in dict(value).items()}
    except Exception:
        return {}


def _node_id(node: Any) -> str:
    # 技术说明：从 Neo4j 节点中提取唯一标识符的降级策略：
    # 优先 element_id（Neo4j ≥5.x），其次 id（旧版），最后从属性中回退 name。
    element_id = getattr(node, "element_id", None)
    if element_id is not None:
        return str(element_id)
    node_id = getattr(node, "id", None)
    if node_id is not None:
        return str(node_id)
    props = _safe_properties(node)
    return str(props.get("id") or props.get("name") or "")


def _relationship_type(rel: Any) -> str:
    # 技术说明：从 Neo4j 关系对象中提取关系类型名称，兼容不同驱动版本。
    rel_type = getattr(rel, "type", None)
    if rel_type is not None:
        return str(rel_type)
    return rel.__class__.__name__


def _relationship_endpoint(rel: Any, attr: str) -> str:
    # 技术说明：获取关系的起点或终点节点 ID，支持 start_node / end_node 两种属性名。
    node = getattr(rel, attr, None)
    if node is not None:
        return _node_id(node)
    value = getattr(rel, f"{attr}_node_id", None)
    return "" if value is None else str(value)


def serialize_node(node: Any) -> dict[str, Any]:
    # 业务说明：将 Neo4j 节点对象转换为前端图可视化组件（如 D3 / ECharts）所需的统一节点数据结构。
    # 技术说明：提取 labels、category、name 等字段，确保前端渲染时节点样式和分组正确。
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
    # 业务说明：将 Neo4j 关系对象转换为前端图可视化组件所需的统一边（edge/relationship）数据结构。
    # 技术说明：包含 source_id、target_id、type 及属性（如 weight），用于前端连线渲染和交互。
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
    # 业务说明：对图谱节点和边进行去重，保留首次出现的元素，避免前端渲染时出现重叠或重复数据。
    # 技术说明：节点以 id 为键去重，边以 (source_id, target_id, type) 三元组为键去重。
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


# ── 技术栈分组映射 ──
# 业务说明：定义技术栈关键词映射表，用于将职位名称/行业自动分类到对应的技术领域（如人工智能、大数据等）。
# 技术说明：每个技术栈对应一组关键词，匹配时采用大小写不敏感的子串匹配。
TECH_STACK_KEYWORDS: dict[str, list[str]] = {
    "人工智能": ["AI", "人工智能", "机器学习", "深度学习", "NLP", "CV", "算法", "大模型", "LLM", "MLOps"],
    "大数据": ["大数据", "数据", "Hadoop", "Spark", "Flink", "ETL", "数据仓库", "数据分析师"],
    "智能系统": ["智能系统", "智能制造", "自动化", "机器人", "嵌入式"],
    "物联网": ["物联网", "IoT", "嵌入式", "边缘计算", "传感器"],
    "云计算/DevOps": ["云", "DevOps", "运维", "SRE", "Kubernetes", "Docker", "CI/CD", "容器"],
    "网络安全": ["安全", "网络安全", "渗透测试", "安全工程师", "密码学"],
}

# 业务说明：为每个技术栈分配固定的展示颜色，用于前端图可视化中的分类着色。
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
    # 业务说明：根据职位所属行业和职位名称，自动判定其所属技术栈分类。
    # 技术说明：将行业与职位名称拼接后进行关键词子串匹配，未命中时归入 "其他"。
    """Classify a position into a tech stack group."""
    text = f"{industry} {name}".lower()
    for stack, keywords in TECH_STACK_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return stack
    return "其他"


def _classify_level(name: str, props: dict) -> str:
    # 业务说明：根据职位属性或名称中的关键词，将职位划分为初级、中级、高级三档。
    # 技术说明：优先读取 props 中的 level 字段，若不存在则从职位名称中推断。
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
    # 业务说明：按技术栈维度聚合统计职位与技能分布，并计算不同技术栈之间基于共享技能的关联强度，
    # 为前端技术栈概览视图提供数据支撑。
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
    # 业务说明：按职级（初级/中级/高级）维度聚合统计职位与技能分布，并构建职级间的晋升路径关系，
    # 为前端技能成长路径视图提供数据支撑。
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
        source = str(conn.get("source", ""))
        target = str(conn.get("target", ""))
        connections.append({
            "source_id": level_id.get(source, f"lv-{source}"),
            "target_id": level_id.get(target, f"lv-{target}"),
            "type": "EVOLVES_TO",
            "properties": {"weight": conn["weight"]},
        })

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
    }


# Phase 2 SYNC-02: sync_from_pipeline
async def sync_from_pipeline(
    run_id: str,
    new_skills: list[dict[str, Any]] | None = None,
    new_edges: list[dict[str, Any]] | None = None,
    new_positions: list[dict[str, Any]] | None = None,
    extraction_data: dict[str, Any] | None = None,
    target_position: str = "",
) -> dict[str, Any]:
    # 业务说明：将 Pipeline（如 JD 解析流水线）提取出的职位、技能及关系数据同步写入 Neo4j 图谱，
    # 采用 MERGE 语义保证幂等性，支持两种写入模式：
    #   1. Inline 模式（遗留）：直接传入 new_skills / new_edges / new_positions 进行逐条 MERGE；
    #   2. DB-Query 模式（推荐）：传入 extraction_data，函数会查询 PostgreSQL 中的 JDExtractionRecord，
    #      并通过 graph_writer.batch_write_extractions 使用完整的本体（7 节点类型、8 关系类型）批量写入。
    """将 pipeline 提取结果写入 Neo4j 图谱（MERGE 幂等）。

    Supports two modes:
      1. **Inline mode** (legacy): pass new_skills / new_edges / new_positions directly.
      2. **DB-query mode** (preferred): pass extraction_data from Step 2, and optionally
         query JDExtractionRecord from PostgreSQL for richer ontology triples via
         graph_writer.batch_write_extractions.

    When extraction_data is provided, the function queries completed JDExtractionRecords
    created within the pipeline run timeframe and writes them using the full ontology
    (7 node types, 8 relationship types) with retry logic.
    """
    from app.services.resources import resources as app_resources

    driver = app_resources.neo4j_driver
    if driver is None:
        return {"synced": False, "error": "neo4j_driver_unavailable", "count": 0}

    # ── DB-query mode: use graph_writer.batch_write_extractions ──
    if extraction_data is not None:
        return await _sync_via_graph_writer(run_id, driver, app_resources, extraction_data, target_position=target_position)

    # ── Inline mode (legacy): direct MERGE of skills / edges / positions ──
    total_nodes = 0
    total_edges = 0
    errors: list[str] = []

    try:
        async with driver.session() as session:
            for pos in (new_positions or []):
                try:
                    await session.run(
                        "MERGE (p:Position {name: $name}) SET p.industry = $industry, p.updated_at = datetime()",
                        name=pos.get("name", ""), industry=pos.get("industry", ""),
                    )
                    total_nodes += 1
                except Exception as exc:
                    errors.append(f"position '{pos.get('name')}': {exc}")

            for skill in (new_skills or []):
                try:
                    await session.run(
                        "MERGE (s:Skill {name: $name}) SET s.category = $category, s.source_count = coalesce(s.source_count, 0) + 1",
                        name=skill.get("name", ""), category=skill.get("category", "hard_skill"),
                    )
                    total_nodes += 1
                except Exception as exc:
                    errors.append(f"skill '{skill.get('name')}': {exc}")

            for edge in (new_edges or []):
                try:
                    await session.run(
                        "MATCH (p:Position {name: $pos_name}) MATCH (s:Skill {name: $skill_name}) "
                        "MERGE (p)-[r:REQUIRES]->(s) SET r.level = $level, r.required = $required",
                        pos_name=edge.get("position_name", ""), skill_name=edge.get("skill_name", ""),
                        level=edge.get("level", "熟悉"), required=edge.get("required", True),
                    )
                    total_edges += 1
                except Exception as exc:
                    errors.append(f"edge: {exc}")

        logger.info("sync_from_pipeline (inline): {} nodes, {} edges (run_id={})", total_nodes, total_edges, run_id)
        return {"synced": len(errors) == 0, "count": total_nodes + total_edges, "nodes": total_nodes, "edges": total_edges, "errors": errors}
    except Exception as exc:
        logger.error("sync_from_pipeline failed: {}", exc)
        return {"synced": False, "error": str(exc), "count": total_nodes + total_edges}


async def _sync_via_graph_writer(
    run_id: str,
    driver: Any,
    app_resources: Any,
    extraction_data: dict[str, Any],
    target_position: str = "",
) -> dict[str, Any]:
    # 业务说明：DB-Query 模式的核心实现，通过 graph_writer 批量将提取结果写入 Neo4j。
    # 技术说明：
    #   1. 先从当前 pipeline 的 extraction_data 构建提取字典；
    #   2. 再查询近 5 分钟内的 JDExtractionRecord 补充更多数据；
    #   3. 最后调用 batch_write_extractions 使用完整本体（7 节点 + 8 关系）批量写入，
    #      内置 MERGE + 重试机制，避免重复写入。
    """Query JDExtractionRecord from PostgreSQL and write to Neo4j via graph_writer.

    Strategy:
      1. Build an extraction dict from the Step 2 extraction_data for immediate write.
      2. Query JDExtractionRecords created during the pipeline run timeframe
         (last 5 minutes) for additional records that may have been persisted
         by the batch pipeline executor.
      3. Write all collected extractions via graph_writer.batch_write_extractions
         which uses the full 7-node / 8-relationship ontology with MERGE + retry.
    """
    from datetime import UTC, datetime, timedelta

    from app.core.extraction.graph_writer import batch_write_extractions
    from app.models.extraction_models import JDExtractionRecord

    extractions: list[dict[str, Any]] = []
    nodes_written = 0
    edges_written = 0

    try:
        # ── 1. Build extraction from the current pipeline run's Step 2 data ──
        position_name = extraction_data.get("position_name", "")
        skills = extraction_data.get("skills", [])

        if position_name:
            required_skills = []
            preferred_skills = []
            for s in skills:
                entry = {
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "level": s.get("proficiency", "熟悉"),
                }
                if s.get("importance") == "required":
                    required_skills.append(entry)
                else:
                    preferred_skills.append(entry)

            current_extraction: dict[str, Any] = {
                "position_name": position_name,
                "industry": extraction_data.get("industry", ""),
                "description": extraction_data.get("description", ""),
                "experience_required": extraction_data.get("experience_required"),
                "education_required": extraction_data.get("education_required"),
                "knowledge_areas": extraction_data.get("knowledge_areas", []),
                "required_skills": required_skills,
                "preferred_skills": preferred_skills,
                "tools": extraction_data.get("tools", []),
                "prerequisites": extraction_data.get("prerequisites", []),
                "learning_resources": extraction_data.get("learning_resources", []),
                "evolves_to": extraction_data.get("evolves_to", []),
            }
            extractions.append(current_extraction)

        # If target_position differs from position_name, also create a Position node
        # with the target_position name so Step 4 match diagnosis can find it.
        if target_position and target_position != position_name and skills:
            required_skills_alt = []
            preferred_skills_alt = []
            for s in skills:
                entry = {
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "level": s.get("proficiency", "熟悉"),
                }
                if s.get("importance") == "required":
                    required_skills_alt.append(entry)
                else:
                    preferred_skills_alt.append(entry)
            target_extraction: dict[str, Any] = {
                "position_name": target_position,
                "industry": extraction_data.get("industry", ""),
                "description": extraction_data.get("description", ""),
                "experience_required": extraction_data.get("experience_required"),
                "education_required": extraction_data.get("education_required"),
                "knowledge_areas": extraction_data.get("knowledge_areas", []),
                "required_skills": required_skills_alt,
                "preferred_skills": preferred_skills_alt,
                "tools": extraction_data.get("tools", []),
                "prerequisites": extraction_data.get("prerequisites", []),
                "learning_resources": extraction_data.get("learning_resources", []),
                "evolves_to": extraction_data.get("evolves_to", []),
            }
            extractions.append(target_extraction)

        # ── 2. Query JDExtractionRecords from PostgreSQL ──
        pg_sessionmaker = app_resources.pg_sessionmaker
        if pg_sessionmaker is not None:
            try:
                import sqlalchemy as sa

                # Look for records created within the pipeline run timeframe
                since = datetime.now(UTC) - timedelta(minutes=5)
                async with pg_sessionmaker() as session:
                    rows = (
                        await session.execute(
                            sa.select(JDExtractionRecord)
                            .where(
                                JDExtractionRecord.status == "completed",
                                JDExtractionRecord.created_at >= since,
                            )
                            .order_by(JDExtractionRecord.created_at.desc())
                            .limit(200)
                        )
                    ).scalars().all()

                for record in rows:
                    payload = record.to_extraction_payload()
                    # Avoid duplicating the current run's extraction
                    if position_name and payload.get("position_name") == position_name:
                        # Check if skills overlap significantly — skip if same extraction
                        existing_names = {s.get("name") for s in current_extraction.get("required_skills", []) if s.get("name")}
                        existing_names |= {s.get("name") for s in current_extraction.get("preferred_skills", []) if s.get("name")}
                        payload_names = set()
                        for entries in (payload.get("required_skills", []), payload.get("preferred_skills", [])):
                            for entry in entries or []:
                                name = entry.get("name") if isinstance(entry, dict) else str(entry)
                                if name:
                                    payload_names.add(name)
                        if existing_names and payload_names and existing_names == payload_names:
                            continue
                    extractions.append(payload)

                logger.info(
                    "sync_from_pipeline: found {} DB records for run_id={}",
                    len(rows), run_id,
                )
            except Exception as exc:
                logger.warning(
                    "sync_from_pipeline: DB query failed (non-fatal, using inline data): {}", exc,
                )
        else:
            logger.debug("sync_from_pipeline: pg_sessionmaker not available, using inline data only")

        # ── 3. Write all extractions to Neo4j via graph_writer ──
        if not extractions:
            return {"synced": True, "nodes_written": 0, "edges_written": 0, "extractions_processed": 0}

        summaries = await batch_write_extractions(extractions, driver)

        # Aggregate counts from all summaries
        for summary in summaries:
            nodes_written += int(summary.get("nodes_touched", 0))
            edges_written += int(summary.get("relationships_touched", 0))

        logger.info(
            "sync_from_pipeline (graph_writer): {} extractions, {} nodes, {} edges (run_id={})",
            len(extractions), nodes_written, edges_written, run_id,
        )
        return {
            "synced": True,
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "extractions_processed": len(extractions),
        }
    except Exception as exc:
        logger.error("sync_from_pipeline (graph_writer) failed: {}", exc)
        return {"synced": False, "error": str(exc), "nodes_written": nodes_written, "edges_written": edges_written}



