"""图谱查询 API。"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

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
    """图谱查询响应。阶段2先返回空图骨架。"""

    nodes: list[GraphNode] = Field(default_factory=list, description="图谱节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="图谱边列表")


class GraphPanoramaResponse(BaseModel):
    """全景图谱响应。"""

    nodes: list[GraphNode] = Field(default_factory=list, description="图谱节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="图谱边列表")


class PositionSkillGraphResponse(BaseModel):
    """岗位技能子图响应骨架。"""

    position: dict[str, Any] | None = Field(default=None, description="岗位信息")
    skills: list[dict[str, Any]] = Field(default_factory=list, description="技能节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="技能关系边列表")


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
) -> GraphQueryResponse:
    _ = cypher
    return GraphQueryResponse()


@router.get(
    "/panorama",
    summary="全景图谱",
    description="阶段2骨架接口。默认返回全图，阶段3接入图谱查询服务。",
    response_model=GraphPanoramaResponse,
)
async def get_graph_panorama() -> GraphPanoramaResponse:
    return GraphPanoramaResponse()


@router.get(
    "/position/{position_id}/skills",
    summary="岗位技能图谱",
    description="阶段3前的占位接口。",
    response_model=PositionSkillGraphResponse,
)
async def get_position_skills(
    position_id: str,
    depth: Annotated[int, Query(description="递归查询深度（含技能先修关系）", ge=1, le=5)] = 1,
) -> PositionSkillGraphResponse:
    _ = (position_id, depth)
    return PositionSkillGraphResponse()
