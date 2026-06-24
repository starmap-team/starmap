"""Real end-to-end LLM extraction evaluation.

Calls the REAL MiMo API on each Golden Set raw_jd, runs the full
extraction pipeline (LLM -> validate -> normalize -> anti-hallucination),
then scores with judge_eval. Produces the FIRST trustworthy F1.

Anti-cheat: golden truth fields (required_skills/bonus_skills/exp/edu) are
NEVER passed to extraction. Only raw_jd goes in. Truth is compared only at
scoring time.

Usage (from project root):
    python evaluation/run_real_eval.py                # full 50 samples
    SAMPLE_LIMIT=3 python evaluation/run_real_eval.py # debug: 3 samples
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# chdir to project root so config.py can find .env
BASE_DIR = Path(__file__).resolve().parent.parent
os.chdir(BASE_DIR)

BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from app.core.extraction.jd_extract import JDExtractionPipeline  # noqa: E402
from app.core.extraction.llm_client import LLMClient  # noqa: E402
from judge_eval import evaluate_batch, generate_evaluation_report  # noqa: E402

EVAL_DIR = BASE_DIR / "evaluation"
GOLDEN_PATH = EVAL_DIR / "golden_set.jsonl"
OUTPUT_DIR = EVAL_DIR / "real_eval_report"
INTER_CALL_DELAY = 0.5  # seconds between API calls (QPS guard)


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────

def check_api_keys() -> None:
    """Fail fast if no LLM key configured — never silently degrade to mock."""
    from app.config import settings

    has_mimo = bool(settings.mimo_api_key)
    has_xunfei = bool(settings.xunfei_api_key)
    if not has_mimo and not has_xunfei:
        raise SystemExit(
            "FATAL: no LLM API key configured. "
            "Set MIMO_API_KEY or XUNFEI_API_KEY in .env. "
            "Refusing to run without a real API."
        )


def load_golden(path: Path) -> list[dict]:
    """Load golden_set.jsonl. Each line is one JSON object."""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def save_jsonl(records: list[dict], path: Path) -> None:
    """Write records as JSONL (one JSON per line, utf-8, no ASCII escaping)."""
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _get_skill_names(skills) -> list[str]:
    """Extract skill name strings from a list of SkillEntry objects or dicts."""
    result = []
    for s in skills:
        if isinstance(s, dict):
            result.append(s.get("name", str(s)))
        elif hasattr(s, "name"):
            result.append(s.name)
        else:
            result.append(str(s))
    return result


def format_for_eval(pipeline_output: dict, sample_id: str) -> dict:
    """Convert pipeline.run() output to judge_eval's expected format.

    Handles both pydantic objects and raw dicts (pipeline may return either).
    """
    if not pipeline_output.get("success") or pipeline_output.get("data") is None:
        return empty_result(sample_id)

    data = pipeline_output["data"]
    # Support both pydantic model (attr access) and dict (key access)
    def _get(obj, attr, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, attr, default)

    req_skills = _get(data, "required_skills", "required_skills", [])
    bon_skills = _get(data, "preferred_skills", "preferred_skills", [])

    return {
        "id": sample_id,
        "job_title": _get(data, "position_name", "position_name", "") or "",
        "required_skills": _get_skill_names(req_skills),
        "bonus_skills": _get_skill_names(bon_skills),
        "experience_years": _get(data, "experience_required", "experience_required"),
        "education": _get(data, "education_required", "education_required"),
    }


def empty_result(sample_id: str) -> dict:
    """Empty extraction result for failed/exception cases — counts as F1=0."""
    return {
        "id": sample_id,
        "job_title": "",
        "required_skills": [],
        "bonus_skills": [],
        "experience_years": None,
        "education": None,
    }


# ──────────────────────────────────────────────────────────────
# Error analysis
# ──────────────────────────────────────────────────────────────

def classify_errors(golden: dict, system: dict) -> dict:
    """Classify per-sample skill errors into 3 categories.

    Returns dict with keys: hallucination, miss, classification_error.
    """
    g_req = set(golden.get("required_skills", []))
    g_bon = set(golden.get("bonus_skills", []))
    s_req = set(system.get("required_skills", []))
    s_bon = set(system.get("bonus_skills", []))

    g_all = g_req | g_bon
    s_all = s_req | s_bon

    hallucination = sorted(s_all - g_all)
    miss = sorted(g_all - s_all)

    classification_error = []
    for skill in g_all & s_all:
        in_g_req = skill in g_req
        in_s_req = skill in s_req
        if in_g_req != in_s_req:
            classification_error.append(skill)

    return {
        "hallucination": hallucination,
        "miss": miss,
        "classification_error": sorted(classification_error),
    }


def write_error_analysis(results: list[dict], golden_path: Path,
                         output_dir: Path) -> None:
    """Generate error_analysis.md: 3-category breakdown + worst samples."""
    golden_data = load_golden(golden_path)
    golden_map = {g["id"]: g for g in golden_data}

    all_errors: dict[str, list[str]] = {"hallucination": [], "miss": [],
                                         "classification_error": []}
    per_sample = []
    for res in results:
        g = golden_map.get(res["id"], {})
        errs = classify_errors(g, res)
        for k in all_errors:
            all_errors[k].extend(errs[k])
        per_sample.append({"id": res["id"],
                           "job_title": g.get("job_title", ""),
                           "errors": errs})

    total_errs = sum(len(v) for v in all_errors.values())
    lines = ["# 错误分析（真实LLM抽取）\n"]
    lines.append(f"**总错误数**: {total_errs}\n")
    lines.append("## 按类型统计\n")
    lines.append("| 类型 | 次数 | 占比 |")
    lines.append("|------|------|------|")
    label = {
        "hallucination": "幻觉(false positive)",
        "miss": "漏抽(false negative)",
        "classification_error": "required/bonus误分类",
    }
    for k in ("hallucination", "miss", "classification_error"):
        cnt = len(all_errors[k])
        pct = f"{cnt / total_errs * 100:.0f}%" if total_errs else "0%"
        lines.append(f"| {label[k]} | {cnt} | {pct} |")

    lines.append("\n## 最差样本 Top 5（按错误数）\n")
    lines.append("| ID | 岗位 | 幻觉 | 漏抽 | 误分类 | 总计 |")
    lines.append("|----|------|------|------|--------|------|")
    ranked = sorted(per_sample,
                    key=lambda x: sum(len(v) for v in x["errors"].values()),
                    reverse=True)[:5]
    for s in ranked:
        e = s["errors"]
        tot = sum(len(v) for v in e.values())
        lines.append(f"| {s['id']} | {s['job_title']} | {len(e['hallucination'])} | "
                     f"{len(e['miss'])} | {len(e['classification_error'])} | {tot} |")

    lines.append("\n## 优化建议\n")
    if len(all_errors["hallucination"]) > len(all_errors["miss"]):
        lines.append("1. 幻觉多于漏抽 → Prompt 增加\"只输出JD明确提及的具体技术\"约束")
    elif len(all_errors["miss"]) > 0:
        lines.append("1. 漏抽较多 → 检查 Prompt 是否引导充分召回技能关键词")
    if all_errors["classification_error"]:
        lines.append("2. required/bonus误分类存在 → Prompt 强化\"加分项\"上下文判断")

    out_path = output_dir / "error_analysis.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"       Error analysis: {out_path}")


def write_metadata(metrics, failures: list[dict], output_dir: Path) -> None:
    """Write reproducibility metadata: API/prompt versions, config, failures."""
    from app.config import settings

    meta = {
        "eval_timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_provider": "xiaomi-mimo",
        "llm_model": settings.mimo_model,
        "llm_api_base": settings.mimo_api_base,
        "golden_set": "50 entries with raw_jd (PR#18 version)",
        "normalize_source": "hardcoded SKILL_ALIAS (191 groups in normalize.py)",
        "pipeline_config": {
            "anti_hallucination_enabled": True,
            "normalize_skills_enabled": True,
            "use_vector_normalization": False,
        },
        "total_samples": metrics.total_samples,
        "successful_extractions": metrics.total_samples - len(failures),
        "failed_extractions": len(failures),
        "failures": failures,
        "results_summary": {
            "avg_f1": metrics.avg_f1,
            "avg_precision": metrics.avg_precision,
            "avg_recall": metrics.avg_recall,
            "weighted_score": metrics.weighted_score,
        },
    }
    meta_path = output_dir / "evaluation_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"       Metadata: {meta_path}")


# ──────────────────────────────────────────────────────────────
# Main evaluation
# ──────────────────────────────────────────────────────────────

def _append_result(result: dict, path: Path) -> None:
    """Append one result to JSONL file immediately (crash-safe)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


