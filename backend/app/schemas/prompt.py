"""Prompt 管理域 Schema (PLAN-014 批次7)。

从 api/v1/admin_prompts.py 内联 4 个 Request 类迁入集中管理。
Response 形状 (PromptVersionInfo / ABResultSummary) 仍为 dict — 后续
批次统一 schema 化 (笔记本记: admin_prompts 全内联契约仍需 follow-up).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SetActiveRequest(BaseModel):
    """指定要激活的 prompt 版本。"""

    version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Target prompt version to activate, e.g. v1, v2",
    )


class ABTestRequest(BaseModel):
    """A/B 测试配置：canary 版本 + 流量分桶。"""

    canary_version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Candidate version",
    )
    traffic_fraction: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="Traffic fraction sent to canary in (0.0, 0.5]",
    )


class RegisterVersionRequest(BaseModel):
    """注册新 prompt 版本（可立即激活）。"""

    template: str = Field(
        ...,
        min_length=1,
        description="Prompt template content with placeholders",
    )
    version: str | None = Field(
        default=None,
        max_length=64,
        description="Version label, e.g. v4; auto-increment if omitted",
    )
    activate: bool = Field(
        default=False,
        description="Activate this version immediately",
    )


class ABResultRequest(BaseModel):
    """A/B 测试结果上报 (运行时客户端调用)。"""

    version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Version identifier (active or canary)",
    )
    success: bool = Field(default=True, description="Whether the prompt led to success")
    f1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional F1 score for this call",
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional latency in milliseconds",
    )
