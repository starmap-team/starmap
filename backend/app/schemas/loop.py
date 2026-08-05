"""Loop 域 Schema (PLAN-014 批次12).

从 api/v1/loop.py 内联 4 个 BaseModel 迁入集中管理.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LoopRunRequest(BaseModel):
    """Request body for POST /loop/run."""

    jd_text: str = Field(..., min_length=1, description="Raw JD text to process")
    target_position: str | None = Field(
        default=None,
        description="Target position name for match diagnosis (optional, LOOP-09)",
    )

    @field_validator("target_position")
    @classmethod
    def coerce_empty_string(cls, v: str | None) -> str | None:
        """Convert empty/whitespace-only strings to None so the field is truly optional."""
        if v is not None and not v.strip():
            return None
        return v


class LoopStepResponse(BaseModel):
    """Single step result in the loop timeline."""

    step: int = Field(..., ge=0, description="步骤序号")
    name: str = Field(..., min_length=1, description="步骤名")
    status: str = Field(..., min_length=1, description="pending/running/done/failed")
    data: dict[str, Any] = Field(default_factory=dict, description="步骤输出")
    error: str | None = Field(default=None, description="错误信息")
    duration_seconds: float = Field(default=0.0, ge=0, description="步骤耗时 (秒)")
    note: str | None = Field(default=None, description="备注")


class LoopRunResponse(BaseModel):
    """Response for POST /loop/run."""

    run_id: str = Field(..., min_length=1, description="运行 ID")
    jd_text: str = Field(..., description="原始 JD 文本")
    target_position: str | None = Field(default=None, description="目标岗位")
    status: str = Field(..., min_length=1, description="运行状态")
    steps: list[LoopStepResponse] = Field(default_factory=list, description="步骤时间线")
    extracted_skills: list[dict[str, Any]] = Field(default_factory=list, description="抽取技能")
    graph_update: dict[str, Any] = Field(default_factory=dict, description="图谱更新结果")
    match_result: dict[str, Any] = Field(default_factory=dict, description="匹配结果")
    learning_path: dict[str, Any] = Field(default_factory=dict, description="学习路径")
    total_duration_seconds: float = Field(default=0.0, ge=0, description="总耗时 (秒)")


class LoopHistoryResponse(BaseModel):
    """Response for GET /loop/history."""

    items: list[dict[str, Any]] = Field(default_factory=list, description="历史运行记录")
