"""图谱查询 API。"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_neo4j_driver
from app.schemas.graph import (
    DomainOverviewResponse,
    GraphEdge,
    KAPositionsResponse,
    PositionSkillDetailResponse,
)
from app.services.graph_serializers import _safe_properties
from app.services.graph_service import fetch_position_graph

router = APIRouter(prefix="/graph", tags=["图谱查询"])


def _graph_edges(items: list[dict[str, Any]]) -> list[GraphEdge]:
    return [GraphEdge(**item) for item in items]


@router.get(
    "/position/{position_id}/skills",
    summary="岗位技能图谱",
    description="按岗位名称或节点 id 获取岗位技能子图；skills 返回扁平 SkillNode 字段。",
    response_model=PositionSkillDetailResponse,
)
async def get_position_skills(
    position_id: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    depth: Annotated[int, Query(description="递归查询深度（含技能先修关系）", ge=1, le=5)] = 1,
) -> PositionSkillDetailResponse:
    graph = await fetch_position_graph(driver, position_id, depth)
    if graph["position"] is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")
    return PositionSkillDetailResponse(
        position=graph["position"],
        skills=graph["skills"],
        edges=_graph_edges(graph["edges"]),
    )


@router.get(
    "/overview",
    summary="领域概览",
    description="返回 KnowledgeArea 节点 + 聚合统计，用于第一层领域视图。",
    response_model=DomainOverviewResponse,
)
async def get_graph_overview(
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    group_by: Annotated[
        Literal["domain", "tech_stack", "level", "heat"], Query(description="分组方式: domain(默认)/tech_stack/level/heat(技能需求频次)")
    ] = "domain",
) -> DomainOverviewResponse:
    import time

    # PLAN-006④: 服务端响应时间戳注入；前端据此显示"截至 X"诚实信号
    # （Neo4j 节点无内置 updated_at，不编造节点级 freshness）
    generated_at = time.time()
    if driver is None:
        return DomainOverviewResponse(
            independent_positions=0,
            independent_skills=0,
            independent_edges=0,
            generated_at=generated_at,
        )
    # Dispatch to specialized queries
    from app.services.graph_service import (
        fetch_overview_by_domain,
        fetch_overview_by_level,
        fetch_overview_by_tech_stack,
    )
    if group_by == "tech_stack":
        data = await fetch_overview_by_tech_stack(driver)
        return DomainOverviewResponse(**data, generated_at=generated_at)
    if group_by == "domain":
        data = await fetch_overview_by_domain(driver)
        return DomainOverviewResponse(**data, generated_at=generated_at)
    if group_by == "level":
        data = await fetch_overview_by_level(driver)
        return DomainOverviewResponse(**data, generated_at=generated_at)
    if group_by == "heat":
        from app.services.graph_overview import fetch_overview_by_heat
        data = await fetch_overview_by_heat(driver)
        return DomainOverviewResponse(**data, generated_at=generated_at)


@router.get(
    "/ka/{ka_id}/positions",
    summary="KA 下的岗位列表",
    description="返回指定 KnowledgeArea 下的 Position 节点及其与 Skill 的 REQUIRES 关系。支持 domain/tech_stack/level 三种模式。",
    response_model=KAPositionsResponse,
)
async def get_ka_positions(
    ka_id: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> KAPositionsResponse:
    if driver is None:
        return KAPositionsResponse(ka_id=ka_id)
    from app.services.graph_service import serialize_node, serialize_relationship

    # ── Dispatch by ID prefix ──
    # domain mode: ka_id is Neo4j elementId (e.g. "4:xxx:123")
    # tech_stack mode: ka_id is literal like "ts-ai", "ts-bigdata"
    # level mode: ka_id is literal like "lv-junior", "lv-mid"
    if ka_id.startswith("ts-") or ka_id.startswith("lv-"):
        # Build a synthetic category filter — reuse the same classifiers
        # from graph_overview.py to find matching positions.
        from app.services.graph_overview import (
            _classify_level,
            _classify_tech_stack,
        )

        # Reverse-lookup the category name from the literal ID
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
        level_id = {"初级": "lv-junior", "中级": "lv-mid", "高级": "lv-senior"}
        is_tech_stack = ka_id.startswith("ts-")
        ka_name = ""
        if is_tech_stack:
            for name, lid in stack_id_prefix.items():
                if lid == ka_id:
                    ka_name = name
                    break
        else:
            for name, lid in level_id.items():
                if lid == ka_id:
                    ka_name = name
                    break

        async with driver.session() as session:
            # Phase 1: fetch all Positions and filter in-application
            result = await session.run("MATCH (p:Position) RETURN p")
            matched_element_ids: list[str] = []
            positions: dict[str, dict[str, Any]] = {}
            async for record in result:
                p_node = record["p"]
                if p_node is None:
                    continue
                props = _safe_properties(p_node)
                name = props.get("name", "")
                industry = props.get("industry", "")
                if is_tech_stack:
                    matched = _classify_tech_stack(industry, name) == ka_name
                else:
                    matched = _classify_level(name, props) == ka_name
                if not matched:
                    continue
                pos_data = serialize_node(p_node)
                if pos_data["id"] not in positions:
                    positions[pos_data["id"]] = pos_data
                    matched_element_ids.append(p_node.element_id)

            # Phase 2: batch-fetch REQUIRES edges + Skill nodes for all matched positions
            skills: dict[str, dict[str, Any]] = {}
            edges: list[dict[str, Any]] = []
            if matched_element_ids:
                edge_result = await session.run(
                    "MATCH (p:Position)-[r:REQUIRES]->(s:Skill) WHERE elementId(p) IN $pids RETURN r, s",
                    pids=matched_element_ids,
                )
                async for e_record in edge_result:
                    r = e_record["r"]
                    s = e_record["s"]
                    if r:
                        edges.append(serialize_relationship(r))
                    if s and s.element_id not in skills:
                        skills[s.element_id] = serialize_node(s)

        return KAPositionsResponse(
            ka_id=ka_id,
            ka_name=ka_name,
            positions=list(positions.values()),
            position_skill_edges=edges,
            skills=list(skills.values()),
        )

    # ── heat mode: ka_id is "heat-skill-{skillName}" ──
    if ka_id.startswith("heat-skill-"):
        skill_name = ka_id[len("heat-skill-"):]
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Position)-[:REQUIRES]->(s:Skill {name: $sname}) "
                "RETURN p, collect(DISTINCT s) AS skills",
                sname=skill_name,
            )
            positions_dict: dict[str, dict[str, Any]] = {}
            skills_dict: dict[str, dict[str, Any]] = {}
            edges: list[dict[str, Any]] = []
            async for record in result:
                p_node = record["p"]
                if p_node is None:
                    continue
                pos_data = serialize_node(p_node)
                if pos_data["id"] not in positions_dict:
                    positions_dict[pos_data["id"]] = pos_data
                for s_node in record["skills"] or []:
                    if s_node and s_node.element_id not in skills_dict:
                        skills_dict[s_node.element_id] = serialize_node(s_node)
                    if s_node and p_node:
                        edges.append({"source_id": p_node.element_id, "target_id": s_node.element_id, "type": "REQUIRES", "properties": {}})
            return KAPositionsResponse(
                ka_id=ka_id,
                ka_name=skill_name,
                positions=list(positions_dict.values()),
                position_skill_edges=edges,
                skills=list(skills_dict.values()),
            )

    # ── industry mode: ka_id is "ind-{industryKey}" ──
    if ka_id.startswith("ind-"):
        from app.services.graph_overview import INDUSTRY_ID_PREFIX, _classify_industry
        # Reverse-lookup the industry name from the literal ID
        industry_name = ""
        for name, prefix in INDUSTRY_ID_PREFIX.items():
            if prefix == ka_id:
                industry_name = name
                break
        if not industry_name:
            industry_name = ka_id[len("ind-"):]

        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN p")
            matched_element_ids: list[str] = []
            positions_dict: dict[str, dict[str, Any]] = {}
            async for record in result:
                p_node = record["p"]
                if p_node is None:
                    continue
                props = _safe_properties(p_node)
                name = props.get("name", "")
                industry = props.get("industry", "")
                matched = _classify_industry(name, industry) == industry_name
                if not matched:
                    continue
                pos_data = serialize_node(p_node)
                if pos_data["id"] not in positions_dict:
                    positions_dict[pos_data["id"]] = pos_data
                    matched_element_ids.append(p_node.element_id)

            skills_dict: dict[str, dict[str, Any]] = {}
            edges: list[dict[str, Any]] = []
            if matched_element_ids:
                edge_result = await session.run(
                    "MATCH (p:Position)-[r:REQUIRES]->(s:Skill) WHERE elementId(p) IN $pids RETURN r, s",
                    pids=matched_element_ids,
                )
                async for e_record in edge_result:
                    r = e_record["r"]
                    s = e_record["s"]
                    if r:
                        edges.append(serialize_relationship(r))
                    if s and s.element_id not in skills_dict:
                        skills_dict[s.element_id] = serialize_node(s)

        return KAPositionsResponse(
            ka_id=ka_id,
            ka_name=industry_name,
            positions=list(positions_dict.values()),
            position_skill_edges=edges,
            skills=list(skills_dict.values()),
        )

    # ── domain mode: match by Neo4j elementId ──
    async with driver.session() as session:
        # Find KA name first
        ka_query = """
        MATCH (ka:KnowledgeArea)
        WHERE elementId(ka) = $ka_id
        RETURN ka.name AS name
        LIMIT 1
        """
        ka_result = await session.run(ka_query, ka_id=ka_id)
        ka_record = await ka_result.single()
        ka_name = ka_record["name"] if ka_record and ka_record["name"] else ""

        # Get positions under this KA via Skill BELONGS_TO
        query = """
        MATCH (ka:KnowledgeArea)<-[:BELONGS_TO]-(s:Skill)<-[r:REQUIRES]-(p:Position)
        WHERE elementId(ka) = $ka_id
        RETURN DISTINCT p, r, s
        """
        result = await session.run(query, ka_id=ka_id)
        domain_positions: dict[str, dict[str, Any]] = {}
        domain_skills: dict[str, dict[str, Any]] = {}
        domain_edges: list[dict[str, Any]] = []
        async for record in result:
            p = record["p"]
            if p and p.element_id not in domain_positions:
                domain_positions[p.element_id] = serialize_node(p)
            s = record["s"]
            if s and s.element_id not in domain_skills:
                domain_skills[s.element_id] = serialize_node(s)
            r = record["r"]
            if r:
                domain_edges.append(serialize_relationship(r))

    return KAPositionsResponse(
        ka_id=ka_id,
        ka_name=ka_name,
        positions=list(domain_positions.values()),
        position_skill_edges=domain_edges,
        skills=list(domain_skills.values()),
    )