async def run_real_evaluation(sample_limit: int | None = None) -> tuple[list[dict], list[dict]]:
    """Run real end-to-end extraction with incremental saving + resume.

    If system_real_llm.jsonl already exists, skips already-processed samples.
    Each result is appended immediately (crash-safe).
    """
    golden = load_golden(GOLDEN_PATH)
    if sample_limit:
        golden = golden[:sample_limit]
    total = len(golden)

    # Resume support: load existing results
    system_path = OUTPUT_DIR / "system_real_llm.jsonl"
    existing_ids = set()
    results = []
    failures = []
    if system_path.exists():
        existing = load_golden(system_path)
        results = existing
        existing_ids = {r["id"] for r in existing}
        print(f"[1/4] Resume mode: {len(existing)} already done, "
              f"{total - len(existing)} remaining")
    else:
        print(f"[1/4] Fresh run: {total} golden entries")

    pipeline = JDExtractionPipeline(
        llm_client=LLMClient(),
        anti_hallucination_enabled=True,
        normalize_skills_enabled=True,
    )
    print("[2/4] Pipeline ready (MiMo mimo-v2.5)")

    done_count = len(existing_ids)
    for i, entry in enumerate(golden, 1):
        sample_id = entry.get("id", f"idx-{i}")
        if sample_id in existing_ids:
            continue  # Already processed in a previous run

        raw_jd = entry.get("raw_jd", "")
        if not raw_jd.strip():
            failures.append({"id": sample_id, "error": "missing raw_jd"})
            empty = empty_result(sample_id)
            results.append(empty)
            _append_result(empty, system_path)
            print(f"       [{done_count + 1}/{total}] {sample_id} SKIP (no raw_jd)")
            done_count += 1
            continue
        try:
            output = await pipeline.run(raw_jd)
            result = format_for_eval(output, sample_id)
            results.append(result)
            _append_result(result, system_path)  # Save immediately
            n_skills = len(result["required_skills"])
            print(f"       [{done_count + 1}/{total}] {sample_id} OK ({n_skills} req skills)")
        except Exception as e:  # noqa: BLE001 — capture all for transparency
            failures.append({"id": sample_id, "error": str(e)})
            empty = empty_result(sample_id)
            results.append(empty)
            _append_result(empty, system_path)
            print(f"       [{done_count + 1}/{total}] {sample_id} FAIL: {e}")
        done_count += 1
        await asyncio.sleep(INTER_CALL_DELAY)

    print(f"[3/4] Extraction done: {done_count - len(failures)} OK, {len(failures)} failed")
    return results, failures


