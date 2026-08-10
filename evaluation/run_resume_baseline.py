"""Resume extraction evaluation runner.

Uses the same rule-based extraction as JD baseline (keyword matching)
to establish a baseline for resume skill extraction F1.
"""
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from app.core.extraction.normalize import SKILL_ALIAS


def build_pattern_index() -> dict[str, str]:
    """Build lowercase skill -> canonical name lookup dict."""
    index = {}
    for standard, aliases in SKILL_ALIAS.items():
        for alias in aliases:
            index[alias.lower()] = standard
        index[standard.lower()] = standard
    return index


def extract_skills_keyword(text: str, index: dict[str, str]) -> dict[str, str]:
    """Extract skill names from text by substring matching."""
    text_lower = text.lower()
    found = {}
    for alias_lower, canonical in index.items():
        if len(alias_lower) <= 2:
            pattern = r'(?:^|[^a-zA-Z0-9\u4e00-\u9fff])' + re.escape(alias_lower) + r'(?:$|[^a-zA-Z0-9\u4e00-\u9fff])'
            if re.search(pattern, text_lower, re.IGNORECASE):
                found[canonical.lower()] = canonical
        else:
            if alias_lower in text_lower:
                found[canonical.lower()] = canonical
    return found


def evaluate_sample(predicted: set[str], expected: set[str]) -> dict:
    """Evaluate precision, recall, F1 for a single sample."""
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def main():
    golden_path = Path(__file__).resolve().parent / "golden_set_resume.jsonl"
    index = build_pattern_index()

    # Load golden set
    samples = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    total_tp = total_fp = total_fn = 0
    per_sample = []

    for sample in samples:
        text = sample["input"]
        expected = set(sample["expected"]["skills"])
        found = extract_skills_keyword(text, index)
        predicted = set(found.values())

        result = evaluate_sample(predicted, expected)
        total_tp += result["tp"]
        total_fp += result["fp"]
        total_fn += result["fn"]
        per_sample.append({"id": sample["id"], **result})

    # Micro-averaged metrics
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("=" * 60)
    print("RESUME EXTRACTION BASELINE")
    print("=" * 60)
    print(f"  Total samples:   {len(samples)}")
    print(f"  Avg Precision:   {precision:.4f}")
    print(f"  Avg Recall:      {recall:.4f}")
    print(f"  Avg F1:          {f1:.4f}")
    print(f"  Quality Gate (F1 >= 0.90): {'PASS' if f1 >= 0.90 else 'FAIL'}")
    print("=" * 60)

    return {"precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    main()
