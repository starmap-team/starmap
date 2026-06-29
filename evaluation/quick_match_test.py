"""Quick match accuracy test - bypasses ChromaDB normalize."""
import asyncio, json, os, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR / "backend"))

# Monkey-patch normalize to skip ChromaDB
import app.core.extraction.normalize as norm_mod
_orig = norm_mod.normalize_skill
def _fast_normalize(name: str):
    """Skip vector normalization, only use rule-based."""
    result = _orig(name)
    return result
# Set env to disable vector normalization
os.environ["CHROMA_HOST"] = "skip"

from app.services.match_service import run_match, _canonical_skill_name

async def main():
    golden_path = BASE_DIR / "evaluation" / "golden_set_match.jsonl"
    samples = []
    with open(golden_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line.strip()))

    print(f"Match Accuracy Test ({len(samples)} samples)")
    print("=" * 60)

    correct = 0
    total = 0
    details = []

    for sample in samples:
        sid = sample["id"]
        position = sample["position"]
        person_skills = sample["person_skills"]
        expected = sample["expected"]

        result = await run_match(
            target_position=position,
            person_skills=[{"name": s["name"], "proficiency": s.get("proficiency", "熟悉")} for s in person_skills],
            driver=None,
        )

        score = result["match_score"]
        should_match = expected["should_match"]
        score_min = expected["match_score_min"]
        score_max = expected["match_score_max"]

        in_range = score_min <= score <= score_max
        predicted_match = score >= 0.6
        decision_correct = predicted_match == should_match
        if decision_correct:
            correct += 1
        total += 1

        status = "OK" if decision_correct else "FAIL"
        print(f"  {sid}: pos={position}, score={score:.3f}, "
              f"range=[{score_min},{score_max}], match={predicted_match}, "
              f"expected={should_match} -> {status}")
        details.append({"id": sid, "score": score, "correct": decision_correct})

    acc = correct / total if total > 0 else 0
    print(f"\nAccuracy: {correct}/{total} = {acc:.4f}")
    print(f"Target >= 0.90 -> {'PASS' if acc >= 0.90 else 'NEEDS IMPROVEMENT'}")

    # Save report
    report = {"match_accuracy": acc, "correct": correct, "total": total, "details": details}
    with open(BASE_DIR / "evaluation" / "match_accuracy_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved to evaluation/match_accuracy_report.json")

if __name__ == "__main__":
    asyncio.run(main())
