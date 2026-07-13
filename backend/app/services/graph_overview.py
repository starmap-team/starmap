"""Tech-stack & level overview helpers for graph service — extracted from graph_service.py (m7).

业务说明：
    按技术栈（AI/大数据/IoT/...）和职级（初级/中级/高级）两个维度聚合统计职位与技能，
    并构建跨维度关联（共享技能 / 晋升路径），为前端技术栈与成长路径视图提供数据。
    graph_service.py 重新导出本模块的公共符号以保持向后兼容。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from loguru import logger

from app.services.graph_serializers import _node_id, _safe_properties

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

    # Query actual Neo4j independent counts (same across all group_by modes)
    # Initialize fallbacks before try block to prevent UnboundLocalError when async for yields 0 records
    independent_pos = total_pos
    independent_skill = total_skill
    independent_edge = len(connections)
    try:
        async with driver.session() as session:
            pos_rec = await session.run("MATCH (p:Position) RETURN count(p) AS cnt")
            async for r in pos_rec:
                independent_pos = r["cnt"]
            skill_rec = await session.run("MATCH (s:Skill) RETURN count(s) AS cnt")
            async for r in skill_rec:
                independent_skill = r["cnt"]
            edge_rec = await session.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS cnt")
            async for r in edge_rec:
                independent_edge = r["cnt"]
    except Exception:
        pass  # fallback values already set above

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
        "independent_positions": independent_pos,
        "independent_skills": independent_skill,
        "independent_edges": independent_edge,
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

    # Query actual Neo4j independent counts (same across all group_by modes)
    # Initialize fallbacks before try block to prevent UnboundLocalError when async for yields 0 records
    independent_pos = total_pos
    independent_skill = total_skill
    independent_edge = len(connections)
    try:
        async with driver.session() as session:
            pos_rec = await session.run("MATCH (p:Position) RETURN count(p) AS cnt")
            async for r in pos_rec:
                independent_pos = r["cnt"]
            skill_rec = await session.run("MATCH (s:Skill) RETURN count(s) AS cnt")
            async for r in skill_rec:
                independent_skill = r["cnt"]
            edge_rec = await session.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS cnt")
            async for r in edge_rec:
                independent_edge = r["cnt"]
    except Exception:
        pass  # fallback values already set above

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
        "independent_positions": independent_pos,
        "independent_skills": independent_skill,
        "independent_edges": independent_edge,
    }
