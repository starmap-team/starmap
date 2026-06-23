"""LLM-as-judge 服务层（§7.2 第四环）。

异步包装 evaluation.judge_eval 的核心逻辑，供 FastAPI 端点调用；
同时支持两两对比（A/B 测试场景）和批量评测。

调用链路:
    JudgeService._run_judge(raw_jd, system_output)
      → prompt.get_prompt("llm_judge", v1/v2)
      → llm_client.call_llm_with_fallback()
      → parse_llm_json_response()
      → 返回多维度评分
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

# 技能归一化（可选，导入失败时退化为基础匹配）
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    from app.core.extraction.normalize import normalize_by_alias
    _HAS_NORMALIZE = True
except Exception:
    _HAS_NORMALIZE = False

from app.core.extraction.llm_client import (
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    call_llm_with_fallback,
    parse_llm_json_response,
)
from app.core.extraction.prompt import get_prompt, get_prompt_version


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


class SampleEvaluation(BaseModel):
    """单条样本的评估结果。"""

    sample_id: str = ""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    llm_score: Optional[float] = None
    llm_reasoning: Optional[str] = None
    errors: list[str] = Field(default_factory=list)


class ExtractionMetrics(BaseModel):
    """批量评估的汇总指标。"""

    total_samples: int = 0
    evaluated_samples: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    weighted_score: float = 0.0
    f1_distribution: dict[str, int] = Field(
        default_factory=lambda: {"excellent": 0, "good": 0, "fair": 0, "poor": 0},
    )
    per_sample: list[SampleEvaluation] = Field(default_factory=list)
    quality_gate: Optional[dict[str, Any]] = None
    judge_prompt_version: Optional[str] = None


# ──────────────────────────────────────────────
# 内部辅助函数
# ──────────────────────────────────────────────


def _normalize_skill(skill: str) -> str:
    """对技能名称做归一化，用于公平比对。"""
    import re as _re

    s = (skill or "").strip()
    if not s:
        return ""
    if _HAS_NORMALIZE:
        norm = normalize_by_alias(s)
        if norm:
            return norm.lower()
    return _re.sub(r"[^a-z0-9+#.]", "", s.lower())


def _skill_names(items: list[Any]) -> list[str]:
    """从技能列表中提取名称（兼容 str / dict 两种格式）。"""
    result: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            result.append(str(item.get("name", "")))
        else:
            result.append(str(item))
    return result


def _build_judge_prompt(
    golden: dict[str, Any],
    system: dict[str, Any],
    version: str | None = None,
) -> str:
    """构造 LLM judge 提示词（注入 golden / system JSON）。"""
    golden_json = json.dumps(golden, ensure_ascii=False, indent=2)
    system_json = json.dumps(system, ensure_ascii=False, indent=2)
    if version:
        try:
            return get_prompt_version(
                "llm_judge", version,
                golden_json=golden_json, system_json=system_json,
            )
        except KeyError:
            logger.warning("Judge prompt version '{}' not found, falling back", version)
    return get_prompt("llm_judge", golden_json=golden_json, system_json=system_json)


async def _call_llm_judge_async(
    golden: dict[str, Any],
    system: dict[str, Any],
    version: str | None = None,
) -> tuple[float | None, str | None]:
    """异步调用 LLM judge，返回 (score, reasoning)。"""
    prompt = _build_judge_prompt(golden, system, version)
    raw = await call_llm_with_fallback(prompt)
    content = raw.get("content", "") if isinstance(raw, dict) else str(raw)
    try:
        result = parse_llm_json_response(content)
    except LLMResponseError:
        return None, f"Failed to parse LLM response: {content[:200]}"
    if not isinstance(result, dict):
        return None, f"LLM returned non-dict: {content[:200]}"
    score = result.get("f1_score") or result.get("accuracy") or result.get("precision")
    reasoning = result.get("details") or result.get("reasoning") or ""
    return (float(score) if score is not None else None, str(reasoning))


def _load_jsonl(filepath: str | Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件，忽略空行和非法 JSON。"""
    path = Path(filepath)
    if not path.exists():
        logger.warning("JSONL file not found: {}", path)
        return []
    data: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON at {}:{}: {}", path.name, lineno, exc)
    return data


def _check_quality_gate(metrics: "ExtractionMetrics", threshold: float) -> dict[str, Any]:
    """检查整体指标是否通过质量门禁。"""
    passed = metrics.avg_f1 >= threshold
    return {
        "passed": passed,
        "avg_f1": round(metrics.avg_f1, 4),
        "threshold": threshold,
        "status": "green" if passed else "red",
        "message": (
            f"Quality gate {'passed' if passed else 'failed'}: "
            f"F1 {metrics.avg_f1:.4f} {'≥' if passed else '<'} {threshold}"
        ),
    }


# ──────────────────────────────────────────────
# 核心异步 API
# ──────────────────────────────────────────────


