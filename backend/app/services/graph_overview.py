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

from app.core.constants import LEVEL_JUNIOR, LEVEL_MID, LEVEL_SENIOR
from app.exceptions import DashboardError, StarMapError
from app.services.graph_serializers import _node_id, _safe_properties


def _prune_connections(connections: list[dict[str, Any]], domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop connections whose source or target node is not in the retained
    ``domains`` set.

    Background: a dimension group with zero members is filtered out of the
    ``domains`` list, but the group's incident edges (e.g. ``EVOLVES_TO``)
    can still appear in the ``connections`` payload. Forwarding those
    dangling edges to the 3d-force-graph renderer raises "node not found"
    and leaves the view in a corrupted state across dimension switches.
    """
    valid = {d.get("id") for d in domains if d.get("id") is not None}
    return [
        c for c in connections
        if c.get("source_id") in valid and c.get("target_id") in valid
    ]

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
    LEVEL_JUNIOR: "#67C23A",
    LEVEL_MID: "#E6A23C",
    LEVEL_SENIOR: "#F56C6C",
}

# 共享技能权重归一化分母：当两个技术栈共享技能数超过此值时，权重封顶为 1.0
_SHARED_SKILL_WEIGHT_DENOMINATOR = 20.0

# 职级晋升路径默认权重（初始值，未来可由实际晋升数据驱动替换）
_DEFAULT_EVOLUTION_WEIGHT = 0.8


# Step 2: heat 视图（按技能需求频率着色）
HEAT_COLOR_RAMP = [
    (0,  "#e0f2fe"),
    (1,  "#7dd3fc"),
    (2,  "#38bdf8"),
    (3,  "#f97316"),
    (4,  "#ef4444"),
]
HEAT_ID_PREFIX = "heat-skill-"


def _heat_color(count: int) -> str:
    """Map skill demand count → heat color."""
    if count <= 0:
        return HEAT_COLOR_RAMP[0][1]
    if count >= HEAT_COLOR_RAMP[-1][0]:
        return HEAT_COLOR_RAMP[-1][1]
    for i, (threshold, color) in enumerate(HEAT_COLOR_RAMP):
        next_threshold = HEAT_COLOR_RAMP[i + 1][0] if i + 1 < len(HEAT_COLOR_RAMP) else threshold
        if threshold <= count < next_threshold:
            return color
    return HEAT_COLOR_RAMP[-1][1]


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
        return LEVEL_JUNIOR
    if level in ("高级", "senior", "expert", "高级工程师", "资深"):
        return LEVEL_SENIOR
    if level in ("中级", "mid", "intermediate"):
        return LEVEL_MID
 # Infer from name
    name_lower = name.lower()
    if any(kw in name_lower for kw in ("高级", "资深", "senior", "专家", "架构师", "首席")):
        return LEVEL_SENIOR
    if any(kw in name_lower for kw in ("初级", "实习", "junior", "助理", "入门")):
        return LEVEL_JUNIOR
    return LEVEL_MID


# Step 1: 行业归一（13 大行业，对标 spec 5.3）
INDUSTRY_ID_PREFIX: dict[str, str] = {
    "人工智能": "ind-ai", "大数据": "ind-data", "数据科学": "ind-ds",
    "数据工程": "ind-de", "AI/机器学习": "ind-ml", "前端开发": "ind-fe",
    "后端开发": "ind-be", "云计算/DevOps": "ind-cloud", "网络安全": "ind-sec",
    "移动开发": "ind-mobile", "测试": "ind-qa", "嵌入式与物联网": "ind-iot",
    "游戏开发": "ind-game", "区块链与Web3": "ind-bc", "数据库与存储": "ind-db",
    "互联网/IT": "ind-it", "项目管理与协作": "ind-pm", "其他": "ind-other",
}
INDUSTRY_COLORS = {
    "人工智能": "#9B59B6",
    "AI/机器学习": "#9B59B6",
    "数据科学": "#E6A23C",
    "数据工程": "#E6A23C",
    "前端开发": "#409EFF",
    "后端开发": "#67C23A",
    "云计算/DevOps": "#36CFC9",
    "网络安全": "#F56C6C",
    "移动开发": "#1ABC9C",
    "测试": "#95A5A6",
    "嵌入式与物联网": "#607D8B",
    "游戏开发": "#9B59B6",
    "区块链与Web3": "#FF9800",
    "互联网/IT": "#3498DB",
    "其他": "#F39C12",
}
_INDUSTRY_KEYWORDS = {
    "人工智能": ["人工智能", "ai工程师", "算法工程师", "机器学习", "深度学习", "nlp", "大模型"],
    "AI/机器学习": ["ai ", "ml ", "算法"],
    "数据科学": ["数据科学", "分析师", "统计"],
    "数据工程": ["数据工程", "etl", "数仓", "数据仓库"],
    "前端开发": ["前端", "frontend", "vue", "react", "h5", "web前端"],
    "后端开发": ["后端", "backend", "服务端", "java", "go ", "python", "node"],
    "云计算/DevOps": ["devops", "sre", "运维", "云", "k8s", "docker"],
    "网络安全": ["安全", "security", "渗透", "安全工程师"],
    "移动开发": ["移动", "ios", "android", "flutter", "react native"],
    "测试": ["测试", "qa", "测开", "sdet"],
    "嵌入式与物联网": ["嵌入式", "iot", "单片机", "嵌入式软件"],
    "游戏开发": ["游戏", "unity", "unreal", "游戏开发"],
    "区块链与Web3": ["区块链", "web3", "solidity"],
    "互联网/IT": ["互联网", "it "],
}


def _classify_industry(name: str, industry: str) -> str:
    """Phase 13 Step 1: 按 Position.name + industry 关键词分类到 13 大行业。"""
    text = f"{industry or ''} {name or ''}".lower()
 # 按关键词最长优先匹配（"AI/机器学习" 比 "人工智能" 长，先匹配更具体的）
    for ind in sorted(_INDUSTRY_KEYWORDS.keys(), key=len, reverse=True):
        for kw in _INDUSTRY_KEYWORDS[ind]:
            if kw.lower() in text:
                return ind
    return "其他"


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
    except Exception as exc:
 # : 独立计数是补充指标,失败/列缺失时降级为 0,不拖垮主概览。
        logger.warning("Failed to fetch independent counts, degrading to zeros: {}", exc)
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
    except Exception as exc:
 # : Neo4j 不可用时降级返回空概览(仪表盘显示"暂无数据"),不抛 500。
 # 契约:test_driver_exception_returns_empty。
        logger.warning("Tech stack overview failed, degrading to empty: {}", exc)
        return {
            "domains": [],
            "connections": [],
            "total_positions": 0,
            "total_skills": 0,
            "independent_positions": 0,
            "independent_skills": 0,
            "independent_edges": 0,
        }

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
        "connections": _prune_connections(connections, domains),
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
    except Exception as exc:
 # : Neo4j 不可用时降级返回空概览,不抛 500。契约:test_driver_exception_returns_empty。
        logger.warning("Level overview failed, degrading to empty: {}", exc)
        return {
            "domains": [],
            "connections": [],
            "total_positions": 0,
            "total_skills": 0,
            "independent_positions": 0,
            "independent_skills": 0,
            "independent_edges": 0,
        }

    level_id = {"初级": "lv-junior", "中级": "lv-mid", "高级": "lv-senior"}
    domains = []
    total_pos = 0
    total_skill = 0
    for level, data in groups.items():
 # Step 5: 3 维泡始终保留(空 level 渲染为 0/0 透明泡),但占位不计入 total 计数。
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

 # Step 5: 兜底维度。PG 中 0 个 lv-junior 岗时，确保 3 维泡全在（0/0 透明），前端不会因缺桶渲染破图。
    for required_level in ("初级",):
        if not any(d["name"] == required_level for d in domains):
            domains.append(
                {
                    "id": level_id[required_level],
                    "name": required_level,
                    "position_count": 0,
                    "skill_count": 0,
                    "color": LEVEL_COLORS[required_level],
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
        "connections": _prune_connections(connections, domains),
        "total_positions": total_pos,
        "total_skills": total_skill,
        "independent_positions": counts["positions"],
        "independent_skills": counts["skills"],
        "independent_edges": counts["edges"],
    }


# Step 2: 热度视图（技能需求频次）
HEAT_BUCKETS: list[tuple[str, int, str]] = [
    ("高 (≥20岗)", 20, "#E74C3C"),
    ("中 (10-19岗)", 10, "#F39C12"),
    ("低 (1-9岗)", 1, "#3498DB"),
    ("无岗", 0, "#95A5A6"),
]

async def fetch_overview_by_heat(driver: AsyncDriver) -> dict[str, Any]:
    """Phase 13 Step 2: 按技能需求频率排序的"热度视图"。

    节点：需求 ≥ 1 的技能；按需求数量降序；前 30 个。
    边：REQUIRES 关联（直接展示"技能与技能"的共享岗位关系）。
    颜色：按 demand count 走 HEAT_COLOR_RAMP（蓝→深紫）。
    """
    counts_indep = await _fetch_independent_counts(driver)

    if driver is None:
        return {
            "domains": [],
            "connections": [],
            "total_positions": counts_indep["positions"],
            "total_skills": counts_indep["skills"],
            "independent_positions": counts_indep["positions"],
            "independent_skills": counts_indep["skills"],
            "independent_edges": counts_indep["edges"],
        }

    domains: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    total_skill = 0
    top_count = 0

    try:
        async with driver.session() as session:
 # 统计每个技能被多少 Position REQUIRES（需求频率）
            result = await session.run(
                "MATCH (p:Position)-[:REQUIRES]->(s:Skill) "
                "WITH s, count(DISTINCT p) AS demand "
                "WHERE demand >= 1 "
                "RETURN s.name AS name, demand "
                "ORDER BY demand DESC, s.name ASC "
                "LIMIT 30"
            )
            async for record in result:
                name = record["name"] or ""
                demand = int(record["demand"] or 0)
                if not name or demand <= 0:
                    continue
                domains.append({
                    "id": f"{HEAT_ID_PREFIX}{name}",
                    "name": name,
                    "position_count": demand,
                    "skill_count": 0,
                    "color": _heat_color(demand),
                })
                total_skill += demand
                if demand > top_count:
                    top_count = demand

 # 共享岗位关系（按 heat 排序，取 top 5 之间的 EVOLVES_TO 路径）
            if len(domains) >= 2:
                conn_result = await session.run(
                    "MATCH (s1:Skill)<-[:REQUIRES]-(p:Position)-[:REQUIRES]->(s2:Skill) "
                    "WHERE s1.name IN $ids AND s2.name IN $ids AND s1.name < s2.name "
                    "RETURN s1.name AS n1, s2.name AS n2, count(DISTINCT p) AS shared "
                    "ORDER BY shared DESC LIMIT 30",
                    ids=[d["name"] for d in domains[:5]],
                )
                async for record in conn_result:
                    n1 = record["n1"] or ""
                    n2 = record["n2"] or ""
                    if not n1 or not n2:
                        continue
                    shared = int(record["shared"] or 0)
                    connections.append({
                        "source_id": f"{HEAT_ID_PREFIX}{n1}",
                        "target_id": f"{HEAT_ID_PREFIX}{n2}",
                        "type": "CO_DEMANDED",
                        "properties": {"weight": min(1.0, shared / 5.0)},
                    })
    except Exception as exc:
        logger.exception("Heat overview failed: {}", exc)
        raise DashboardError(str(exc)) from exc

    return {
        "domains": domains,
        "connections": _prune_connections(connections, domains),
        "total_positions": counts_indep["positions"],
        "total_skills": counts_indep["skills"],
        "independent_positions": counts_indep["positions"],
        "independent_skills": counts_indep["skills"],
        "independent_edges": counts_indep["edges"],
    }
