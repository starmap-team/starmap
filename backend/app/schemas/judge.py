"""Judge 域 Schema (PLAN-014 批次10)。

从 api/v1/judge.py 内联 6 个 BaseModel 迁入集中管理。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings


class JudgeRequest(BaseModel):
    """单样本评估请求：golden 标准答案 vs 系统输出."""

    golden: dict[str, Any] = Field(..., description="标准答案 (golden standard)")
    system_output: dict[str, Any] = Field(..., description="系统抽取结果")
    use_llm_judge: bool = Field(
        default=False,
        description="是否启用 LLM judge 进行多维度评分",
    )
    judge_prompt_version: str | None = Field(
        default=None,
        description="Judge prompt 版本号 (v1/v2), 默认使用 active 版本",
    )


class PairwiseRequest(BaseModel):
    """两两对比请求 (无 golden, A/B 测试场景)."""

    output_a: dict[str, Any] = Field(..., description="A 版本抽取结果")
    output_b: dict[str, Any] = Field(..., description="B 版本抽取结果")


class BatchJudgeRequest(BaseModel):
    """批量评估请求: JSONL 文件路径."""

    golden_file: str = Field(..., min_length=1, description="Golden set JSONL 文件路径")
    system_file: str = Field(..., min_length=1, description="System 输出 JSONL 文件路径")
    use_llm_judge: bool = Field(default=False, description="是否启用 LLM judge")
    judge_prompt_version: str | None = Field(default=None, description="Judge prompt 版本")
    threshold: float = Field(
        default=settings.eval_f1_gate,
        ge=0.0,
        le=1.0,
        description="质量门禁阈值 (NEW-11 唯一常量 settings.eval_f1_gate)",
    )


class JudgeSampleResponse(BaseModel):
    """单样本评估结果."""

    sample_id: str = Field(default="", description="样本 ID")
    precision: float = Field(default=0.0, ge=0.0, le=1.0, description="精确率")
    recall: float = Field(default=0.0, ge=0.0, le=1.0, description="召回率")
    f1: float = Field(default=0.0, ge=0.0, le=1.0, description="F1 分")
    llm_score: float | None = Field(default=None, ge=0.0, le=1.0, description="LLM judge 评分")
    llm_reasoning: str | None = Field(default=None, description="LLM judge 推理")
    errors: list[str] = Field(default_factory=list, description="错误列表")
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="评估时间 ISO 8601",
    )


class PairwiseResponse(BaseModel):
    """两两对比结果 (B vs A)."""

    sample_id: str = Field(default="", description="样本 ID")
    precision_b_vs_a: float = Field(default=0.0, description="B vs A 精确率差")
    recall_b_vs_a: float = Field(default=0.0, description="B vs A 召回率差")
    f1_b_vs_a: float = Field(default=0.0, description="B vs A F1 差")
    errors: list[str] = Field(default_factory=list, description="错误列表")
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="评估时间 ISO 8601",
    )


class BatchJudgeResponse(BaseModel):
    """批量评估汇总."""

    total_samples: int = Field(default=0, ge=0, description="总样本数")
    evaluated_samples: int = Field(default=0, ge=0, description="实际评估样本数")
    avg_precision: float = Field(default=0.0, ge=0.0, le=1.0, description="平均精确率")
    avg_recall: float = Field(default=0.0, ge=0.0, le=1.0, description="平均召回率")
    avg_f1: float = Field(default=0.0, ge=0.0, le=1.0, description="平均 F1")
    weighted_score: float = Field(default=0.0, description="加权总分")
    f1_distribution: dict[str, int] = Field(default_factory=dict, description="F1 分布")
    quality_gate: dict[str, Any] | None = Field(default=None, description="质量门禁结果")
    per_sample: list[dict[str, Any]] = Field(default_factory=list, description="逐样本详情")
    judge_prompt_version: str | None = Field(default=None, description="使用的 judge prompt 版本")
