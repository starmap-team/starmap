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
    graph = await fetch_panorama(driver)
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
    return PositionSkillDetailResponse(
        position=graph["position"],
        skills=graph["skills"],
        edges=_graph_edges(graph["edges"]),
    )
