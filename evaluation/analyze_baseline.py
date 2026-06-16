"""Analyze baseline results: identify false positives/negatives vs golden set."""
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Load golden and system outputs
with open(BASE / "golden_set.jsonl", "r", encoding="utf-8") as f:
    golden = [json.loads(line) for line in f if line.strip()]

with open(BASE / "system_baseline.jsonl", "r", encoding="utf-8") as f:
    system = [json.loads(line) for line in f if line.strip()]

golden_map = {g["id"]: g for g in golden}
system_map = {s["id"]: s for s in system}

all_false_positives = Counter()
all_false_negatives = Counter()
sample_details = []

for sid in golden_map:
    g = golden_map[sid]
    s = system_map.get(sid, {})

    g_req = set(x.lower() for x in g.get("required_skills", []))
    g_bon = set(x.lower() for x in g.get("bonus_skills", []))
    s_req = set(x.lower() for x in s.get("required_skills", []))
    s_bon = set(x.lower() for x in s.get("bonus_skills", []))

    g_all = g_req | g_bon
    s_all = s_req | s_bon

    fp = s_all - g_all
    fn = g_all - s_all

    for skill in fp:
        all_false_positives[skill] += 1
    for skill in fn:
        all_false_negatives[skill] += 1

    sample_details.append({
        "id": sid,
        "title": g["job_title"],
        "golden_count": len(g_all),
        "system_count": len(s_all),
        "fp_count": len(fp),
        "fn_count": len(fn),
        "false_positives": sorted(fp),
        "false_negatives": sorted(fn),
    })

# Sort by worst F1 (most errors)
sample_details.sort(key=lambda x: x["fp_count"] + x["fn_count"], reverse=True)

print("=" * 60)
print("BASELINE FAILURE ANALYSIS")
print("=" * 60)

print(f"\nTotal false negatives across all samples: {sum(all_false_negatives.values())}")
print(f"Total false positives across all samples: {sum(all_false_positives.values())}")
print(f"Unique skills missed (FN): {len(all_false_negatives)}")
print(f"Unique skills wrongly matched (FP): {len(all_false_positives)}")

print("\n--- TOP 15 MISSED SKILLS (False Negatives) ---")
for skill, count in all_false_negatives.most_common(15):
    print(f"  {skill:30s}  missing in {count}/50 samples")

print("\n--- TOP 15 WRONG SKILLS (False Positives) ---")
for skill, count in all_false_positives.most_common(15):
    print(f"  {skill:30s}  extra in {count}/50 samples")

print("\n--- WORST SAMPLES (most errors) ---")
for sd in sample_details[:10]:
    print(f"\n  [{sd['id']}] {sd['title']}")
    print(f"       Golden: {sd['golden_count']} skills, System: {sd['system_count']} skills")
    print(f"       FP: {sd['fp_count']}, FN: {sd['fn_count']}")
    if sd["false_positives"]:
        print(f"       Wrong extra skills: {', '.join(sd['false_positives'][:8])}")
    if sd["false_negatives"]:
        print(f"       Missing skills: {', '.join(sd['false_negatives'][:8])}")

print("\n--- SKILLS IN GOLDEN SET NOT IN SKILL_ALIAS ---")
all_golden_skills = set()
for g in golden:
    for s in g.get("required_skills", []):
        all_golden_skills.add(s.lower())
    for s in g.get("bonus_skills", []):
        all_golden_skills.add(s.lower())

with open(BASE / "system_baseline.jsonl", "r", encoding="utf-8") as f:
    sys_skills = set()
    for line in f:
        if line.strip():
            d = json.loads(line)
            for s in d.get("required_skills", []):
                sys_skills.add(s.lower())
            for s in d.get("bonus_skills", []):
                sys_skills.add(s.lower())

missing_from_alias = all_golden_skills - sys_skills
print(f"\nGolden skills not detected by rule-based ({len(missing_from_alias)}):")
for s in sorted(missing_from_alias):
    print(f"  - {s}")
