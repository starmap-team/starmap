"""Resume extraction evaluation module.

Provides F1/precision/recall evaluation against a golden set of resumes.
Follows the same patterns as jd_extract.py for consistency.

Pipeline:
    build_golden_set() -> load golden samples
    evaluate_f1(predictions, golden) -> precision/recall/F1 metrics
    run_resume_evaluation() -> full evaluation pipeline against golden set

Usage:
    from app.core.extraction.resume_eval import build_golden_set, evaluate_f1, run_resume_evaluation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Golden set path (relative to project root)
_GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "resume_golden_set.json"


@dataclass
class GoldenSample:
    """A single golden-set sample for resume evaluation."""

    resume_text: str
    expected_skills: list[dict[str, Any]]
    position: str
    sample_id: str = ""

    @property
    def expected_skill_names(self) -> set[str]:
        """Return normalized lowercase set of expected skill names."""
        return {s["name"].strip().lower() for s in self.expected_skills if s.get("name")}


@dataclass
class F1Metrics:
    """F1 evaluation result."""

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    total_predicted: int = 0
    total_expected: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_predicted": self.total_predicted,
            "total_expected": self.total_expected,
        }


@dataclass
class EvaluationResult:
    """Aggregated evaluation result across multiple samples."""

    total_samples: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_f1: float = 0.0
    macro_f1: float = 0.0
    per_sample: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "avg_precision": round(self.avg_precision, 4),
            "avg_recall": round(self.avg_recall, 4),
            "avg_f1": round(self.avg_f1, 4),
            "macro_f1": round(self.macro_f1, 4),
            "per_sample": self.per_sample,
            "summary": self.summary,
        }


def _normalize_skill_name(name: str) -> str:
    """Normalize a skill name for comparison (lowercase, strip whitespace)."""
    return name.strip().lower()


def _skill_matches(predicted: str, expected: set[str]) -> bool:
    """Check if a predicted skill matches any expected skill.

    Uses substring and alias matching for fuzzy comparison:
    - Exact match (after normalization)
    - Substring containment (e.g., "react" matches "react.js")
    """
    pred_norm = _normalize_skill_name(predicted)
    if pred_norm in expected:
        return True
    # Substring matching: predicted contained in expected or vice versa
    for exp in expected:
        if pred_norm in exp or exp in pred_norm:
            return True
    return False


def build_golden_set(path: str | Path | None = None) -> list[GoldenSample]:
    """Load the resume golden set from JSON file.

    Args:
        path: Path to the golden set JSON file. Defaults to data/resume_golden_set.json.

    Returns:
        List of GoldenSample objects.
    """
    file_path = Path(path) if path else _GOLDEN_SET_PATH
    if not file_path.exists():
        logger.warning("Golden set file not found: {}", file_path)
        return []

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    samples: list[GoldenSample] = []
    for i, entry in enumerate(data):
        samples.append(GoldenSample(
            resume_text=entry.get("resume_text", ""),
            expected_skills=entry.get("expected_skills", []),
            position=entry.get("position", ""),
            sample_id=entry.get("id", f"sample_{i:03d}"),
        ))

    logger.info("Loaded {} golden samples from {}", len(samples), file_path)
    return samples


def evaluate_f1(
    predictions: list[set[str]],
    golden: list[GoldenSample],
) -> dict[str, Any]:
    """Evaluate F1 score for resume skill extraction predictions against golden set.

    Args:
        predictions: List of sets of predicted skill names (one set per golden sample).
        golden: List of GoldenSample objects with expected skills.

    Returns:
        Dict with aggregate precision, recall, f1 and per-sample breakdowns.
    """
    if len(predictions) != len(golden):
        raise ValueError(
            f"Prediction count ({len(predictions)}) != golden count ({len(golden)})"
        )

    per_sample_metrics: list[dict[str, Any]] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    f1_values: list[float] = []

    for i, (pred_set, sample) in enumerate(zip(predictions, golden)):
        expected = sample.expected_skill_names

        # True positives: predicted skills that match expected
        tp = sum(1 for p in pred_set if _skill_matches(p, expected))
        # False positives: predicted skills that don't match any expected
        fp = len(pred_set) - tp
        # False negatives: expected skills not matched by any prediction
        matched_expected: set[str] = set()
        for p in pred_set:
            for e in expected:
                if _skill_matches(p, {e}):
                    matched_expected.add(e)
        fn = len(expected - matched_expected)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        total_tp += tp
        total_fp += fp
        total_fn += fn
        f1_values.append(f1)

        per_sample_metrics.append({
            "sample_id": sample.sample_id,
            "position": sample.position,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "predicted_count": len(pred_set),
            "expected_count": len(expected),
        })

    # Micro-averaged metrics
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall) > 0
        else 0.0
    )

    # Macro-averaged F1
    macro_f1 = sum(f1_values) / len(f1_values) if f1_values else 0.0

    return {
        "precision": round(micro_precision, 4),
        "recall": round(micro_recall, 4),
        "f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "total_samples": len(golden),
        "per_sample": per_sample_metrics,
    }


def evaluate_single(
    predicted_skills: list[str] | list[dict[str, Any]],
    expected_skills: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate a single extraction result against expected skills.

    Args:
        predicted_skills: List of predicted skill names or dicts with 'name' key.
        expected_skills: List of expected skill dicts with 'name' and 'proficiency'.

    Returns:
        Dict with precision, recall, f1 for this single sample.
    """
    # Normalize predictions to name set
    pred_names: set[str] = set()
    for s in predicted_skills:
        if isinstance(s, dict):
            name = s.get("name") or s.get("skill") or ""
        else:
            name = str(s)
        if name:
            pred_names.add(name)

    golden = GoldenSample(
        resume_text="",
        expected_skills=expected_skills,
        position="",
    )
    result = evaluate_f1([pred_names], [golden])
    if result["per_sample"]:
        return result["per_sample"][0]
    return {"precision": 0.0, "recall": 0.0, "f1": 0.0}


