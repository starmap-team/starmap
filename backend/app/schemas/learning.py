"""Pydantic schemas for the Learning API.

集中式 Pydantic 模型定义 — 路由层直接 import 使用,不在 api/v1/learning.py 内联。
契约文件:`starmap-contracts/openapi.yaml`。

迁移说明:这些类原在 backend/app/api/v1/learning.py 内联定义,违反
docs/standards/01-backend/02-API路由层.md 强制规则 #2。Phase X 闭环
审计时全部迁出,路由层改为 import。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SkillGapInput(BaseModel):
    """Skill gap from match diagnosis."""

    skill: str = Field(..., min_length=1, description="技能名称")
    importance: str = Field(default="required", description="required | bonus")
    gap_level: str = Field(
        default="完全缺失",
        description="完全缺失 | 部分掌握 | 已掌握",
    )
    learning_path: list[str] = Field(default_factory=list, description="前置技能链")
    target_proficiency: str = Field(default="熟悉", description="目标熟练度")


class CreatePlanRequest(BaseModel):
    """Request to create a learning plan."""

    position: str = Field(..., min_length=1, description="目标岗位")
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="匹配分 0-1")
    skills: list[SkillGapInput] = Field(..., min_length=1, description="技能缺口列表")
    available_hours_per_week: float = Field(
        default=10.0, ge=1.0, le=40.0, description="每周可用学习小时数"
    )


class SkillProgressItem(BaseModel):
    """Per-skill progress in plan response."""

    skill_name: str = Field(..., description="技能名")
    status: str = Field(..., description="not_started | in_progress | mastered | completed")
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="进度 0-100")
    importance: str = Field(default="required", description="required | bonus")
    estimated_hours: float = Field(default=0.0, ge=0.0, description="估算学习小时数")
    started_at: str | None = Field(default=None, description="ISO 8601")
    completed_at: str | None = Field(default=None, description="ISO 8601")
    notes: str | None = Field(default=None, description="学习笔记")


class PhaseInfo(BaseModel):
    """Learning phase info."""

    phase: int = Field(ge=1, description="阶段序号")
    skills: list[str] = Field(default_factory=list, description="该阶段包含的技能")
    estimated_hours: float = Field(ge=0.0, description="该阶段总学习小时数")
    estimated_weeks: float = Field(ge=0.0, description="该阶段预计完成周数")


class PlanResponse(BaseModel):
    """Learning plan response."""

    plan_id: str = Field(..., description="计划 UUID")
    position: str = Field(..., description="目标岗位")
    status: str = Field(..., description="active | completed | archived")
    match_score_at_creation: float = Field(default=0.0, ge=0.0, le=1.0, description="创建时的匹配分")
    overall_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="整体完成度 0-100")
    total_hours: float = Field(default=0.0, ge=0.0, description="总学习小时数")
    total_weeks: float = Field(default=0.0, ge=0.0, description="总学习周数")
    phase_count: int = Field(default=0, ge=0, description="阶段数")
    phases: list[PhaseInfo] = Field(default_factory=list, description="学习阶段列表")
    skills: list[SkillProgressItem] = Field(default_factory=list, description="技能进度列表")
    stats: dict[str, Any] = Field(default_factory=dict, description="计划级别统计")


class UpdateProgressRequest(BaseModel):
    """Request to update skill progress."""

    skill_name: str = Field(..., min_length=1, description="技能名")
    status: str | None = Field(
        default=None,
        description="not_started | in_progress | mastered",
    )
    progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    notes: str | None = Field(default=None, description="学习笔记")


class RecommendationItem(BaseModel):
    """A personalized learning recommendation."""

    skill: str = Field(..., description="推荐学习的技能")
    importance: str = Field(..., description="required | bonus")
    gap_level: str = Field(..., description="完全缺失 | 部分掌握 | 已掌握")
    estimated_hours: float = Field(default=0.0, ge=0.0, description="估算学习小时数")
    prerequisites: list[str] = Field(default_factory=list, description="前置技能")
    reason: str = Field(default="", description="推荐原因")


class RecommendationsResponse(BaseModel):
    """Response for personalized recommendations."""

    items: list[RecommendationItem] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)


class AddSkillRequest(BaseModel):
    """Request to add a new skill to an existing plan."""

    skill_name: str = Field(..., min_length=1, description="技能名称")
    importance: str = Field(default="bonus", description="required | bonus")
    estimated_hours: float = Field(default=20.0, ge=0.0, description="预计学习小时数")


__all__ = [
    "SkillGapInput",
    "CreatePlanRequest",
    "SkillProgressItem",
    "PhaseInfo",
    "PlanResponse",
    "UpdateProgressRequest",
    "RecommendationItem",
    "RecommendationsResponse",
    "AddSkillRequest",
]