async def evaluate_sample_async(
    golden: dict[str, Any],
    system: dict[str, Any],
    use_llm_judge: bool = False,
    judge_version: str | None = None,
) -> SampleEvaluation:
    """评估单条系统输出 vs 标准答案（Golden）。"""
    sid = golden.get("id") or system.get("id") or "unknown"

    golden_required = golden.get("required_skills") or []
    golden_bonus = golden.get("bonus_skills") or []
    system_required = system.get("required_skills") or []
    system_bonus = system.get("bonus_skills") or []

    golden_req_set = {_normalize_skill(s) for s in _skill_names(golden_required)} - {""}
    golden_bon_set = {_normalize_skill(s) for s in _skill_names(golden_bonus)} - {""}
    system_req_set = {_normalize_skill(s) for s in _skill_names(system_required)} - {""}
    system_bon_set = {_normalize_skill(s) for s in _skill_names(system_bonus)} - {""}

    def _f1(gs: set[str], ss: set[str]) -> tuple[float, float, float]:
        if not gs and not ss:
            return 1.0, 1.0, 1.0
        if not gs or not ss:
            return 0.0, 0.0, 0.0
        tp = len(gs & ss)
        p = tp / len(ss) if ss else 0.0
        r = tp / len(gs) if gs else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    p_req, r_req, f1_req = _f1(golden_req_set, system_req_set)
    p_bon, r_bon, f1_bon = _f1(golden_bon_set, system_bon_set)

    total = len(golden_required) + len(golden_bonus)
    if total > 0:
        w_req = len(golden_required) / total
        w_bon = len(golden_bonus) / total
        precision = p_req * w_req + p_bon * w_bon
        recall = r_req * w_req + r_bon * w_bon
        f1 = f1_req * w_req + f1_bon * w_bon
    else:
        precision = recall = f1 = 0.0

    errors: list[str] = []
    if golden_required and not system_required:
        errors.append("missing required_skills field")
    if golden_bonus and not system_bonus:
        errors.append("missing bonus_skills field")

    eval_result = SampleEvaluation(
        sample_id=sid,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        errors=errors,
    )

    if use_llm_judge:
        llm_score, llm_reasoning = await _call_llm_judge_async(golden, system, judge_version)
        eval_result.llm_score = llm_score
        eval_result.llm_reasoning = llm_reasoning

    return eval_result


async def evaluate_pair_async(
    output_a: dict[str, Any],
    output_b: dict[str, Any],
) -> SampleEvaluation:
    """无 Golden 参考时，对比两份抽取结果（A/B 场景）。

    以 output_a 为基准，计算 output_b 相对 output_a 的 precision / recall / F1。
    """
    sid = output_b.get("id") or output_a.get("id") or "unknown"
    return await evaluate_sample_async(output_a, output_b, use_llm_judge=False)


async def evaluate_batch_async(
    golden_file: str | Path,
    system_file: str | Path,
    use_llm_judge: bool = False,
    judge_version: str | None = None,
    threshold: float = 0.90,
) -> ExtractionMetrics:
    """批量评估 system 输出 vs golden 标准。"""
    golden_data = _load_jsonl(golden_file)
    system_data = _load_jsonl(system_file)
    system_map: dict[str, dict[str, Any]] = {
        s.get("id", ""): s for s in system_data if s.get("id")
    }

    evaluations: list[SampleEvaluation] = []
    for golden in golden_data:
        sid = golden.get("id", "")
        system = system_map.get(sid, {})
        if not system:
            logger.debug("No system output for sample '{}', treating as empty", sid)
        eval_result = await evaluate_sample_async(
            golden, system,
            use_llm_judge=use_llm_judge,
            judge_version=judge_version,
        )
        evaluations.append(eval_result)

    if not evaluations:
        return ExtractionMetrics(judge_prompt_version=judge_version)

    total_p = sum(e.precision for e in evaluations)
    total_r = sum(e.recall for e in evaluations)
    total_f = sum(e.f1 for e in evaluations)
    n = len(evaluations)

    dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for e in evaluations:
        if e.f1 >= 0.90:
            dist["excellent"] += 1
        elif e.f1 >= 0.70:
            dist["good"] += 1
        elif e.f1 >= 0.50:
            dist["fair"] += 1
        else:
            dist["poor"] += 1

    avg_p = total_p / n
    avg_r = total_r / n
    avg_f = total_f / n

    weights = {"excellent": 1.0, "good": 0.75, "fair": 0.5, "poor": 0.0}
    weighted = sum(dist[k] * weights[k] for k in weights) / max(n, 1)

    metrics = ExtractionMetrics(
        total_samples=len(golden_data),
        evaluated_samples=n,
        avg_precision=round(avg_p, 4),
        avg_recall=round(avg_r, 4),
        avg_f1=round(avg_f, 4),
        weighted_score=round(weighted, 4),
        f1_distribution=dist,
        per_sample=evaluations,
        judge_prompt_version=judge_version,
    )
    metrics.quality_gate = _check_quality_gate(metrics, threshold)
    return metrics
