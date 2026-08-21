"""岗位域 Schema：岗位节点、技能节点、列表分页。

PositionNode 和 SkillNode 同时用于：
- PostgreSQL + Neo4j 混合查询的响应
- 图谱可视化中的节点数据
- 匹配诊断的结果展示
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SkillCategory(StrEnum):
    """技能分类枚举。"""

    hard_skill = "hard_skill"
    soft_skill = "soft_skill"
    tool = "tool"
    certificate = "certificate"


class Proficiency(StrEnum):
    """熟练度等级。"""

    level_1 = "了解"
    level_2 = "熟悉"
    level_3 = "精通"


class ReviewStatus(StrEnum):
    """审核状态。"""

    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class SkillNode(BaseModel):
    """岗位所需技能骨架。

    对应 Neo4j Skill 节点 + Postgres skill_records 表。
    """

    skill_id: str = Field(
        min_length=1,
        description="技能唯一标识（归一化后的 stable ID）",
        examples=["py-core-001"],
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="技能展示名称",
        examples=["Python 核心编程"],
    )
    name_cn: str | None = Field(
        default=None,
        max_length=200,
        description="技能中文名（英文技能翻译后展示，前端 name_cn || name）",
    )
    category: str = Field(
        min_length=1,
        max_length=50,
        description="技能分类标签",
        examples=["hard_skill", "tool"],
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="该技能与岗位关联的置信度 [0, 1]",
    )
    source_count: int = Field(
        default=0,
        ge=0,
        description="支撑该技能的来源文档数量",
    )


class PositionNode(BaseModel):
    """岗位核心模型。

    对应 Postgres position_records + Neo4j Position 节点。
    """

    position_id: str = Field(
        min_length=1,
        description="岗位唯一标识（UUID 或自定义 ID）",
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="岗位名称",
        examples=["Python 后端开发工程师"],
    )
    name_cn: str = Field(
        default="",
        max_length=200,
        description="岗位中文名称",
    )
    industry: str = Field(
        default="",
        max_length=100,
        description="所属行业（可为空：DB 中 NULL/空 industry 岗位合法，契约与实现对齐）",
        examples=["信息技术", "金融"],
    )
    description: str = Field(
        default="",
        description="岗位描述文本",
    )
    skills_required: list[SkillNode] = Field(
        default_factory=list,
        description="岗位所要求的技能列表",
    )
    discovered_at: datetime | None = Field(
        default=None,
        description="首次发现时间（ISO 8601）",
    )
    review_status: ReviewStatus | None = Field(
        default=None,
        description="审核状态",
    )
    # 2026-08-20 (修复 C): 数据来源追溯 —— 让用户知根知底
    provenance: dict[str, Any] | None = Field(
        default=None,
        description=(
            "数据来源追溯信息：source_run_id（来源流水线）/created_by（创建人）/"
            "reviewed_by（审核人）/review_status（审核状态）/created_at（创建时间）"
        ),
    )


class PositionListResponse(BaseModel):
    """岗位列表分页响应。"""

    items: list[PositionNode] = Field(
        default_factory=list,
        description="当前页岗位列表",
    )
    total: int = Field(
        default=0,
        ge=0,
        description="符合条件的岗位总数",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="当前页码（从 1 开始）",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="每页数量",
    )


class IndustriesResponse(BaseModel):
    """行业列表响应。"""

    industries: list[str] = Field(
        default_factory=list,
        description="去重排序后的行业名称列表",
    )


class PositionSyncFailure(BaseModel):
    """单条岗位同步失败明细。"""

    name: str = Field(
        default="",
        max_length=200,
        description="同步失败的岗位名称",
    )
    canonical_id: str | None = Field(
        default=None,
        max_length=64,
        description="岗位 canonical_id（= PG PositionRecord.id 的字符串形式）",
    )
    error: str = Field(
        default="",
        max_length=500,
        description="失败原因（截断至 500 字符）",
    )


class PositionSyncResult(BaseModel):
    """全量 PG → Neo4j Position 同步结果。"""

    synced: int = Field(
        default=0,
        ge=0,
        description="成功 MERGE 到 Neo4j 的 Position 节点数",
    )
    failed: list[PositionSyncFailure] = Field(
        default_factory=list,
        description="失败明细列表（单条失败不阻断全量补跑）",
    )
    total: int = Field(
        default=0,
        ge=0,
        description="PG position_records 总行数",
    )
    pruned: int = Field(
        default=0,
        ge=0,
        description="剪枝掉的无 canonical_id 遗留 Position 节点数（prune_legacy=true 时生效）",
    )
    started_at: str = Field(
        default="",
        description="同步开始时间（ISO 8601）",
    )
    finished_at: str = Field(
        default="",
        description="同步结束时间（ISO 8601）",
    )