async def run_resume_evaluation(
    golden_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run full resume extraction evaluation against the golden set.

    Loads golden samples, runs extraction pipeline on each, and computes F1 metrics.

    Args:
        golden_path: Optional path to golden set JSON.

    Returns:
        Complete evaluation result dict.
    """
    from app.core.extraction.jd_extract import extract_from_jd

    samples = build_golden_set(golden_path)
    if not samples:
        return {
            "success": False,
            "error": "No golden samples found",
            "metrics": {},
        }

    predictions: list[set[str]] = []
    extraction_errors: list[dict[str, Any]] = []

    for i, sample in enumerate(samples):
        try:
            result = await extract_from_jd(sample.resume_text, options={"source": "resume"})
            if result.get("success") and result.get("data"):
                data = result["data"]
                pred_skills = set()
                for s in data.get("required_skills", []):
                    name = s.get("name", "") if isinstance(s, dict) else str(s)
                    if name:
                        pred_skills.add(name)
                for s in data.get("preferred_skills", []):
                    name = s.get("name", "") if isinstance(s, dict) else str(s)
                    if name:
                        pred_skills.add(name)
                predictions.append(pred_skills)
            else:
                predictions.append(set())
                extraction_errors.append({
                    "sample_id": sample.sample_id,
                    "error": result.get("error", "Unknown error"),
                })
        except Exception as e:
            logger.warning("Extraction failed for sample {}: {}", sample.sample_id, e)
            predictions.append(set())
            extraction_errors.append({
                "sample_id": sample.sample_id,
                "error": str(e),
            })

        if (i + 1) % 10 == 0:
            logger.info("Resume evaluation progress: {}/{}", i + 1, len(samples))

    metrics = evaluate_f1(predictions, samples)

    # Summary statistics
    positions_seen: dict[str, int] = {}
    for s in samples:
        positions_seen[s.position] = positions_seen.get(s.position, 0) + 1

    metrics["summary"] = {
        "positions_evaluated": positions_seen,
        "extraction_errors": len(extraction_errors),
        "errors": extraction_errors[:10],  # First 10 errors for debugging
    }

    logger.info(
        "Resume evaluation complete: {} samples, F1={:.4f}, precision={:.4f}, recall={:.4f}",
        metrics["total_samples"], metrics["f1"], metrics["precision"], metrics["recall"],
    )

    return {
        "success": True,
        "metrics": metrics,
    }
