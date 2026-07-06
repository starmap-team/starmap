"""
StarMap Backend Quality Report — Phase 4 Data Flow Completion.

Provides three evaluation functions that integrate with the backend's
extraction and matching services to produce quality metrics:

  - measure_jd_extraction_quality(): Run JD extraction on Golden Set, compute F1
  - measure_match_accuracy(): Run matching on Match Golden Set, compute accuracy
  - measure_overall_system_health(): Aggregate all quality metrics

Usage:
    python -m scripts.quality_report [--golden DIR] [--output DIR]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Make backend importable when running as a script ──
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _load_jsonl(filepath: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL file, return list of dicts. Returns empty list if file missing."""
    path = Path(filepath)
    if not path.exists():
        return []
    data: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return data


def _normalize_name(name: str) -> str:
    """Normalize a skill/field name for comparison."""
    return re.sub(r"[^a-z0-9+#.]", "", str(name).strip().lower())


def _extract_skill_names(skills: list[Any]) -> set[str]:
    """Extract normalized name strings from a list of skill entries (str or dict)."""
    names: set[str] = set()
    for s in skills:
        if isinstance(s, dict):
            name = str(s.get("name", ""))
        else:
            name = str(s)
        normalized = _normalize_name(name)
        if normalized:
            names.add(normalized)
    return names


