"""Debug keyword matching on golden set JDs."""
import json, re
from pathlib import Path

# Load first golden entry
with open(Path(__file__).resolve().parent / "golden_set.jsonl", "r", encoding="utf-8") as f:
    entry = json.loads(f.readline())

raw_jd = entry["raw_jd"]
golden_skills = entry["required_skills"] + entry["bonus_skills"]

print(f"ID: {entry['id']}")
print(f"Title: {entry['job_title']}")
print(f"Golden skills ({len(golden_skills)}): {golden_skills}")
print(f"\nJD text ({len(raw_jd)} chars, first 200): {raw_jd[:200]}")
print()

# Try matching each golden skill
for skill in golden_skills:
    # Try \b word boundary approach
    p1 = re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE)
    m1 = p1.search(raw_jd)
    
    # Try (?!\w) approach
    p2 = re.compile(rf"(?<!\w){re.escape(skill)}(?!\w)", re.IGNORECASE)
    m2 = p2.search(raw_jd)
    
    # Try raw substring (no word boundaries)
    m3 = skill.lower() in raw_jd.lower()
    
    results = []
    if m1: results.append(f"word-boundary: '{m1.group()}'")
    if m2: results.append(f"not-w: '{m2.group()}'")
    if m3: results.append("raw-substring")
    
    if results:
        print(f"  [OK] {skill}: {'; '.join(results)}")
    else:
        print(f"  ❌ {skill}: NOT FOUND")
        
        # Show context around where skill might be expected
        idx = raw_jd.lower().find(skill.lower()[:4])
        if idx >= 0:
            print(f"     Context nearby: ...{raw_jd[max(0,idx-10):idx+len(skill)+10]}...")
