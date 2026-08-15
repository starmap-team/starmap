import asyncio
import json
import random
import re
import sys
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

# Import normalize module for skill alias resolution
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.core.extraction.normalize import normalize_by_alias
    _HAS_NORMALIZE = True
except Exception:
    _HAS_NORMALIZE = False
    logger.warning("normalize module not available, using basic matching only")

# Import LLM client for judge evaluation
try:
    from app.core.extraction.llm_client import (
        call_llm_with_fallback,
        parse_llm_json_response,
    )
    from app.core.extraction.prompt import get_prompt
    _HAS_LLM = True
except Exception:
    _HAS_LLM = False
    logger.warning("LLM client not available for judge evaluation: {}")


def _normalize_skill_for_eval(skill: str) -> str:
    """Normalize a skill name for fair comparison.

    Tries alias-based normalization first, then falls back to basic
    case/dash/space normalization.
    """
    s = skill.strip()
    if not s:
        return ""
    # Step 1: alias normalization (Kafka <-> Apache Kafka etc.)
    if _HAS_NORMALIZE:
        norm = normalize_by_alias(s)
        if norm is not None:
            return norm.lower()
    # Step 2: basic normalization (remove non-alphanumeric, lowercase)
    return re.sub(r'[^a-z0-9+#.]', '', s.lower())


class SampleEvaluation(BaseModel):
    sample_id: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    llm_score: float | None = None
    llm_reasoning: str | None = None
    errors: list[str] = Field(default_factory=list)


class ExtractionMetrics(BaseModel):
    total_samples: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    weighted_score: float = 0.0
    f1_distribution: dict[str, int] = Field(default_factory=lambda: {"excellent": 0, "good": 0, "fair": 0, "poor": 0})
    per_sample: list[SampleEvaluation] = Field(default_factory=list)
    # 95% bootstrap CI（n=1000 重采样，纯 stdlib，无依赖）。ALIGN-08：§14.5 置信区间报告落地。
    # 缺失时表示样本数 < 2 或不启用。
    ci_95: dict[str, dict[str, float]] | None = None


