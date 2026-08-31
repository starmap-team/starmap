"""Neo4j-backed graph query helpers for API v1.

业务说明：
    本模块封装了与 Neo4j 图数据库交互的查询逻辑（fetch_position_graph、overview）。
    序列化与计数逻辑已拆分至 graph_serializers.py（m7）。
    同步逻辑（sync_from_pipeline）已拆分至 graph_sync.py（m7）。
    本模块 re-export graph_serializers 的公共符号以保持向后兼容。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.graph_overview import (  # noqa: F401  (re-export)
    INDUSTRY_COLORS,
    INDUSTRY_ID_PREFIX,
    LEVEL_COLORS,
    TECH_STACK_COLORS,
    TECH_STACK_KEYWORDS,
    _classify_industry,
    _classify_level,
    _classify_tech_stack,
    _prune_connections,
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
from app.services.graph_serializers import (
    position_item as _position_item,  # noqa: F401  (re-export, private alias for backward compat)
)
from app.services.graph_serializers import (
    skill_item as _skill_item,  # noqa: F401  (re-export, private alias for backward compat)
)


# ── count/serializer 详见 graph_serializers.py ──
# ── overview 详见 graph_overview.py ──
async def _resolve_position_name(driver: Any, position_name: str) -> str:
 # 业务说明：根据用户输入的职位名称，在 Neo4j 中模糊匹配最接近的正式职位名称，
 # 支持精确匹配、子串匹配和双向包含匹配，提升搜索容错率。
 # 契约统一（name_cn→name）：前端下拉/深链可能传中文显示名 name_cn，这里先按
 # name_cn 精确/包含解析回 canonical name，再回退 name 精确/包含，保证两类键都能命中。
    """Resolve the closest Neo4j Position name (supports name & name_cn)."""
    async with driver.session() as session:
        # 1) 精确: p.name = $name 或 p.name_cn = $name
        exact = await session.run(
            "MATCH (p:Position) WHERE p.name = $name OR coalesce(p.name_cn, '') = $name "
            "RETURN p.name AS name LIMIT 1",
            name=position_name,
        )
        rec = await exact.single()
        if rec and rec["name"]:
            return rec["name"]
        # 2026-08-29 (PERF-02): 原实现 MATCH 全量拉取所有 Position 到 Python 做
        # 子串模糊匹配 → O(N) 全图扫描(实测 graph/overview 2.7s 的主因之一)。
        # 改为 Neo4j 侧 CONTAINS 过滤 + LIMIT 5, 只拉候选集做精度匹配。
        target = position_name.strip().lower()
        fuzzy = await session.run(
            "MATCH (p:Position) "
            "WHERE toLower(p.name) CONTAINS $kw "
            "   OR (coalesce(p.name_cn, '') <> '' AND toLower(p.name_cn) CONTAINS $kw) "
            "RETURN p.name AS name, coalesce(p.name_cn, '') AS name_cn LIMIT 5",
            kw=target,
        )
        async for row in fuzzy:
            candidate = str(row.get("name") or "").strip()
            candidate_cn = str(row.get("name_cn") or "").strip()
            cand_lower = candidate.lower()
            cand_cn_lower = candidate_cn.lower()
            # name_cn 为空时跳过包含匹配（`"" in target` 恒真会误命中）
            cn_hit = bool(candidate_cn) and (
                cand_cn_lower == target
                or target in cand_cn_lower
                or cand_cn_lower in target
            )
            # 2) 包含匹配: 保留"用户输入是候选名子串"(backend → Backend Engineer)，
            #    去掉"候选名是用户输入子串"——后者会让 "E2E Data Engineer" 误命中
            #    "Data Engineer"(候选名是输入的子串)，导致新岗位匹配到错误画像。
            #    name_cn 保留双向包含(中文容错)。
            if (
                cand_lower == target
                or target in cand_lower
                or cn_hit
            ):
                return candidate
    return position_name


async def fetch_position_graph(driver: Any, position_name: str, depth: int = 1) -> dict[str, Any]:
 # 业务说明：以指定职位为中心，按深度（depth）向外抓取子图，包含职位节点、关联技能节点及边关系。
 # 技术说明：
 # - depth=1 时仅抓取直接 REQUIRES 关系；
 # - depth>1 时支持可变长度路径（REQUIRES*1..depth），并递归抓取 PREREQUISITE 和 EVOLVES_TO 关系；
 # - depth 被限制在 [1, 5] 范围内，防止查询爆炸。
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
 # INJ-04: depth is int, clamped to [1,5] by API validator + max/min guard.
 # str(int) cannot inject Cypher syntax; assert for defense-in-depth.
            assert isinstance(depth, int) and 1 <= depth <= 5, f"depth must be int in [1,5], got {depth!r}"
            multi_query = (
                f"MATCH (position:Position)-[rel:REQUIRES*1..{depth}]->(skill:Skill) "
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


async def fetch_overview_by_domain(driver: Any) -> dict[str, Any]:
    """Fetch domain-grouped overview with KA nodes and connections.

    P1-3 fix: extracted from graph.py API route to keep route layer thin.
    P1 fix: when no KnowledgeArea nodes exist, fallback to grouping by
    Position.industry so the overview still shows meaningful clusters.
    """
    if driver is None:
        return {
            "domains": [],
            "connections": [],
            "total_positions": 0,
            "total_skills": 0,
            "independent_positions": 0,
            "independent_skills": 0,
            "independent_edges": 0,
        }

    _domain_colors = {
        "人工智能": "#9B59B6",
        "AI/机器学习": "#9B59B6",
        "AI": "#9B59B6",
        "数据科学": "#E6A23C",
        "数据工程": "#E6A23C",
        "数据库与存储": "#E6A23C",
        "前端工程": "#409EFF",
        "前端开发": "#409EFF",
        "后端架构": "#67C23A",
        "后端开发": "#67C23A",
        "云计算": "#36CFC9",
        "DevOps": "#36CFC9",
        "云原生与基础设施": "#36CFC9",
        "DevOps与运维": "#36CFC9",
        "大数据": "#E6A23C",
        "网络安全": "#F56C6C",
        "编程语言与框架": "#E67E22",
        "游戏开发": "#9B59B6",
        "移动开发": "#1ABC9C",
        "测试": "#95A5A6",
        "测试与质量保障": "#95A5A6",
        "嵌入式与物联网": "#607D8B",
        "项目管理与协作": "#FF9800",
        "设计": "#FF5722",
        "区块链与Web3": "#FF9800",
        "其他": "#F39C12",
        "其他技能领域": "#F39C12",
        "AI与机器学习": "#9B59B6",
        "云原生": "#36CFC9",
    }

 # Palette for domains not in the map above — prevents 灰色 flood
    _fallback_palette = [
        "#6366F1", "#8B5CF6", "#EC4899", "#F43F5E",
        "#14B8A6", "#06B6D4", "#0EA5E9", "#84CC16",
        "#EAB308", "#F97316", "#D946EF", "#10B981",
    ]

    async with driver.session() as session:
 # Get all KA nodes with counts
        ka_query = """
        MATCH (ka:KnowledgeArea)
        OPTIONAL MATCH (ka)<-[:BELONGS_TO]-(s:Skill)
        OPTIONAL MATCH (s)<-[:REQUIRES]-(p:Position)
        WITH ka, count(DISTINCT s) AS skill_count, count(DISTINCT p) AS pos_count
        WHERE skill_count > 0 OR pos_count > 0
        RETURN ka, skill_count, pos_count
        """
        result = await session.run(ka_query)
        domains = []
        total_pos = 0
        total_skill = 0
        fallback_idx = 0  # Index into fallback palette for unmatched domains
        async for record in result:
            ka_node = record["ka"]
            if ka_node is None:
                continue
            props = dict(ka_node)
            name = props.get("name", "")
            sc = record["skill_count"]
            pc = record["pos_count"]
            total_skill += sc
            total_pos += pc
 # Color resolution: exact match → palette rotation (no substring fallback)
            color = _domain_colors.get(name)
            if not color:
                color = _fallback_palette[fallback_idx % len(_fallback_palette)]
                fallback_idx += 1
            domains.append(
                {
                    "id": str(ka_node.element_id),
                    "name": name,
                    "position_count": pc,
                    "skill_count": sc,
                    "color": color,
                }
            )

 # Get independent counts (single query, fix pattern)
        count_result = await session.run(
            "MATCH (p:Position) WITH count(p) AS pos_cnt "
            "MATCH (s:Skill) WITH pos_cnt, count(s) AS skill_cnt "
            "MATCH ()-[r:REQUIRES]->() "
            "RETURN pos_cnt, skill_cnt, count(r) AS edge_cnt"
        )
        count_record = await count_result.single()
        if count_record:
            independent_pos = count_record["pos_cnt"]
            independent_skill = count_record["skill_cnt"]
            independent_edge = count_record["edge_cnt"]
        else:
            independent_pos = 0
            independent_skill = 0
            independent_edge = 0

 # ── Fallback: when no KA nodes, classify positions by 行业 ( Step 1) ──
 # 与 tech_stack 视图正交：tech_stack 按技术栈聚类，domain 按行业聚类。
        connections: list[dict[str, Any]] = []
        if not domains and independent_pos > 0:
            groups: dict[str, dict[str, Any]] = {}
            for industry_name, color in INDUSTRY_COLORS.items():
                groups[industry_name] = {"positions": [], "skills": set(), "color": color}

            pos_result = await session.run("MATCH (p:Position) RETURN p")
            async for record in pos_result:
                node = record["p"]
                if node is None:
                    continue
                props = _safe_properties(node)
                name = props.get("name", "")
                industry = props.get("industry", "")
                bucket = _classify_industry(name, industry)
                groups[bucket]["positions"].append({"id": _node_id(node), "name": name})

 # Count skills per industry
            skill_result = await session.run(
                "MATCH (p:Position)-[:REQUIRES]->(s:Skill) "
                "RETURN p.name AS pos_name, p.industry AS pos_industry, collect(DISTINCT s.name) AS skills"
            )
            async for record in skill_result:
                pos_name = record["pos_name"] or ""
                pos_industry = record["pos_industry"] or ""
                skills = record["skills"] or []
                bucket = _classify_industry(pos_name, pos_industry)
                for s in skills:
                    groups[bucket]["skills"].add(s)

            for industry_name, gdata in groups.items():
                if not gdata["positions"] and not gdata["skills"]:
                    continue
                pc = len(gdata["positions"])
                sc = len(gdata["skills"])
                total_pos += pc
                total_skill += sc
                domains.append({
                    "id": INDUSTRY_ID_PREFIX.get(industry_name, f"ind-{industry_name}"),
                    "name": industry_name,
                    "position_count": pc,
                    "skill_count": sc,
                    "color": gdata["color"],
                })

 # Build industry-industry connections (shared skills)
            if len(domains) > 1:
                conn_result = await session.run(
                    "MATCH (p1:Position)-[:REQUIRES]->(s:Skill)<-[:REQUIRES]-(p2:Position) "
                    "WHERE p1.name < p2.name "
                    "RETURN p1.name AS n1, p1.industry AS i1, p2.name AS n2, p2.industry AS i2, count(s) AS shared "
                    "ORDER BY shared DESC LIMIT 50"
                )
                bucket_connections: dict[tuple[str, str], int] = defaultdict(int)
                async for record in conn_result:
                    b1 = _classify_industry(record["n1"] or "", record["i1"] or "")
                    b2 = _classify_industry(record["n2"] or "", record["i2"] or "")
                    if b1 != b2:
                        key = tuple(sorted([b1, b2]))
                        bucket_connections[key] += record["shared"] or 0
                for (b1, b2), weight in bucket_connections.items():
                    connections.append({
                        "source_id": INDUSTRY_ID_PREFIX.get(b1, f"ind-{b1}"),
                        "target_id": INDUSTRY_ID_PREFIX.get(b2, f"ind-{b2}"),
                        "type": "SHARES_SKILLS",
                        "properties": {"weight": min(1.0, weight / 20.0)},
                    })
        else:
 # Get KA-KA connections via shared positions
            conn_query = """
            MATCH (ka1:KnowledgeArea)<-[:BELONGS_TO]-(s:Skill)<-[:REQUIRES]-(p:Position)-[:REQUIRES]->(s2:Skill)-[:BELONGS_TO]->(ka2:KnowledgeArea)
            WHERE elementId(ka1) < elementId(ka2)
            RETURN DISTINCT ka1, ka2
            LIMIT 100
            """
            conn_result = await session.run(conn_query)
            async for record in conn_result:
                ka1 = record["ka1"]
                ka2 = record["ka2"]
                if ka1 and ka2:
                    connections.append(
                        {
                            "source_id": str(ka1.element_id),
                            "target_id": str(ka2.element_id),
                            "type": "SHARES_POSITION",
                            "properties": {"weight": 0.5},
                        }
                    )

    return {
        "domains": domains,
        "connections": _prune_connections(connections, domains),
 # （ 强制规范）：total_* 一律用全局去重计数，禁止按域/KA 累加
 # 导致的重复计数（曾使 total_skills=395 而 distinct=257）。分组视图见 domains[]。
        "total_positions": independent_pos,
        "total_skills": independent_skill,
        "independent_positions": independent_pos,
        "independent_skills": independent_skill,
        "independent_edges": independent_edge,
    }
