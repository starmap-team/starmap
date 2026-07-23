"""图谱域 Schema：图节点、边、概览、详情。

对应 Neo4j 查询返回的图数据模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.position import PositionNode, SkillNode


class GraphNode(BaseModel):
    """通用图谱节点。

    对应 Neo4j 中的任意节点类型。
    """

    id: str = Field(min_length=1, description="节点稳定 ID")
    labels: list[str] = Field(
        default_factory=list,
        description="Neo4j 节点标签列表",
        examples=[["Position"], ["Skill", "Tool"]],
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="节点属性键值对",
    )


class GraphEdge(BaseModel):
    """通用图谱边。"""

    source_id: str = Field(min_length=1, description="源节点 ID")
    target_id: str = Field(min_length=1, description="目标节点 ID")
    type: str = Field(
        min_length=1,
        description="关系类型",
        examples=["REQUIRES", "EVOLVES_TO", "BELONGS_TO"],
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="边属性键值对",
    )


class GraphOverviewResponse(BaseModel):
    """图谱全局概览。

    用于仪表盘首页展示图谱统计信息。
    """

    total_nodes: int = Field(ge=0, description="图谱总节点数")
    total_edges: int = Field(ge=0, description="图谱总边数")
    total_positions: int = Field(ge=0, description="岗位节点数")
    total_skills: int = Field(ge=0, description="技能节点数")
    total_domains: int = Field(ge=0, description="知识域节点数")
    trust_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="全局可信度评分 [0, 1]",
    )
    hallucination_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="全局幻觉率 [0, 1]",
    )
    pipeline_status: str = Field(
        default="idle",
        description="数据管线状态",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="数据快照时间",
    )


class PositionSkillDetailResponse(BaseModel):
    """岗位-技能详情（含路径信息）。"""

    position: PositionNode = Field(description="岗位节点")
    skills: list[SkillNode] = Field(
        default_factory=list,
        description="关联技能列表",
    )
    paths: list[list[str]] = Field(
        default_factory=list,
        description="岗位到技能的关系路径（用于可视化）",
    )


class GraphQueryRequest(BaseModel):
    """图谱查询请求（按需子图）。"""

    position_ids: list[str] | None = Field(
        default=None,
        description="按岗位 ID 筛选（空表示全部）",
    )
    max_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="最大展开深度",
    )
    include_edges: bool = Field(
        default=True,
        description="是否包含边数据",
    )
