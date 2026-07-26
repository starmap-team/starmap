"""Tech-stack & level overview helpers for graph service — extracted from graph_service.py (m7).

业务说明：
    按技术栈（AI/大数据/IoT/...）和职级（初级/中级/高级）两个维度聚合统计职位与技能，
    并构建跨维度关联（共享技能 / 晋升路径），为前端技术栈与成长路径视图提供数据。
    graph_service.py 重新导出本模块的公共符号以保持向后兼容。
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from loguru import logger
from neo4j.exceptions import Neo4jError

from app.exceptions import DashboardError, StarMapError
from app.services.graph_serializers import _node_id, _safe_properties

if TYPE_CHECKING:
    from neo4j import AsyncDriver


# ── 常量 ──

# 业务说明：定义技术栈关键词映射表（中英双语），用于将职位名称/行业自动分类到对应的技术领域。
# 技术说明：每个技术栈对应一组关键词，匹配时采用大小写不敏感的子串匹配。
# P1 fix: 加入英文关键词以支持英文职位名称的分类。
TECH_STACK_KEYWORDS: dict[str, list[str]] = {
    "人工智能": [
        "AI", "人工智能", "机器学习", "深度学习", "NLP", "CV", "算法", "大模型", "LLM", "MLOps",
        "Machine Learning", "Deep Learning", "Computer Vision", "ML Engineer", "Data Scien",
        "Prompt", "RAG", "Fine-tuning", "LangChain", "Transformer",
    ],
    "大数据": [
        "大数据", "数据", "Hadoop", "Spark", "Flink", "ETL", "数据仓库", "数据分析师",
        "Data Engineer", "Data Analyst", "Analytics", "BI", "Big Data", "Kafka",
    ],
    "前端开发": [
        "前端", "Web前端", "Frontend", "Front-end", "React", "Vue", "Angular",
        "UI", "UX", "JavaScript", "TypeScript",
    ],
    "后端开发": [
        "后端", "Backend", "Back-end", "API", "Microservice", "GraphQL",
        "Java Dev", "Go Dev", "Python Dev", "Rust Dev", ".NET Dev",
        "Node.js", "PHP", "Ruby",
    ],
    "智能系统": ["智能系统", "智能制造", "自动化", "机器人", "嵌入式"],
    "物联网": ["物联网", "IoT", "嵌入式", "边缘计算", "传感器", "Embedded", "Firmware"],
    "云计算/DevOps": [
        "云", "DevOps", "运维", "SRE", "Kubernetes", "Docker", "CI/CD", "容器",
        "Cloud", "Platform Engineer", "Infrastructure", "Terraform",
    ],
    "网络安全": [
        "安全", "网络安全", "渗透测试", "安全工程师", "密码学",
        "Security", "DevSecOps", "Penetration", "IAM",
    ],
    "移动开发": [
        "移动", "Android", "iOS", "Flutter", "React Native", "Mobile",
        "App Dev", "Swift",
    ],
    "测试": [
        "测试", "QA", "Test", "SDET", "Quality", "Automation",
    ],
    "区块链/Web3": [
        "区块链", "Blockchain", "Web3", "Solidity", "Smart Contract",
    ],
    "游戏开发": [
        "游戏", "Game Dev", "Unity", "Unreal", "Game Developer",
    ],
}

# 业务说明：为每个技术栈分配固定的展示颜色，用于前端图可视化中的分类着色。
TECH_STACK_COLORS = {
    "人工智能": "#9B59B6",
    "大数据": "#E6A23C",
    "前端开发": "#409EFF",
    "后端开发": "#67C23A",
    "智能系统": "#409EFF",
    "物联网": "#67C23A",
    "云计算/DevOps": "#36CFC9",
    "网络安全": "#F56C6C",
    "移动开发": "#67C23A",
    "测试": "#909399",
    "区块链/Web3": "#909399",
    "游戏开发": "#9B59B6",
    "其他": "#909399",
}

LEVEL_COLORS = {
    "初级": "#67C23A",
    "中级": "#E6A23C",
    "高级": "#F56C6C",
}

# 共享技能权重归一化分母：当两个技术栈共享技能数超过此值时，权重封顶为 1.0
_SHARED_SKILL_WEIGHT_DENOMINATOR = 20.0

# 职级晋升路径默认权重（初始值，未来可由实际晋升数据驱动替换）
_DEFAULT_EVOLUTION_WEIGHT = 0.8


# ── 分类函数 ──


def _classify_tech_stack(industry: str, name: str) -> str:
    """Classify a position into a tech stack group."""
    text = f"{industry} {name}".lower()
    for stack, keywords in TECH_STACK_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return stack
    return "其他"


def _classify_level(name: str, props: dict[str, Any]) -> str:
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


# ── 内部辅助函数 ──


async def _fetch_independent_counts(driver: AsyncDriver) -> dict[str, int]:
    """Fetch independent node/edge counts from Neo4j in a single query.

    Returns a dict with keys: positions, skills, edges.
    """
    try:
        async with driver.session() as session:
            # 3 separate count queries to avoid Cartesian product
            # (MATCH (p), (s) OPTIONAL MATCH ()-[r]->() produces |p|*|s|*|r| rows)
            result = await session.run(
                "MATCH (p:Position) WITH count(p) AS pos_cnt "
                "MATCH (s:Skill) WITH pos_cnt, count(s) AS skill_cnt "
                "MATCH ()-[r:REQUIRES]->() "
                "RETURN pos_cnt, skill_cnt, count(r) AS edge_cnt"
            )
            record = await result.single()
            if record:
                return {
                    "positions": record["pos_cnt"],
                    "skills": record["skill_cnt"],
                    "edges": record["edge_cnt"],
                }
    except StarMapError:
        raise
    except Neo4jError as exc:
        logger.warning("Failed to fetch independent counts from Neo4j: {}", exc)
        raise DashboardError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error fetching independent counts: {}", exc)
        raise DashboardError(str(exc)) from exc
    return {"positions": 0, "skills": 0, "edges": 0}


# ── 公开 API ──


async def fetch_overview_by_tech_stack(driver: AsyncDriver) -> dict[str, Any]:
    """Overview grouped by tech stack (AI/大数据/IoT/etc)."""
    groups: dict[str, dict] = {}
    for stack, color in TECH_STACK_COLORS.items():
        groups[stack] = {"positions": [], "skills": set(), "color": color}

    try:
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN p")
            async for record in result:
                node = record["p"]
                if node is None:
                    continue
                props = _safe_properties(node)
                name = props.get("name", "")
                industry = props.get("industry", "")
                stack = _classify_tech_stack(industry, name)
                groups[stack]["positions"].append(
                    {
                        "id": _node_id(node),
                        "name": name,
                        "industry": industry,
                    }
                )

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
    except StarMapError:
        raise
    except Neo4jError as exc:
        logger.error("Tech stack overview Neo4j error: {}", exc)
        raise DashboardError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Tech stack overview failed: {}", exc)
        raise DashboardError(str(exc)) from exc

    # Build response
    stack_id_prefix = {
        "人工智能": "ts-ai",
        "大数据": "ts-bigdata",
        "前端开发": "ts-frontend",
        "后端开发": "ts-backend",
        "智能系统": "ts-sys",
        "物联网": "ts-iot",
        "云计算/DevOps": "ts-cloud",
        "网络安全": "ts-sec",
        "移动开发": "ts-mobile",
        "测试": "ts-qa",
        "区块链/Web3": "ts-blockchain",
        "游戏开发": "ts-game",
        "其他": "ts-other",
    }
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
        domains.append(
            {
                "id": stack_id_prefix.get(stack, f"ts-{stack}"),
                "name": stack,
                "position_count": pc,
                "skill_count": sc,
                "color": data["color"],
            }
        )

    connections = []
    for (s1, s2), weight in stack_connections.items():
        connections.append(
            {
                "source_id": stack_id_prefix.get(s1, f"ts-{s1}"),
                "target_id": stack_id_prefix.get(s2, f"ts-{s2}"),
                "type": "SHARES_SKILLS",
                "properties": {"weight": min(1.0, weight / _SHARED_SKILL_WEIGHT_DENOMINATOR)},
            }
        )

    # Fetch independent counts (P1 fix: single query + logging)
    counts = await _fetch_independent_counts(driver)

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
        "independent_positions": counts["positions"],
        "independent_skills": counts["skills"],
        "independent_edges": counts["edges"],
    }


async def fetch_overview_by_level(driver: AsyncDriver) -> dict[str, Any]:
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
                groups[level]["positions"].append(
                    {
                        "id": _node_id(node),
                        "name": name,
                        "level": level,
                    }
                )

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
                {"source": "初级", "target": "中级", "weight": _DEFAULT_EVOLUTION_WEIGHT},
                {"source": "中级", "target": "高级", "weight": _DEFAULT_EVOLUTION_WEIGHT},
            ]
    except StarMapError:
        raise
    except Neo4jError as exc:
        logger.error("Level overview Neo4j error: {}", exc)
        raise DashboardError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Level overview failed: {}", exc)
        raise DashboardError(str(exc)) from exc

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
        domains.append(
            {
                "id": level_id.get(level, f"lv-{level}"),
                "name": level,
                "position_count": pc,
                "skill_count": sc,
                "color": data["color"],
            }
        )

    connections = []
    for conn in level_connections:
        source = str(conn.get("source", ""))
        target = str(conn.get("target", ""))
        connections.append(
            {
                "source_id": level_id.get(source, f"lv-{source}"),
                "target_id": level_id.get(target, f"lv-{target}"),
                "type": "EVOLVES_TO",
                "properties": {"weight": conn["weight"]},
            }
        )

    # Fetch independent counts (P1 fix: single query + logging)
    counts = await _fetch_independent_counts(driver)

    return {
        "domains": domains,
        "connections": connections,
        "total_positions": total_pos,
        "total_skills": total_skill,
        "independent_positions": counts["positions"],
        "independent_skills": counts["skills"],
        "independent_edges": counts["edges"],
    }
