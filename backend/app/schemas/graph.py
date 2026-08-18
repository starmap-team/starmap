"""图谱域 Schema：图节点、边、概览、详情。

对应 Neo4j 查询返回的图数据模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class GraphPositionNode(BaseModel):
    """图域岗位扁平节点（Neo4j Position 序列化产物）。

    与 position.PositionNode 不同：skills_required 为 Neo4j 属性原始
    dict 列表（无规范子结构），且无 PG 侧的 discovered_at/review_status。
    原内联于 graph 路由，违反 Schema 集中管理约定，2026-08-05 迁入。
    """

    position_id: str = Field(default="", description="岗位唯一标识")
    name: str = Field(default="", description="岗位名称")
    name_cn: str = Field(default="", description="岗位中文名称")
    industry: str = Field(default="", description="所属行业")
    description: str = Field(default="", description="岗位描述")
    skills_required: list[dict[str, Any]] = Field(
        default_factory=list,
        description="岗位所需技能（Neo4j 属性原始 dict 列表）",
    )


class GraphSkillNode(BaseModel):
    """图域技能扁平节点（Neo4j Skill 节点 + REQUIRES 关系序列化产物）。

    与 position.SkillNode 不同：额外携带 proficiency/trend/importance
    （源自关系属性 level/required 的归一化结果）。
    原内联于 graph 路由，违反 Schema 集中管理约定，2026-08-05 迁入。
    """

    skill_id: str = Field(min_length=1, description="技能唯一标识")
    name: str = Field(min_length=1, description="技能名称")
    category: str = Field(default="hard_skill", description="技能分类")
    proficiency: str = Field(default="熟悉", description="熟练度")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    source_count: int = Field(default=0, ge=0, description="来源文档计数")
    trend: str = Field(default="stable", description="趋势方向")
    importance: str = Field(default="required", description="required/bonus")


class PositionSkillDetailResponse(BaseModel):
    """岗位技能子图响应：position + skills 扁平列表 + REQUIRES 边。

    以 GET /graph/position/{position_id}/skills 真实返回为准（前端
    match/jd store 均按 {position, skills, edges} 消费）。旧契约含
    paths 字段与真实 API 漂移，2026-08-05 对齐修正。
    """

    position: GraphPositionNode | None = Field(default=None, description="岗位信息")
    skills: list[GraphSkillNode] = Field(default_factory=list, description="技能节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="技能关系边列表")


class KAPositionsResponse(BaseModel):
    """单个 KA 下的 Position 列表 + 关联 Skill 边。

    对应 GET /graph/ka/{ka_id}/positions。原内联于 graph 路由，违反
    Schema 集中管理约定，2026-08-05 迁入。
    """

    ka_id: str = Field(default="", description="KA 节点 ID 或模式字面量（ts-/lv-/heat-/ind-）")
    ka_name: str = Field(default="", description="KA 名称（用于展示）")
    positions: list[GraphNode] = Field(default_factory=list, description="Position 节点列表")
    position_skill_edges: list[GraphEdge] = Field(default_factory=list, description="Position-REQUIRES-Skill 边列表")
    skills: list[GraphNode] = Field(default_factory=list, description="关联的 Skill 节点")


class DomainOverviewItem(BaseModel):
    """领域概览中的单个 KA 节点。"""

    id: str = Field(min_length=1, description="知识域节点 ID")
    name: str = Field(min_length=1, description="知识域名称")
    position_count: int = Field(default=0, ge=0, description="关联岗位数")
    skill_count: int = Field(default=0, ge=0, description="关联技能数")
    color: str = Field(default="", description="节点颜色")


class DomainOverviewResponse(BaseModel):
    """领域概览响应：KA 节点 + KA 间关联 + 独立节点统计。

    对应 GET /graph/overview 实际返回结构（原内联于路由，违反
    Schema 集中管理约定，2026-08-05 迁入）。
    """

    domains: list[DomainOverviewItem] = Field(default_factory=list, description="KA 节点列表")
    connections: list[GraphEdge] = Field(default_factory=list, description="KA 间关联边")
    total_positions: int = Field(default=0, ge=0, description="岗位总数")
    total_skills: int = Field(default=0, ge=0, description="技能总数")
 # 独立节点计数（去重，与 Neo4j 实际节点数一致）
    independent_positions: int = Field(default=0, ge=0, description="独立 Position 节点数（去重）")
    independent_skills: int = Field(default=0, ge=0, description="独立 Skill 节点数（去重）")
    independent_edges: int = Field(default=0, ge=0, description="独立 REQUIRES 关系数（去重）")
 # ④: 服务端响应生成时间（Unix 秒），前端可据此显示"截至 X"，避免编造 freshness
    generated_at: float = Field(default=0.0, ge=0, description="响应生成 Unix 时间戳")


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