def score_existing_results() -> None:
    """Score existing system_real_llm.jsonl without re-running extraction."""
    system_path = OUTPUT_DIR / "system_real_llm.jsonl"
    if not system_path.exists():
        raise SystemExit(f"No results found at {system_path}. Run extraction first.")

    results = load_golden(system_path)
    print(f"Scoring {len(results)} existing results...")

    metrics = evaluate_batch(
        golden_file=str(GOLDEN_PATH),
        system_file=str(system_path),
        output_file=str(OUTPUT_DIR / "evaluation_results.json"),
    )
    generate_evaluation_report(metrics, str(OUTPUT_DIR))
    write_error_analysis(results, GOLDEN_PATH, OUTPUT_DIR)
    write_metadata(metrics, [], OUTPUT_DIR)
    _print_summary(metrics)


def _print_summary(metrics) -> None:
    """Print evaluation summary to console."""
    print(f"\n{'=' * 60}")
    print(f"REAL END-TO-END F1: {metrics.avg_f1:.4f}")
    print(f"  Precision: {metrics.avg_precision:.4f}")
    print(f"  Recall:    {metrics.avg_recall:.4f}")
    print(f"  Weighted:  {metrics.weighted_score:.4f}")
    print(f"  Distribution:")
    print(f"    Excellent(>=0.90): {metrics.f1_distribution.get('excellent', 0)}")
    print(f"    Good    (>=0.70): {metrics.f1_distribution.get('good', 0)}")
    print(f"    Fair    (>=0.50): {metrics.f1_distribution.get('fair', 0)}")
    print(f"    Poor    (<0.50):  {metrics.f1_distribution.get('poor', 0)}")
    gate = "PASS" if metrics.avg_f1 >= 0.80 else "FAIL"
    print(f"  Gate(>=0.80): [{gate}]")
    print(f"  Report: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


async def main(sample_limit: int | None = None) -> None:
    """Full evaluation: extract -> save -> score -> report -> error analysis."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results, failures = await run_real_evaluation(sample_limit=sample_limit)

    system_path = OUTPUT_DIR / "system_real_llm.jsonl"
    print(f"[4/4] System output saved: {system_path}")

    # Score using full golden (results are already filtered by sample_limit)
    metrics = evaluate_batch(
        golden_file=str(GOLDEN_PATH),
        system_file=str(system_path),
        output_file=str(OUTPUT_DIR / "evaluation_results.json"),
    )
    generate_evaluation_report(metrics, str(OUTPUT_DIR))

    write_error_analysis(results, GOLDEN_PATH, OUTPUT_DIR)
    write_metadata(metrics, failures, OUTPUT_DIR)
    _print_summary(metrics)


if __name__ == "__main__":
    import sys as _sys

    if "--score-only" in _sys.argv:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        score_existing_results()
    else:
        check_api_keys()
        limit = int(os.getenv("SAMPLE_LIMIT", "0")) or None
        asyncio.run(main(sample_limit=limit))
