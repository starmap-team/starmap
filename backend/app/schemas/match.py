"""Pydantic schemas for the Match API.

集中式 Pydantic 模型定义 — 路由层直接 import 使用,不在 api/v1/match.py 内联。
契约文件:`starmap-contracts/openapi.yaml`。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PersonSkillInput(BaseModel):
    """More permissive skill input for current frontend payloads."""

    skill_id: str | None = Field(default=None, description="技能 UUID（可选,旧数据可能为空）")
    name: str = Field(..., min_length=1, description="技能名称")
    category: str = Field(
        default="hard_skill",
        description="技能类别:hard_skill / soft_skill / tool / project_management / design / domain / language / certification / methodology",
    )
    proficiency: str = Field(default="熟悉", description="熟练度:了解 / 熟悉 / 精通")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="技能掌握置信度 0-1")
    source_count: int = Field(default=0, ge=0, description="来源数(用于反幻觉)")


class MatchOptionsInput(BaseModel):
    """Tuning options for match engine."""

    threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="技能匹配阈值")


class MatchRequestInput(BaseModel):
    """Request body for /match/position and /match/diagnose."""

    person_skills: list[PersonSkillInput] = Field(default_factory=list, description="用户已掌握技能")
    target_position: str = Field(..., min_length=1, description="目标岗位名称")
    options: MatchOptionsInput = Field(default_factory=MatchOptionsInput)


class BatchMatchItem(BaseModel):
    """Single item in a batch match request."""

    position: str = Field(default="", description="目标岗位名称")
    position_name: str = Field(default="", description="position 字段别名(兼容旧前端)")
    skills: list[PersonSkillInput] = Field(default_factory=list, description="用户技能")


class BatchMatchRequest(BaseModel):
    """Batch match request with validated items (P2 INJ-02/AUTHZ-03 修复)。"""

    entries: list[BatchMatchItem] = Field(
        default_factory=list,
        max_length=20,
        alias="items",
        description="批量岗位(最多 20 个)",
    )

    model_config = {"populate_by_name": True}


class SkillGapDetail(BaseModel):
    """Detailed skill gap entry."""

    skill: str = Field(..., description="技能名")
    importance: str = Field(..., description="required | bonus")
    gap_level: Literal["完全缺失", "部分掌握", "已掌握"]
    learning_path: list[str] = Field(default_factory=list, description="前置学习路径")


class MatchScoreBreakdown(BaseModel):
    """匹配分数拆解 — 让用户理解 match_score 的构成（D-01 透明化）。

    match_score = required_avg * weight_required + bonus_avg * weight_bonus
    inflated 表示该岗位存在 CII 通胀迹象（cii > 1.2），边缘必备项已被降为加分项。
    """

    required_avg: float = Field(ge=0.0, le=1.0, description="必备技能匹配均值")
    bonus_avg: float = Field(ge=0.0, le=1.0, description="加分技能匹配均值")
    weight_required: float = Field(ge=0.0, le=1.0, description="必备权重 0.7")
    weight_bonus: float = Field(ge=0.0, le=1.0, description="加分权重 0.3")
    inflated: bool = Field(default=False, description="是否应用了 CII 通胀修正")


class MatchResponse(BaseModel):
    """Match result for a single position."""

    match_id: str = Field(..., description="本次匹配 UUID")
    target_position: str = Field(..., description="目标岗位名称")
    match_score: float = Field(ge=0.0, le=1.0, description="综合匹配分 0-1")
    matched_skills: list[str] = Field(default_factory=list, description="已掌握的技能")
    gap_skills: list[str] = Field(default_factory=list, description="差距技能")
    recommendations: list[str] = Field(default_factory=list, description="学习建议")
    missing_required: list[str] = Field(default_factory=list, description="缺失的必备技能")
    missing_bonus: list[str] = Field(default_factory=list, description="缺失的加分技能")
    skill_gap_detail: list[SkillGapDetail] = Field(default_factory=list)
    overall_assessment: str = Field(default="", description="整体评估文案")
    estimated_learning_time: str = Field(default="", description="预计学习时长")
    cii: float | None = Field(default=None, description="能力通胀指数 0-1+")
    # D6 fix: add real trust_score (was missing — frontend was passing match_score as
    # trust-score by mistake, displaying duplicate "信任度" identical to "匹配度").
    # Computed as the MIN of matched_skills' Neo4j trust_score — the bottleneck
    # skill's trust determines the overall trustworthiness of the match.
    trust_score: float | None = Field(
        default=None,
        ge=0.0, le=1.0,
        description="已掌握技能中 Neo4j Skill.trust_score 的最小值（瓶颈信任度）",
    )
    # D-01: 分数拆解 — 用户可感知 match_score 的构成（必备均值×0.7 + 加分均值×0.3）
    score_breakdown: MatchScoreBreakdown | None = Field(
        default=None,
        description="匹配分数拆解（必需/加分均值与权重、是否通胀修正）",
    )
    note: str | None = Field(
        default=None,
        description="M2 补充说明(如岗位存在但无技能画像,无法计算匹配度)",
    )


class ReverseMatchRequest(BaseModel):
    """Request body for reverse matching: given user skills, find suitable positions."""

    person_skills: list[PersonSkillInput] = Field(default_factory=list, description="用户当前技能")
    # fix (M13): 兼容前端传 `skills` 字段(学习中心/匹配向导),自动归并到 person_skills
    skills: list[PersonSkillInput] = Field(
        default_factory=list,
        exclude=True,
        description="person_skills 的别名(前端兼容)",
    )
    top_k: int = Field(default=10, ge=1, le=50, description="最多返回岗位数")
    min_score: float = Field(default=0.3, ge=0.0, le=1.0, description="最低匹配分阈值")

    @model_validator(mode="after")
    def _merge_skills(self) -> ReverseMatchRequest:
        if self.skills and not self.person_skills:
            self.person_skills = list(self.skills)
        return self


class PositionRecommendation(BaseModel):
    """A single position recommendation from reverse matching."""

    position_name: str = Field(..., description="推荐岗位名")
    match_score: float = Field(ge=0.0, le=1.0, description="匹配分 0-1")
    matched_skills: list[str] = Field(default_factory=list, description="已掌握技能")
    gap_skills: list[str] = Field(default_factory=list, description="差距技能")
    skill_coverage: float = Field(ge=0.0, le=1.0, description="必备技能覆盖率")


class ReverseMatchResponse(BaseModel):
    """Response for reverse matching."""

    recommendations: list[PositionRecommendation] = Field(default_factory=list)
    total_positions_scanned: int = Field(ge=0, description="扫描的岗位总数")
    skills_provided: int = Field(ge=0, description="用户提供的技能数")


__all__ = [
    "PersonSkillInput",
    "MatchOptionsInput",
    "MatchRequestInput",
    "BatchMatchItem",
    "BatchMatchRequest",
    "SkillGapDetail",
    "MatchResponse",
    "ReverseMatchRequest",
    "PositionRecommendation",
    "ReverseMatchResponse",
]