def bootstrap_ci_95(
    values: list[float],
    n_resamples: int = 1000,
    seed: int = 42,
) -> dict[str, float] | None:
    """Compute bootstrap 95% confidence interval using percentile method.

    Pure stdlib (random.seed + choices); no external stats dependency.
    Returns {"lower": q025, "upper": q975, "mean": ..., "n": ...} or None
    when input has fewer than 2 non-NaN values.

    Per docs/星图-项目设计文档v2.0.md §14.5 (ALIGN-08 落地)。
    """
    clean = [v for v in values if v is not None and not (isinstance(v, float) and v != v)]
    if len(clean) < 2:
        return None
    rng = random.Random(seed)
    n = len(clean)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [clean[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return {
        "lower": round(means[int(0.025 * n_resamples)], 4),
        "upper": round(means[int(0.975 * n_resamples)], 4),
        "mean": round(sum(clean) / n, 4),
        "n": n,
        "n_resamples": n_resamples,
    }


def compute_skill_f1(golden_skills: list[str], system_skills: list[str]) -> tuple[float, float, float]:
    # Normalize both sides through alias + basic normalization for fair comparison
    golden_set = {_normalize_skill_for_eval(s) for s in golden_skills if s.strip()}
    system_set = {_normalize_skill_for_eval(s) for s in system_skills if s.strip()}

    # Remove empty strings that may result from normalization
    golden_set.discard("")
    system_set.discard("")

    if not golden_set and not system_set:
        return 1.0, 1.0, 1.0
    if not golden_set or not system_set:
        return 0.0, 0.0, 0.0

    true_positives = len(golden_set & system_set)
    precision = true_positives / len(system_set)
    recall = true_positives / len(golden_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


async def _call_llm_judge(golden: dict, system: dict) -> tuple[float | None, str | None]:
    """Call LLM-as-judge to evaluate extraction quality.

    Uses the llm_judge prompt from prompt.py and call_llm_with_fallback
    to obtain multi-dimensional quality scores from the LLM.

    Returns:
        Tuple of (score, reasoning). score is f1_score or overall accuracy from LLM.
        Returns (None, error_message) on failure.
    """
    if not _HAS_LLM:
        return None, "LLM client not available"

    try:
        golden_json = json.dumps(golden, ensure_ascii=False, indent=2)
        system_json = json.dumps(system, ensure_ascii=False, indent=2)
        prompt = get_prompt("llm_judge", golden_json=golden_json, system_json=system_json)
        response = await asyncio.wait_for(call_llm_with_fallback(prompt), timeout=10.0)
        content = response.get("content", "") if isinstance(response, dict) else str(response)
        result = parse_llm_json_response(content)
    except TimeoutError:
        return None, "LLM judge timed out after 10s"
    except Exception as exc:
        return None, f"LLM judge call failed: {exc}"

    if not isinstance(result, dict):
        return None, f"LLM returned non-dict result: {str(result)[:200]}"

    score = result.get("f1_score") or result.get("accuracy") or result.get("precision")
    reasoning = result.get("details") or result.get("reasoning") or ""
    return (float(score) if score is not None else None), str(reasoning)


async def evaluate_single_sample(golden: dict, system: dict, use_llm_judge: bool = False) -> SampleEvaluation:
    """Evaluate a single system output against golden standard.

    Supports two modes:
      - use_llm_judge=False (default): Compute F1 from skill name overlap.
      - use_llm_judge=True: Also call LLM judge for multi-dimensional scoring.
        # ponytail: feature flag — LLM judge is optional; _HAS_LLM guard handles unavailability

    Args:
        golden: Golden standard dict.
        system: System output dict.
        use_llm_judge: Whether to also call the LLM judge.

    Returns:
        SampleEvaluation with F1 metrics and optional LLM scores.
    """
    sid = golden.get("id", system.get("id", "unknown"))

    golden_required = golden.get("required_skills", [])
    golden_bonus = golden.get("bonus_skills", [])
    system_required = system.get("required_skills", [])
    system_bonus = system.get("bonus_skills", [])

    p_req, r_req, f1_req = compute_skill_f1(golden_required, system_required)
    p_bon, r_bon, f1_bon = compute_skill_f1(golden_bonus, system_bonus)

    if golden_required or golden_bonus:
        precision = (p_req * len(golden_required) + p_bon * len(golden_bonus)) / (len(golden_required) + len(golden_bonus))
        recall = (r_req * len(golden_required) + r_bon * len(golden_bonus)) / (len(golden_required) + len(golden_bonus))
        f1 = (f1_req * len(golden_required) + f1_bon * len(golden_bonus)) / (len(golden_required) + len(golden_bonus))
    else:
        precision = recall = f1 = 0.0

    eval_result = SampleEvaluation(
        sample_id=sid,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )

    errors = []
    if golden_required and not system_required:
        errors.append("missing required_skills field")
    if golden_bonus and not system_bonus:
        errors.append("missing bonus_skills field")
    eval_result.errors = errors

    if use_llm_judge:
        llm_score, llm_reasoning = await _call_llm_judge(golden, system)
        eval_result.llm_score = llm_score
        eval_result.llm_reasoning = llm_reasoning
        if llm_score is None:
            logger.info("LLM judge unavailable for sample {}, using F1 only", sid)

    return eval_result


async def evaluate_batch(golden_file: str, system_file: str, output_file: str | None = None, use_llm_judge: bool = False) -> ExtractionMetrics:
    """Evaluate system output against golden standard in batch.

    Args:
        golden_file: Path to golden JSONL file.
        system_file: Path to system output JSONL file.
        output_file: Optional output path for the metrics JSON.
        use_llm_judge: Whether to use LLM judge for evaluation.

    Returns:
        ExtractionMetrics with aggregate scores.
    """
    golden_data = _load_jsonl(golden_file)
    system_data = _load_jsonl(system_file)
    system_map = {s.get("id", s.get("job_title", "")): s for s in system_data}

    evaluations: list[SampleEvaluation] = []
    for golden in golden_data:
        sid = golden.get("id", "")
        system = system_map.get(sid, {})
        if not system:
            logger.warning(f"No system output for sample {sid}, treating as empty")
            system = {}
        eval_result = await evaluate_single_sample(golden, system, use_llm_judge=use_llm_judge)
        evaluations.append(eval_result)

    if not evaluations:
        return ExtractionMetrics()

    avg_p = sum(e.precision for e in evaluations) / len(evaluations)
    avg_r = sum(e.recall for e in evaluations) / len(evaluations)
    avg_f = sum(e.f1 for e in evaluations) / len(evaluations)

    f1_dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for e in evaluations:
        if e.f1 >= 0.9:
            f1_dist["excellent"] += 1
        elif e.f1 >= 0.7:
            f1_dist["good"] += 1
        elif e.f1 >= 0.5:
            f1_dist["fair"] += 1
        else:
            f1_dist["poor"] += 1

    metrics = ExtractionMetrics(
        total_samples=len(evaluations),
        avg_precision=round(avg_p, 4),
        avg_recall=round(avg_r, 4),
        avg_f1=round(avg_f, 4),
        f1_distribution=f1_dist,
        per_sample=evaluations,
    )
    metrics.weighted_score = compute_weighted_score(metrics)

    # ALIGN-08: §14.5 bootstrap 95% CI（per-sample 重采样，1000 次）
    f1_values = [e.f1 for e in evaluations]
    p_values = [e.precision for e in evaluations]
    r_values = [e.recall for e in evaluations]
    metrics.ci_95 = {
        "f1": bootstrap_ci_95(f1_values) or {},
        "precision": bootstrap_ci_95(p_values) or {},
        "recall": bootstrap_ci_95(r_values) or {},
    }

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(metrics.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Evaluation results saved to {output_file}")

    return metrics


def generate_evaluation_report(metrics: ExtractionMetrics, output_dir: str) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    md = [
        "# StarMap Extraction Evaluation Report",
        "",
        f"- **Total Samples**: {metrics.total_samples}",
        f"- **Avg Precision**: {metrics.avg_precision:.4f}",
        f"- **Avg Recall**: {metrics.avg_recall:.4f}",
        f"- **Avg F1**: {metrics.avg_f1:.4f}",
        f"- **Weighted Score**: {metrics.weighted_score:.4f}",
        "",
    ]

    # ALIGN-08 §14.5 置信区间报告（bootstrap 1000 次 95% CI）
    if metrics.ci_95:
        md.append("## 95% Bootstrap CI (ALIGN-08, §14.5)\n")
        md.append("| 指标 | 下限 | 均值 | 上限 | 样本 |")
        md.append("|------|------|------|------|------|")
        for label, key in (("F1", "f1"), ("Precision", "precision"), ("Recall", "recall")):
            ci = metrics.ci_95.get(key) or {}
            if ci:
                md.append(
                    f"| {label} | {ci.get('lower', 0):.4f} | "
                    f"{ci.get('mean', 0):.4f} | {ci.get('upper', 0):.4f} | "
                    f"{ci.get('n', 0)} |"
                )
        md.append("")
        # 格式：`JD解析 F1 = 92.3% [90.1%, 94.3%]`
        ci_f1 = metrics.ci_95.get("f1") or {}
        if ci_f1:
            md.append(
                f"**报告格式**：`JD解析 F1 = {metrics.avg_f1:.4f} "
                f"[{ci_f1.get('lower', 0):.4f}, {ci_f1.get('upper', 0):.4f}]`\n"
            )

    md.extend([
        "## F1 Distribution",
        f"- Excellent (>= 0.90): {metrics.f1_distribution['excellent']}",
        f"- Good (>= 0.70): {metrics.f1_distribution['good']}",
        f"- Fair (>= 0.50): {metrics.f1_distribution['fair']}",
        f"- Poor (< 0.50): {metrics.f1_distribution['poor']}",
        "",
        "## Per-Sample Breakdown",
        "| ID | Precision | Recall | F1 | Errors |",
        "|----|-----------|--------|----|--------|",
    ])
    for e in metrics.per_sample:
        errors = "; ".join(e.errors) if e.errors else "-"
        md.append(f"| {e.sample_id} | {e.precision:.4f} | {e.recall:.4f} | {e.f1:.4f} | {errors} |")

    md_path = out / "evaluation_report.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    quality = check_quality_gate(metrics)
    json_path = out / "quality_gate.json"
    json_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {"report_path": str(md_path), "quality_gate": quality}
    logger.info(f"Report generated at {md_path}")
    return report


def compute_weighted_score(metrics: ExtractionMetrics) -> float:
    if not metrics.total_samples:
        return 0.0
    weights = {"excellent": 1.0, "good": 0.75, "fair": 0.5, "poor": 0.0}
    total = sum(metrics.f1_distribution.values())
    if total == 0:
        return 0.0
    score = sum(metrics.f1_distribution[k] * weights[k] for k in weights)
    return round(score / total, 4)


def check_quality_gate(metrics: ExtractionMetrics) -> dict:
    passed = metrics.avg_f1 >= 0.90
    return {
        "passed": passed,
        "avg_f1": round(metrics.avg_f1, 4),
        "threshold": 0.90,
        "status": "green" if passed else "red",
        "message": "Quality gate passed" if passed else f"Quality gate failed: F1 {metrics.avg_f1:.4f} < 0.90",
    }


def _load_jsonl(filepath: str) -> list[dict]:
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"File not found: {filepath}, returning empty list")
        return []
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


if __name__ == "__main__":
    # Self-check: verify F1 fallback works when LLM unavailable
    async def _self_check() -> None:
        golden = {"id": "test-1", "required_skills": ["Python", "FastAPI"], "bonus_skills": ["Docker"]}
        system = {"id": "test-1", "required_skills": ["Python", "FastAPI", "Redis"], "bonus_skills": ["Docker"]}
        result = await evaluate_single_sample(golden, system, use_llm_judge=True)
        assert result.f1 > 0, f"F1 should be > 0, got {result.f1}"
        if result.llm_score is None:
            print(f"F1 fallback OK -- f1={result.f1:.4f}, llm_score=None (LLM unavailable)")
        else:
            print(f"LLM judge OK -- f1={result.f1:.4f}, llm_score={result.llm_score}")

    asyncio.run(_self_check())
