import json
import os

from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class SampleEvaluation(BaseModel):
    sample_id: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    llm_score: Optional[float] = None
    llm_reasoning: Optional[str] = None
    errors: list[str] = Field(default_factory=list)


class ExtractionMetrics(BaseModel):
    total_samples: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    weighted_score: float = 0.0
    f1_distribution: dict[str, int] = Field(default_factory=lambda: {"excellent": 0, "good": 0, "fair": 0, "poor": 0})
    per_sample: list[SampleEvaluation] = Field(default_factory=list)


def compute_skill_f1(golden_skills: list[str], system_skills: list[str]) -> tuple[float, float, float]:
    golden_set = set(s.strip().lower() for s in golden_skills if s.strip())
    system_set = set(s.strip().lower() for s in system_skills if s.strip())

    if not golden_set and not system_set:
        return 1.0, 1.0, 1.0
    if not golden_set or not system_set:
        return 0.0, 0.0, 0.0

    true_positives = len(golden_set & system_set)
    precision = true_positives / len(system_set)
    recall = true_positives / len(golden_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def evaluate_single_sample(golden: dict, system: dict, use_llm_judge: bool = False) -> SampleEvaluation:
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
        eval_result.llm_score = round(f1, 4)
        eval_result.llm_reasoning = "LLM judge not yet implemented, using F1 as proxy"

    return eval_result


def evaluate_batch(golden_file: str, system_file: str, output_file: Optional[str] = None) -> ExtractionMetrics:
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
        eval_result = evaluate_single_sample(golden, system)
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
        "## F1 Distribution",
        f"- Excellent (>= 0.90): {metrics.f1_distribution['excellent']}",
        f"- Good (>= 0.70): {metrics.f1_distribution['good']}",
        f"- Fair (>= 0.50): {metrics.f1_distribution['fair']}",
        f"- Poor (< 0.50): {metrics.f1_distribution['poor']}",
        "",
        "## Per-Sample Breakdown",
        "| ID | Precision | Recall | F1 | Errors |",
        "|----|-----------|--------|----|--------|",
    ]
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
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data
