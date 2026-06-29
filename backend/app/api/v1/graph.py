"""图谱查询 API。"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import get_neo4j_driver
from app.services.graph_service import fetch_panorama, fetch_position_graph, run_readonly_query

router = APIRouter(prefix="/graph", tags=["图谱查询"])


class GraphNode(BaseModel):
    """契约中的 GraphNode，供前端图谱组件消费。"""

    id: str = Field(..., description="节点唯一标识")
    labels: list[str] = Field(default_factory=list, description="节点标签")
    properties: dict[str, Any] = Field(default_factory=dict, description="节点属性键值对")


class GraphEdge(BaseModel):
    """契约中的 GraphEdge，供前端图谱组件消费。"""

    source_id: str = Field(..., description="源节点 id")
    target_id: str = Field(..., description="目标节点 id")
    type: str = Field(..., description="关系类型")
    properties: dict[str, Any] = Field(default_factory=dict, description="边属性")


class GraphQueryResponse(BaseModel):
    """图谱查询响应。"""

    nodes: list[GraphNode] = Field(default_factory=list, description="图谱节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="图谱边列表")


class GraphPanoramaResponse(BaseModel):
    """全景图谱响应，供前端图谱组件消费。"""

    nodes: list[GraphNode] = Field(default_factory=list, description="图谱节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="图谱边列表")


class PositionSkillGraphResponse(BaseModel):
    """岗位技能子图响应。"""

    position: dict[str, Any] | None = Field(default=None, description="岗位信息")
    skills: list[dict[str, Any]] = Field(default_factory=list, description="技能节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="技能关系边列表")


class PositionNode(BaseModel):
    """岗位技能接口中的扁平岗位信息。"""

    position_id: str = Field(default="", description="岗位唯一标识")
    name: str = Field(default="", description="岗位名称")
    industry: str = Field(default="", description="所属行业")
    description: str = Field(default="", description="岗位描述")
    skills_required: list[dict[str, Any]] = Field(default_factory=list, description="岗位所需技能")


class SkillNode(BaseModel):
    """岗位技能接口中的扁平技能信息。"""

    skill_id: str = Field(..., description="技能唯一标识")
    name: str = Field(..., description="技能名称")
    category: str = Field(default="hard_skill", description="技能分类")
    proficiency: str = Field(default="熟悉", description="熟练度")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    source_count: int = Field(default=0, ge=0, description="来源文档计数")
    trend: str = Field(default="stable", description="趋势方向")
    importance: str = Field(default="required", description="required/bonus")


class PositionSkillDetailResponse(BaseModel):
    """岗位技能子图响应，skills 为合同 SkillNode 扁平列表。"""

    position: PositionNode | None = Field(default=None, description="岗位信息")
    skills: list[SkillNode] = Field(default_factory=list, description="技能节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="技能关系边列表")


def _graph_nodes(items: list[dict[str, Any]]) -> list[GraphNode]:
    return [GraphNode(**item) for item in items]


def _graph_edges(items: list[dict[str, Any]]) -> list[GraphEdge]:
    return [GraphEdge(**item) for item in items]


@router.get(
    "/query",
    summary="Cypher 图谱查询",
    description="阶段2骨架接口。按契约接收只读 Cypher，阶段3接入图谱查询服务。",
    response_model=GraphQueryResponse,
)
async def graph_query(
    cypher: Annotated[
        str,
        Query(
            description="只读 Cypher 查询语句",
            examples=["MATCH (s:Skill)-[r:REQUIRED_FOR]->(p:Position) RETURN s, r, p LIMIT 50"],
        ),
    ],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> GraphQueryResponse:
    try:
        graph = await run_readonly_query(driver, cypher)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GraphQueryResponse(nodes=_graph_nodes(graph["nodes"]), edges=_graph_edges(graph["edges"]))


@router.get(
    "/panorama",
    summary="全景图谱",
    description=(
        "返回全量岗位-技能全景图谱。节点 properties 至少包含 name、category，"
        "边 properties 至少包含 weight。"
    ),
    response_model=GraphPanoramaResponse,
)
async def get_graph_panorama(
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> GraphPanoramaResponse:
    try:
        graph = await fetch_panorama(driver)
    except Exception as exc:
        from loguru import logger
        logger.error("Panorama query failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphPanoramaResponse(nodes=_graph_nodes(graph["nodes"]), edges=_graph_edges(graph["edges"]))


@router.get(
    "/position/{position_name}",
    summary="岗位图谱",
    description="按岗位名称或节点 id 获取岗位技能子图；阶段3前端兼容端点。",
    response_model=PositionSkillGraphResponse,
)
async def get_position_graph(
    position_name: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    depth: Annotated[int, Query(description="递归查询深度（含技能先修关系）", ge=1, le=5)] = 1,
) -> PositionSkillGraphResponse:
    graph = await fetch_position_graph(driver, position_name, depth)
    return PositionSkillGraphResponse(
        position=graph["position"],
        skills=graph["skills"],
        edges=_graph_edges(graph["edges"]),
    )


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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found")
    return PositionSkillDetailResponse(
        position=graph["position"],
        skills=graph["skills"],
        edges=_graph_edges(graph["edges"]),
    )

class DomainOverviewItem(BaseModel):
    """领域概览中的单个 KA 节点。"""
    id: str
    name: str
    position_count: int = 0
    skill_count: int = 0
    color: str = ""


class DomainOverviewResponse(BaseModel):
    """领域概览响应：KA 节点 + KA 间关联。"""
    domains: list[DomainOverviewItem] = Field(default_factory=list)
    connections: list[GraphEdge] = Field(default_factory=list)
    total_positions: int = 0
    total_skills: int = 0


class DomainDetailResponse(BaseModel):
    """单个领域的详情：KA 下的 Position 列表。"""
    domain_name: str = ""
    positions: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


@router.get(
    "/overview",
    summary="领域概览",
    description="返回 KnowledgeArea 节点 + 聚合统计，用于第一层领域视图。",
    response_model=DomainOverviewResponse,
)
async def get_graph_overview(
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    group_by: Annotated[str, Query(description="分组方式: domain(默认)/tech_stack/level")] = "domain",
) -> DomainOverviewResponse:
    if driver is None:
        return DomainOverviewResponse()
    # Dispatch to specialized queries
    if group_by == "tech_stack":
        from app.services.graph_service import fetch_overview_by_tech_stack
        data = await fetch_overview_by_tech_stack(driver)
        return DomainOverviewResponse(**data)
    if group_by == "level":
        from app.services.graph_service import fetch_overview_by_level
        data = await fetch_overview_by_level(driver)
        return DomainOverviewResponse(**data)
    from app.services.graph_service import serialize_node, serialize_relationship
    DOMAIN_COLORS = {
        "人工智能": "#9B59B6", "AI/机器学习": "#9B59B6",
        "数据科学": "#E6A23C", "数据工程": "#E6A23C",
        "前端工程": "#409EFF", "前端开发": "#409EFF",
        "后端架构": "#67C23A", "后端开发": "#67C23A",
        "云计算": "#36CFC9", "DevOps": "#36CFC9",
    }
    async with driver.session() as session:
        # Get all KA nodes with counts
        ka_query = """
        MATCH (ka:KnowledgeArea)
        OPTIONAL MATCH (ka)<-[:BELONGS_TO]-(s:Skill)
        OPTIONAL MATCH (s)<-[:REQUIRES]-(p:Position)
        RETURN ka, count(DISTINCT s) AS skill_count, count(DISTINCT p) AS pos_count
        """
        result = await session.run(ka_query)
        domains = []
        total_pos = 0
        total_skill = 0
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
            color = DOMAIN_COLORS.get(name, "#909399")
            for key, val in DOMAIN_COLORS.items():
                if key in name:
                    color = val
                    break
            domains.append(DomainOverviewItem(
                id=str(ka_node.element_id),
                name=name,
                position_count=pc,
                skill_count=sc,
                color=color,
            ))

        # Get KA-KA connections via shared positions
        conn_query = """
        MATCH (ka1:KnowledgeArea)<-[:BELONGS_TO]-(s:Skill)<-[:REQUIRES]-(p:Position)-[:REQUIRES]->(s2:Skill)-[:BELONGS_TO]->(ka2:KnowledgeArea)
        WHERE elementId(ka1) < elementId(ka2)
        RETURN DISTINCT ka1, ka2
        LIMIT 100
        """
        conn_result = await session.run(conn_query)
        connections = []
        async for record in conn_result:
            ka1 = record["ka1"]
            ka2 = record["ka2"]
            if ka1 and ka2:
                connections.append(GraphEdge(
                    source_id=str(ka1.element_id),
                    target_id=str(ka2.element_id),
                    type="SHARES_POSITION",
                    properties={"weight": 0.5},
                ))

    return DomainOverviewResponse(
        domains=domains,
        connections=connections,
        total_positions=total_pos,
        total_skills=total_skill,
    )


@router.get(
    "/domain/{domain_name}",
    summary="领域详情",
    description="返回指定 KnowledgeArea 下的 Position 节点列表。",
    response_model=DomainDetailResponse,
)
async def get_domain_detail(
    domain_name: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> DomainDetailResponse:
    if driver is None:
        return DomainDetailResponse(domain_name=domain_name)
    from app.services.graph_service import serialize_node, serialize_relationship
    async with driver.session() as session:
        query = """
        MATCH (ka:KnowledgeArea)-[:CONTAINS]-(s:Skill)<-[r:REQUIRES]-(p:Position)
        WHERE ka.name CONTAINS $name
        RETURN DISTINCT p, r, s
        """
        result = await session.run(query, name=domain_name)
        positions = {}
        edges = []
        async for record in result:
            p = record["p"]
            if p and p.element_id not in positions:
                positions[p.element_id] = serialize_node(p)
            r = record["r"]
            if r:
                edges.append(serialize_relationship(r))

    return DomainDetailResponse(
        domain_name=domain_name,
        positions=list(positions.values()),
        edges=edges,
    )
class KAPositionsResponse(BaseModel):
    """单个 KA 下的 Position 列表 + 关联 Skill 边。"""
    ka_id: str = ""
    ka_name: str = ""
    positions: list[GraphNode] = Field(default_factory=list)
    position_skill_edges: list[GraphEdge] = Field(default_factory=list)


@router.get(
    "/ka/{ka_id}/positions",
    summary="KA 下的岗位列表",
    description="返回指定 KnowledgeArea 下的 Position 节点及其与 Skill 的 REQUIRES 关系。",
    response_model=KAPositionsResponse,
)
async def get_ka_positions(
    ka_id: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> KAPositionsResponse:
    if driver is None:
        return KAPositionsResponse(ka_id=ka_id)
    from app.services.graph_service import serialize_node, serialize_relationship
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
        positions: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        async for record in result:
            p = record["p"]
            if p and p.element_id not in positions:
                positions[p.element_id] = serialize_node(p)
            r = record["r"]
            if r:
                edges.append(serialize_relationship(r))

    return KAPositionsResponse(
        ka_id=ka_id,
        ka_name=ka_name,
        positions=list(positions.values()),
        position_skill_edges=edges,
    )
