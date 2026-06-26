"""Judge API: §7.2 LLM-as-judge 评估端点。

提供单样本评估、两两对比和批量评测三个接口，
作为流 D (QA) 的自动化评估基础。
"""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.extraction.llm_client import (
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.services.judge_service import (
    evaluate_batch_async,
    evaluate_pair_async,
    evaluate_sample_async,
)

router = APIRouter(prefix="/judge")


# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class JudgeRequest(BaseModel):
    """单样本评估请求：golden 标准答案 vs 系统输出。"""

    golden: dict[str, Any] = Field(..., description="标准答案 (golden standard)")
    system_output: dict[str, Any] = Field(..., description="系统抽取结果")
    use_llm_judge: bool = Field(
        default=False,
        description="是否启用 LLM judge 进行多维度评分",
    )
    judge_prompt_version: str | None = Field(
        default=None,
        description="Judge prompt 版本号 (v1/v2)，默认使用 active 版本",
    )


class PairwiseRequest(BaseModel):
    """两两对比请求（无 golden，A/B 测试场景）。"""

    output_a: dict[str, Any] = Field(..., description="A 版本抽取结果")
    output_b: dict[str, Any] = Field(..., description="B 版本抽取结果")


class BatchJudgeRequest(BaseModel):
    """批量评估请求：JSONL 文件路径。"""

    golden_file: str = Field(..., description="Golden set JSONL 文件路径")
    system_file: str = Field(..., description="System 输出 JSONL 文件路径")
    use_llm_judge: bool = False
    judge_prompt_version: str | None = None
    threshold: float = Field(default=0.90, ge=0.0, le=1.0, description="质量门禁阈值")


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class JudgeSampleResponse(BaseModel):
    sample_id: str = ""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    llm_score: float | None = None
    llm_reasoning: str | None = None
    errors: list[str] = []
    evaluated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class PairwiseResponse(BaseModel):
    sample_id: str = ""
    precision_b_vs_a: float = 0.0
    recall_b_vs_a: float = 0.0
    f1_b_vs_a: float = 0.0
    errors: list[str] = []
    evaluated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class BatchJudgeResponse(BaseModel):
    total_samples: int = 0
    evaluated_samples: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    weighted_score: float = 0.0
    f1_distribution: dict[str, int] = {}
    quality_gate: dict[str, Any] | None = None
    per_sample: list[dict[str, Any]] = []
    judge_prompt_version: str | None = None


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.post("/evaluate", response_model=JudgeSampleResponse)
async def evaluate_sample(req: JudgeRequest):
    """§7.2 单样本评估：golden vs system，计算 F1 并可启用 LLM judge。"""
    try:
        result = await evaluate_sample_async(
            golden=req.golden,
            system=req.system_output,
            use_llm_judge=req.use_llm_judge,
            judge_version=req.judge_prompt_version,
        )
        return JudgeSampleResponse(
            sample_id=result.sample_id,
            precision=result.precision,
            recall=result.recall,
            f1=result.f1,
            llm_score=result.llm_score,
            llm_reasoning=result.llm_reasoning,
            errors=result.errors,
        )
    except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e


@router.post("/pairwise", response_model=PairwiseResponse)
async def pairwise_compare(req: PairwiseRequest):
    """两两对比：无 golden 参考，直接比较 output_b 相对 output_a 的 F1。"""
    try:
        result = await evaluate_pair_async(
            output_a=req.output_a, output_b=req.output_b,
        )
        return PairwiseResponse(
            sample_id=result.sample_id,
            precision_b_vs_a=result.precision,
            recall_b_vs_a=result.recall,
            f1_b_vs_a=result.f1,
            errors=result.errors,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pairwise comparison failed: {e}") from e


@router.post("/batch", response_model=BatchJudgeResponse)
async def batch_evaluate(req: BatchJudgeRequest):
    """批量评估：读取 golden/system JSONL 文件，返回汇总指标和质检门禁。"""
    try:
        metrics = await evaluate_batch_async(
            golden_file=req.golden_file,
            system_file=req.system_file,
            use_llm_judge=req.use_llm_judge,
            judge_version=req.judge_prompt_version,
            threshold=req.threshold,
        )
        return BatchJudgeResponse(
            total_samples=metrics.total_samples,
            evaluated_samples=metrics.evaluated_samples,
            avg_precision=metrics.avg_precision,
            avg_recall=metrics.avg_recall,
            avg_f1=metrics.avg_f1,
            weighted_score=metrics.weighted_score,
            f1_distribution=metrics.f1_distribution,
            quality_gate=metrics.quality_gate,
            per_sample=[e.model_dump() for e in metrics.per_sample],
            judge_prompt_version=metrics.judge_prompt_version,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch evaluation failed: {e}") from e
