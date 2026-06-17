"""Baseline evaluation: rule-based keyword extraction against golden set.

Measures F1 using keyword matching as a no-LLM baseline.
"""

import json
import re
import sys
from pathlib import Path

# Ensure both backend and evaluation dirs are importable
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from app.core.extraction.normalize import SKILL_ALIAS
from judge_eval import evaluate_batch, generate_evaluation_report


def build_pattern_index() -> dict[str, str]:
    """Build lowercase skill -> canonical name lookup dict."""
    index = {}
    for standard, aliases in SKILL_ALIAS.items():
        for alias in aliases:
            index[alias.lower()] = standard
        index[standard.lower()] = standard
    return index


def extract_skills_keyword(jd_text: str, index: dict[str, str]) -> dict[str, str]:
    """Extract skill names from JD text by substring matching.
    
    Uses raw substring matching (not word boundaries) because Chinese text
    doesn't have Latin word boundaries.
    
    Returns dict of {canonical_lower: canonical_name} for dedup.
    """
    jd_lower = jd_text.lower()
    found = {}
    for alias_lower, canonical in index.items():
        if alias_lower in jd_lower:
            found[canonical.lower()] = canonical
    return found


def extract_experience_years(jd_text: str) -> int | None:
    """Extract years of experience from JD text via regex."""
    patterns = [
        r"(\d+)[\+]?\s*\u5e74(?:\u4ee5\u4e0a|\u4ee5|\u53ca)?\s*(?:\u76f8\u5173)?\s*(?:\u5de5\u4f5c|\u5f00\u53d1|\u7ecf\u9a8c)",
        r"(\d+)[\+]?\s*(?:\u5e74)?\s*(?:\u4ee5\u4e0a|\u4ee5|\u53ca)?\s*(?:\u5de5\u4f5c|\u5f00\u53d1|\u7ecf\u9a8c|\u7ecf\u9a8c\u5e74\u9650)",
        r"experience[:\s]+(\d+)[\+]?\s*(?:years|yrs)",
        r"(\d+)[\+]?\s*\+\s*years?(?:\s+of)?\s+experience",
        r"(\d+)[\+]?\s*years?(?:\s+of)?\s+(?:working|development|professional)?\s*experience",
    ]
    for p in patterns:
        m = re.search(p, jd_text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def extract_education(jd_text: str) -> str | None:
    """Extract minimum education requirement from JD text."""
    edu_patterns = [
        (r"\u7855\u58eb(?:\u53ca\u4ee5\u4e0a|\u6216\u4ee5\u4e0a|\u53ca\u4ee5|\u6216\u4ee5|\u6216\u4ee5\u4e0a)?|\u7814\u7a76\u751f", "\u7855\u58eb\u53ca\u4ee5\u4e0a"),
        (r"\u672c\u79d1(?:\u53ca\u4ee5\u4e0a|\u6216\u4ee5\u4e0a|\u53ca\u4ee5|\u6216\u4ee5|\u6216\u4ee5\u4e0a)?|\u5b66\u58eb", "\u672c\u79d1\u53ca\u4ee5\u4e0a"),
        (r"\u5927\u4e13(?:\u53ca\u4ee5\u4e0a|\u6216\u4ee5\u4e0a)?|\u4e13\u79d1", "\u5927\u4e13\u53ca\u4ee5\u4e0a"),
        (r"\u535a\u58eb(?:\u53ca\u4ee5\u4e0a|\u6216\u4ee5\u4e0a)?", "\u535a\u58eb\u53ca\u4ee5\u4e0a"),
    ]
    for pattern, result in edu_patterns:
        if re.search(pattern, jd_text):
            return result
    return None


def classify_skills_bonus_context(jd_text: str, found_canonical: list[str]) -> tuple[list[str], list[str]]:
    """Classify skills into required vs bonus based on JD section context."""
    required = []
    bonus = []

    parts = re.split(
        r"(?:\u52a0\u5206[\u9879\u6761\u76ee]|\u4f18\u5148[\u8003\u8651]?|preferred|bonus|plus|nice\.to\.have|\u62c5\u4efb\u804c\u8d23)",
        jd_text,
        flags=re.IGNORECASE,
    )

    main_text = parts[0].lower() if parts else ""
    bonus_text = " ".join(parts[1:]).lower() if len(parts) > 1 else ""

    for skill in found_canonical:
        escaped = re.escape(skill.lower())
        in_main = bool(re.search(escaped, main_text))
        in_bonus = bool(re.search(escaped, bonus_text)) if bonus_text else False

        if in_bonus and not in_main:
            bonus.append(skill)
        else:
            required.append(skill)
    return required, bonus


def process_golden_entry(entry: dict, index: dict[str, str]) -> dict:
    """Process a single golden set entry with rule-based extraction."""
    raw_jd = entry.get("raw_jd", "")
    if not raw_jd:
        return {
            "id": entry.get("id", ""),
            "job_title": entry.get("job_title", ""),
            "required_skills": [],
            "bonus_skills": [],
            "experience_years": None,
            "education": None,
        }

    found = extract_skills_keyword(raw_jd, index)
    canonical_skills = list(found.values())
    required, bonus = classify_skills_bonus_context(raw_jd, canonical_skills)
    exp = extract_experience_years(raw_jd)
    edu = extract_education(raw_jd)

    return {
        "id": entry.get("id", ""),
        "job_title": entry.get("job_title", ""),
        "required_skills": required,
        "bonus_skills": bonus,
        "experience_years": exp,
        "education": edu,
    }


def main():
    """Run baseline evaluation."""
    print("=" * 60)
    print("StarMap Baseline Evaluation - Rule-Based Extraction")
    print("=" * 60)

    golden_path = Path(__file__).resolve().parent / "golden_set.jsonl"
    system_output_path = Path(__file__).resolve().parent / "system_baseline.jsonl"
    report_dir = Path(__file__).resolve().parent / "baseline_report"

    # Load golden set
    print(f"\n[1/4] Loading golden set from: {golden_path}")
    golden_data = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                golden_data.append(json.loads(line))
    print(f"       Loaded {len(golden_data)} entries")

    # Build pattern index
    print("\n[2/4] Building skill index...")
    index = build_pattern_index()
    print(f"       {len(index)} alias entries from {len(SKILL_ALIAS)} skill groups")

    # Run extraction
    print("\n[3/4] Running rule-based extraction on golden set...")
    system_results = []
    for entry in golden_data:
        result = process_golden_entry(entry, index)
        system_results.append(result)

    # Save system output
    with open(system_output_path, "w", encoding="utf-8") as f:
        for item in system_results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"       System output saved to: {system_output_path}")

    # Show sample
    print(f"\nSample output (first entry):")
    print(json.dumps(system_results[0], ensure_ascii=False, indent=2))

    # Evaluate
    print("\n[4/4] Running evaluation...")
    metrics = evaluate_batch(
        golden_file=str(golden_path),
        system_file=str(system_output_path),
        output_file=str(report_dir / "evaluation_results.json"),
    )

    # Generate report
    report = generate_evaluation_report(metrics, str(report_dir))

    # Print summary
    print(f"\n{'=' * 60}")
    print("BASELINE RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total samples:   {metrics.total_samples}")
    print(f"  Avg Precision:   {metrics.avg_precision:.4f}")
    print(f"  Avg Recall:      {metrics.avg_recall:.4f}")
    print(f"  Avg F1:          {metrics.avg_f1:.4f}")
    print(f"  Weighted Score:  {metrics.weighted_score:.4f}")
    print(f"\n  F1 Distribution:")
    print(f"    Excellent (>=0.90):  {metrics.f1_distribution['excellent']}")
    print(f"    Good     (>=0.70):  {metrics.f1_distribution['good']}")
    print(f"    Fair     (>=0.50):  {metrics.f1_distribution['fair']}")
    print(f"    Poor     (<0.50):   {metrics.f1_distribution['poor']}")
    print(f"\n  Quality Gate (F1 >= 0.90): [{'PASS' if report['quality_gate']['passed'] else 'FAIL'}]")
    print(f"  Report: {report['report_path']}")
    print(f"{'=' * 60}")

    return metrics


if __name__ == "__main__":
    main()