def _compute_f1(golden_set: set[str], system_set: set[str]) -> tuple[float, float, float]:
    """Compute precision, recall, and F1 between two sets."""
    if not golden_set and not system_set:
        return 1.0, 1.0, 1.0
    if not golden_set or not system_set:
        return 0.0, 0.0, 0.0
    tp = len(golden_set & system_set)
    precision = tp / len(system_set)
    recall = tp / len(golden_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _weighted_f1(
    g_required: list[Any],
    g_bonus: list[Any],
    s_required: list[Any],
    s_bonus: list[Any],
) -> tuple[float, float, float]:
    """Compute weighted precision/recall/F1 across required and bonus skills."""
    g_req = _extract_skill_names(g_required)
    g_bon = _extract_skill_names(g_bonus)
    s_req = _extract_skill_names(s_required)
    s_bon = _extract_skill_names(s_bonus)

    p_req, r_req, f1_req = _compute_f1(g_req, s_req)
    p_bon, r_bon, f1_bon = _compute_f1(g_bon, s_bon)

    total = len(g_required) + len(g_bonus)
    if total > 0:
        w_req = len(g_required) / total
        w_bon = len(g_bonus) / total
        precision = p_req * w_req + p_bon * w_bon
        recall = r_req * w_req + r_bon * w_bon
        f1 = f1_req * w_req + f1_bon * w_bon
    else:
        precision = recall = f1 = 0.0

    return precision, recall, f1


# ──────────────────────────────────────────────
# Task 4: measure_jd_extraction_quality
# ──────────────────────────────────────────────

async def measure_jd_extraction_quality(
    golden_dir: str | Path = "evaluation",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run JD extraction on Golden Set samples and compute F1.

    Loads the golden set from ``evaluation/golden_set.jsonl``, runs the
    extraction pipeline on each sample's ``raw_jd`` field, then compares
    the extracted skills against the golden standard.

    Returns a metric dict with precision, recall, F1, and per-sample details.
    If the golden set or extraction pipeline is unavailable, returns a clear
    message instead of a pending status.
    """
    golden_path = Path(golden_dir) / "golden_set.jsonl"
    golden_data = _load_jsonl(golden_path)

    if not golden_data:
        return {
            "metric": "JD解析准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": f"Golden set not found or empty at {golden_path}. "
                      "Run evaluation/golden_set.jsonl population first.",
        }

    # Attempt to import and use the extraction pipeline
    try:
        from app.core.extraction.jd_extract import extract_from_jd
        has_extraction = True
    except Exception:
        has_extraction = False

    if not has_extraction:
        return {
            "metric": "JD解析准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": "JD extraction pipeline not available. "
                      "Ensure backend dependencies are installed and LLM is configured.",
        }

    # Run extraction on each golden sample
    evaluations: list[dict[str, Any]] = []
    total_precision = 0.0
    total_recall = 0.0
    total_f1 = 0.0
    errors: list[str] = []

    for golden in golden_data:
        sid = golden.get("id", golden.get("job_title", "unknown"))
        raw_jd = golden.get("raw_jd", "")

        if not raw_jd:
            errors.append(f"Sample {sid}: no raw_jd field")
            evaluations.append({
                "sample_id": sid,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "error": "no raw_jd",
            })
            continue

        try:
            result = await extract_from_jd(raw_jd)
            if not result.get("success"):
                errors.append(f"Sample {sid}: extraction failed - {result.get('error', 'unknown')}")
                evaluations.append({
                    "sample_id": sid,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "error": result.get("error", "extraction_failed"),
                })
                continue

            system_data = result.get("data", {})
        except Exception as exc:
            errors.append(f"Sample {sid}: extraction exception - {exc}")
            evaluations.append({
                "sample_id": sid,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "error": str(exc),
            })
            continue

        # Compare extracted skills against golden
        g_required = golden.get("required_skills", [])
        g_bonus = golden.get("bonus_skills", [])
        s_required = system_data.get("required_skills", [])
        s_bonus = system_data.get("preferred_skills", system_data.get("bonus_skills", []))

        precision, recall, f1 = _weighted_f1(g_required, g_bonus, s_required, s_bonus)

        evaluations.append({
            "sample_id": sid,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        })
        total_precision += precision
        total_recall += recall
        total_f1 += f1

    n = len(evaluations)
    if n == 0:
        return {
            "metric": "JD解析准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": "No valid samples evaluated.",
        }

    avg_precision = round(total_precision / n, 4)
    avg_recall = round(total_recall / n, 4)
    avg_f1 = round(total_f1 / n, 4)
    passed = avg_f1 >= 0.90

    result = {
        "metric": "JD解析准确率",
        "target": ">=90%",
        "current": f"{avg_f1:.2%}",
        "status": "pass" if passed else "fail",
        "detail": (
            f"Based on {n} golden samples: avg_precision={avg_precision:.4f}, "
            f"avg_recall={avg_recall:.4f}, avg_f1={avg_f1:.4f}"
        ),
        "per_sample": evaluations,
    }

    if errors:
        result["errors"] = errors[:10]  # Cap error list

    # Save output if requested
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "jd_extraction_quality.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    return result


# ──────────────────────────────────────────────
# Task 4: measure_match_accuracy
# ──────────────────────────────────────────────

async def measure_match_accuracy(
    golden_dir: str | Path = "evaluation",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run matching on Match Golden Set and compute accuracy.

    Loads the match golden set from ``evaluation/golden_set_match.jsonl``,
    runs the matching service for each sample, and computes binary
    classification accuracy (match vs. no-match).

    Returns a metric dict with accuracy and per-sample details.
    If the golden set or match service is unavailable, returns a clear
    message instead of a pending status.
    """
    golden_path = Path(golden_dir) / "golden_set_match.jsonl"
    golden_data = _load_jsonl(golden_path)

    if not golden_data:
        return {
            "metric": "人岗匹配准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": f"Match golden set not found or empty at {golden_path}. "
                      "Run evaluation/golden_set_match.jsonl population first.",
        }

    # Attempt to import the match service
    try:
        from app.services.match_service import run_match
        has_match = True
    except Exception:
        has_match = False

    if not has_match:
        return {
            "metric": "人岗匹配准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": "Match service not available. "
                      "Ensure backend dependencies are installed.",
        }

    correct = 0
    total = 0
    score_errors: list[float] = []
    evaluations: list[dict[str, Any]] = []
    errors: list[str] = []

    for golden in golden_data:
        sid = golden.get("id", "unknown")
        position = golden.get("position", "")
        person_skills = golden.get("person_skills", [])
        expected = golden.get("expected", {})
        should_match = expected.get("should_match", None)
        expected_min = expected.get("match_score_min", 0.0)
        expected_max = expected.get("match_score_max", 1.0)

        if not position or not person_skills:
            errors.append(f"Sample {sid}: missing position or person_skills")
            continue

        # Build resume text from person_skills for the match service
        skill_lines = []
        for s in person_skills:
            if isinstance(s, dict):
                name = s.get("name", "")
                prof = s.get("proficiency", "")
                skill_lines.append(f"- {name} ({prof})" if prof else f"- {name}")
            else:
                skill_lines.append(f"- {s}")
        resume_text = "技能列表：\n" + "\n".join(skill_lines)

        try:
            result = await run_match(
                position_name=position,
                resume_text=resume_text,
            )
            system_score = result.get("match_score", 0.0)
        except Exception as exc:
            errors.append(f"Sample {sid}: match exception - {exc}")
            evaluations.append({
                "sample_id": sid,
                "system_score": 0.0,
                "expected_range": [expected_min, expected_max],
                "error": str(exc),
            })
            continue

        total += 1

        # Binary accuracy: does the system agree with the golden should_match?
        system_match = system_score >= 0.6
        if should_match is not None:
            if system_match == should_match:
                correct += 1
        else:
            # Fallback: check if score falls within expected range
            if expected_min <= system_score <= expected_max:
                correct += 1

        score_errors.append(abs(system_score - (expected_min + expected_max) / 2))

        evaluations.append({
            "sample_id": sid,
            "system_score": round(system_score, 4),
            "expected_range": [expected_min, expected_max],
            "should_match": should_match,
            "system_match": system_match,
        })

    if total == 0:
        return {
            "metric": "人岗匹配准确率",
            "target": ">=90%",
            "current": "N/A",
            "status": "unavailable",
            "detail": "No valid match samples evaluated. " + "; ".join(errors[:5]),
        }

    accuracy = round(correct / total, 4)
    avg_score_error = round(sum(score_errors) / len(score_errors), 4) if score_errors else 0.0
    passed = accuracy >= 0.90

    result = {
        "metric": "人岗匹配准确率",
        "target": ">=90%",
        "current": f"{accuracy:.2%}",
        "status": "pass" if passed else "fail",
        "detail": (
            f"Based on {total} match samples: accuracy={accuracy:.4f}, "
            f"avg_score_error={avg_score_error:.4f}"
        ),
        "per_sample": evaluations,
    }

    if errors:
        result["errors"] = errors[:10]

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "match_accuracy.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    return result


# ──────────────────────────────────────────────
# Task 4: measure_overall_system_health
# ──────────────────────────────────────────────

async def measure_overall_system_health(
    golden_dir: str | Path = "evaluation",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Aggregate all quality metrics into an overall system health report.

    Runs both JD extraction quality and match accuracy evaluations,
    then combines them into a single health assessment.

    Returns a dict with overall score, per-metric breakdown, and
    a warning level (green/yellow/orange/red).
    """
    jd_result = await measure_jd_extraction_quality(golden_dir, output_dir)
    match_result = await measure_match_accuracy(golden_dir, output_dir)

    # Extract numeric scores from results
    def _extract_score(result: dict[str, Any]) -> float | None:
        current = result.get("current")
        if isinstance(current, str) and current.endswith("%"):
            try:
                return float(current.strip("%")) / 100.0
            except (ValueError, TypeError):
                return None
        if isinstance(current, (int, float)):
            return float(current)
        return None

    jd_score = _extract_score(jd_result)
    match_score = _extract_score(match_result)

    # Compute overall score (average of available metrics)
    scores = [s for s in [jd_score, match_score] if s is not None]
    overall_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    # Determine warning level
    if not scores:
        warning_level = "gray"
    elif overall_score >= 0.90:
        warning_level = "green"
    elif overall_score >= 0.75:
        warning_level = "yellow"
    elif overall_score >= 0.60:
        warning_level = "orange"
    else:
        warning_level = "red"

    # Determine overall status
    if not scores:
        overall_status = "unavailable"
    elif overall_score >= 0.90:
        overall_status = "pass"
    elif overall_score >= 0.70:
        overall_status = "warning"
    else:
        overall_status = "fail"

    # Build recommendations
    recommendations: list[str] = []
    if jd_score is not None and jd_score < 0.80:
        recommendations.append(
            f"JD extraction F1 is {jd_score:.2%}, below 80% threshold. "
            "Consider optimizing the extraction prompt or adding more normalization aliases."
        )
    if match_score is not None and match_score < 0.80:
        recommendations.append(
            f"Match accuracy is {match_score:.2%}, below 80% threshold. "
            "Review skill matching weights and prerequisite graph coverage."
        )
    if jd_score is None:
        recommendations.append(
            "JD extraction quality could not be measured. "
            "Ensure the golden set and LLM extraction pipeline are available."
        )
    if match_score is None:
        recommendations.append(
            "Match accuracy could not be measured. "
            "Ensure the match golden set and match service are available."
        )
    if not recommendations:
        recommendations.append("All quality metrics are within acceptable ranges.")

    result = {
        "metric": "系统综合健康度",
        "target": ">=90%",
        "current": f"{overall_score:.2%}",
        "status": overall_status,
        "warning_level": warning_level,
        "detail": (
            f"Aggregated from {len(scores)} metrics: "
            f"JD_extraction={jd_score if jd_score is not None else 'N/A'}, "
            f"match_accuracy={match_score if match_score is not None else 'N/A'}"
        ),
        "breakdown": {
            "jd_extraction": jd_result,
            "match_accuracy": match_result,
        },
        "recommendations": recommendations,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "overall_system_health.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    return result


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

async def _async_main(args: argparse.Namespace) -> None:
    """Run all quality measurements and produce a report."""
    golden_dir = args.golden
    output_dir = args.output

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = await measure_overall_system_health(golden_dir, output_dir)

    # Write comprehensive report
    report = {
        "generated_at": result["generated_at"],
        "warning_level": result["warning_level"],
        "overall_score": result["current"],
        "overall_status": result["status"],
        "metrics": [
            result["breakdown"]["jd_extraction"],
            result["breakdown"]["match_accuracy"],
        ],
        "recommendations": result["recommendations"],
    }

    json_path = output_path / "quality_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Markdown report
    md_lines = [
        "# StarMap Backend Quality Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Warning Level: **{report['warning_level']}**",
        "",
        "| Metric | Target | Current | Status |",
        "|--------|--------|---------|--------|",
    ]
    for m in report["metrics"]:
        current = m.get("current", "N/A")
        status = m.get("status", "unknown")
        status_icon = {
            "pass": "✅", "fail": "❌", "unavailable": "⬜", "warning": "⚠️",
        }.get(status, "⬜")
        md_lines.append(f"| {m['metric']} | {m['target']} | {current} | {status_icon} {status} |")

    md_lines.append("")
    md_lines.append("## Recommendations")
    for rec in report["recommendations"]:
        md_lines.append(f"- {rec}")

    md_path = output_path / "quality_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("Quality report generated:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print()
    for line in md_lines:
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="StarMap Backend Quality Report")
    parser.add_argument(
        "--golden", default="evaluation",
        help="Directory containing golden set JSONL files (default: evaluation/)",
    )
    parser.add_argument(
        "--output", default="reports/",
        help="Output directory for quality reports (default: reports/)",
    )
    args = parser.parse_args()
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
