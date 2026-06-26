"""M2 evaluation: run the real LLM extraction pipeline against the golden set.

Measures F1 using the actual Xunfei Spark / Qwen pipeline.
Requires Docker/Ollama running with Qwen2.5-7B or Xunfei API keys configured.

Usage:
    python evaluation/run_llm_eval.py          # Full 50-JD evaluation
    python evaluation/run_llm_eval.py --quick  # 5-JD smoke test
"""

import asyncio
import json
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from evaluation.judge_eval import evaluate_batch, generate_evaluation_report
from app.core.extraction.jd_extract import extract_from_jd


def load_golden_set(path: Path, quick: bool = False) -> list[dict]:
    """Load golden set, optionally limiting to first N for smoke test."""
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    if quick:
        entries = entries[:5]
    return entries


def _dedup_skills(skills: list[str]) -> list[str]:
    """Remove duplicate skills while preserving order."""
    seen = set()
    result = []
    for s in skills:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(s)
    return result


def convert_to_eval_format(
    pipeline_result: dict, entry: dict
) -> dict:
    """Convert pipeline output to evaluation-compatible format."""
    data = pipeline_result.get("data", {})
    normalization = pipeline_result.get("normalization", [])

    # Collect skill names, preferring normalized names
    req_skills = []
    for s in data.get("required_skills", []):
        name = s.get("name", "")
        req_skills.append(name)
    pre_skills = []
    for s in data.get("preferred_skills", []):
        name = s.get("name", "")
        pre_skills.append(name)

    # Deduplicate
    req_skills = _dedup_skills(req_skills)
    pre_skills = _dedup_skills(pre_skills)

    return {
        "id": entry.get("id", ""),
        "job_title": entry.get("job_title", ""),
        "required_skills": req_skills,
        "bonus_skills": pre_skills,
        "experience_years": data.get("experience_required"),
        "education": data.get("education_required"),
    }


async def run_evaluation(quick: bool = False):
    """Run the full LLM evaluation pipeline."""
    print("=" * 60)
    print("M2  LLM Pipeline Evaluation")
    print("=" * 60)

    golden_path = BASE_DIR / "evaluation" / "golden_set.jsonl"
    system_output_path = BASE_DIR / "evaluation" / "system_llm_real.jsonl"
    report_dir = BASE_DIR / "evaluation" / "llm_real_report"

    # Load golden set
    entries = load_golden_set(golden_path, quick=quick)
    label = "SMOKE TEST" if quick else "FULL"
    print(f"\n[1/3] Loaded {len(entries)} golden entries [{label}]")

    # Run extraction pipeline on each JD
    print(f"\n[2/3] Running LLM extraction pipeline...")

    # Load existing results to support resuming
    existing_ids = set()
    if system_output_path.exists():
        with open(system_output_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing = json.loads(line)
                        existing_ids.add(existing.get("id", ""))
                    except json.JSONDecodeError:
                        pass
        if existing_ids:
            print(f"  Found {len(existing_ids)} existing results, will skip already-processed entries")

    results = []
    errors = []

    for i, entry in enumerate(entries):
        sid = entry.get("id", f"jd-{i+1:03d}")

        # Skip if already processed
        if sid in existing_ids:
            print(f"  [{i+1}/{len(entries)}] {sid} — already processed, skipping")
            continue

        raw_jd = entry.get("raw_jd", "")
        title = entry.get("job_title", "")

        print(f"  [{i+1}/{len(entries)}] {sid} ({title})...", end="", flush=True)
        t0 = time.time()

        try:
            pipeline_result = await extract_from_jd(
                raw_jd,
                options={"normalize_skills_enabled": True, "anti_hallucination_enabled": False},
            )
            elapsed = time.time() - t0

            if pipeline_result.get("success"):
                converted = convert_to_eval_format(pipeline_result, entry)
                results.append(converted)
                with open(system_output_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(converted, ensure_ascii=False) + "\n")
                skill_count = len(converted["required_skills"]) + len(converted["bonus_skills"])
                print(f"  OK ({skill_count} skills, {elapsed:.1f}s)")
            else:
                error_msg = pipeline_result.get("error", "unknown")
                errors.append({"id": sid, "error": error_msg})
                print(f"  FAIL: {error_msg}")

        except Exception as e:
            elapsed = time.time() - t0
            errors.append({"id": sid, "error": str(e)})
            print(f"  ERROR: {e} ({elapsed:.1f}s)")

    # Save system output (incrementally saved above, also write any remaining)
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  System output saved: {system_output_path}")

    # Save errors
    if errors:
        error_path = report_dir / "errors.json"
        with open(error_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        print(f"  Errors saved: {error_path}")

    # Evaluate
    print(f"\n[3/3] Running evaluation...")
    metrics = evaluate_batch(
        golden_file=str(golden_path),
        system_file=str(system_output_path),
        output_file=str(report_dir / "evaluation_results.json"),
    )

    # Generate report
    report = generate_evaluation_report(metrics, str(report_dir))

    # Summary
    passed = metrics.avg_f1 >= 0.80
    print(f"\n{'=' * 60}")
    print(f"M2 EVALUATION {'PASSED' if passed else 'FAILED'}")
    print(f"{'=' * 60}")
    print(f"  Samples:        {metrics.total_samples}")
    print(f"  Avg Precision:  {metrics.avg_precision:.4f}")
    print(f"  Avg Recall:     {metrics.avg_recall:.4f}")
    print(f"  Avg F1:         {metrics.avg_f1:.4f}")
    print(f"  Target F1:      0.80")
    print(f"  Status:         {'PASS' if passed else 'FAIL'}")
    if errors:
        print(f"  Errors:         {len(errors)} samples failed")
        for e in errors:
            print(f"    - {e['id']}: {e['error']}")
    print(f"\n  Report: {report['report_path']}")
    print(f"{'=' * 60}")

    return metrics.avg_f1 >= 0.80


def main():
    quick = "--quick" in sys.argv
    success = asyncio.run(run_evaluation(quick=quick))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
