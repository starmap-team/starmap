"""Judge API: §7.2 LLM-as-judge 评估端点。

提供单样本评估、两两对比和批量评测三个接口，
作为流 D (QA) 的自动化评估基础。
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.exceptions import JudgeError, StarMapError
from app.schemas.judge import (
    BatchJudgeRequest,
    BatchJudgeResponse,
    JudgeRequest,
    JudgeSampleResponse,
    PairwiseRequest,
    PairwiseResponse,
)
from app.services.judge_service import (
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    evaluate_batch_async,
    evaluate_pair_async,
    evaluate_sample_async,
)

router = APIRouter(prefix="/judge")


# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────



# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.post("/evaluate", response_model=JudgeSampleResponse)
async def evaluate_sample(req: JudgeRequest) -> Any:
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
        logger.error("LLM service error in judge: {}", e)
        raise HTTPException(status_code=502, detail="LLM service temporarily unavailable") from e
    except JudgeError as exc:
        logger.exception("Judge operation failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in judge: {}", exc)
        raise HTTPException(status_code=500, detail="评估处理异常") from exc


@router.post("/pairwise", response_model=PairwiseResponse)
async def pairwise_compare(req: PairwiseRequest) -> Any:
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
    except JudgeError as exc:
        logger.exception("Judge operation failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in judge: {}", exc)
        raise HTTPException(status_code=500, detail="评估处理异常") from exc


@router.post("/batch", response_model=BatchJudgeResponse)
async def batch_evaluate(req: BatchJudgeRequest) -> Any:
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
        logger.warning("File not found in batch judge: {}", e)
        raise HTTPException(status_code=404, detail="Requested evaluation file not found") from e
    except JudgeError as exc:
        logger.exception("Judge operation failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in judge: {}", exc)
        raise HTTPException(status_code=500, detail="评估处理异常") from exc
