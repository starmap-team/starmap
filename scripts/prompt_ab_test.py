"""Prompt A/B Test with Real MiMo LLM - tests v1-v4 on 3 representative samples (to save time)."""
import json, requests, time

BASE_URL = "http://localhost:8000"
GOLDEN_FILE = r"C:\Users\LiShuai\Desktop\Agents\starmap\backend\tests\fixtures\golden_jd_evaluation_sample.jsonl"

# Use 3 representative samples for A/B (AI engineer, backend, NLP)
TEST_IDS = {"golden-1", "golden-4", "golden-8"}

def normalize(name):
    aliases = {
        "python3": "Python", "python": "Python", "js": "JavaScript",
        "typescript": "TypeScript", "vue.js": "Vue.js", "css3": "CSS",
        "html5": "HTML", "node.js": "Node.js", "prompt engineering": "Prompt Engineering",
        "ci/cd": "CI/CD", "scikit-learn": "scikit-learn",
    }
    return aliases.get(name.strip().lower(), name.strip())

def skill_match(extracted, golden_list):
    ext = normalize(extracted).lower()
    for g in golden_list:
        gold = normalize(g).lower()
        if gold == ext or gold in ext or ext in gold:
            return True
    return False

def load_golden():
    samples = []
    with open(GOLDEN_FILE, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return [s for s in samples if s["id"] in TEST_IDS]

def extract_one(jd_text, options=None):
    payload = {"jd_content": jd_text}
    if options:
        payload["options"] = options
    try:
        r = requests.post(f"{BASE_URL}/api/v1/extract/jd", json=payload, timeout=120)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            return []
        data = r.json()
        req = data.get("required_skills", [])
        pref = data.get("preferred_skills", [])
        names = []
        for s in req + pref:
            if isinstance(s, dict):
                names.append(s.get("skill") or s.get("name") or "")
            else:
                names.append(str(s))
        return [n for n in names if n]
    except Exception as e:
        print(f"  Error: {e}")
        return []

def measure_f1(samples, version):
    total_f1 = 0
    count = 0
    for sample in samples:
        golden_all = set(sample["required_skills"]) | set(sample.get("bonus_skills", []))
        jd_text = f"岗位：{sample['job_title']}\n要求：{'、'.join(sample['required_skills'])}"
        if sample.get("bonus_skills"):
            jd_text += f"\n加分项：{'、'.join(sample['bonus_skills'])}"
        
        # Pass version hint via options
        ext_names = extract_one(jd_text, options={"prompt_version": version})
        
        matched = set()
        tp = 0
        for ext in ext_names:
            for g in golden_all:
                if skill_match(ext, [g]) and g not in matched:
                    tp += 1
                    matched.add(g)
                    break
        
        p = tp / len(ext_names) if ext_names else 0
        r_val = tp / len(golden_all) if golden_all else 0
        f1 = 2 * p * r_val / (p + r_val) if (p + r_val) > 0 else 0
        total_f1 += f1
        count += 1
        print(f"  {sample['id']}: F1={f1:.3f} ext={len(ext_names)} gold={len(golden_all)}")
        time.sleep(2)
    
    return round(total_f1 / count, 4) if count else 0

def main():
    samples = load_golden()
    versions = ["v1", "v2", "v3", "v4"]
    results = {}
    
    print("Prompt A/B Test - Real MiMo v2.5 (3 samples)")
    print("=" * 50)
    
    for v in versions:
        print(f"\n--- Testing prompt {v} ---")
        avg_f1 = measure_f1(samples, v)
        results[v] = avg_f1
        print(f"  {v} avg F1: {avg_f1}")
    
    print(f"\n{'='*50}")
    print("PROMPT A/B RESULTS")
    print(f"{'='*50}")
    best_v = max(results, key=lambda k: results[k])
    for v in versions:
        marker = " *** BEST" if v == best_v else ""
        print(f"  {v}: avg F1 = {results[v]}{marker}")
    
    print(f"\nRecommended: {best_v} (F1={results[best_v]})")
    
    output = {
        "test_date": "2026-06-28",
        "llm_model": "mimo-v2.5",
        "golden_samples": len(samples),
        "sample_ids": [s["id"] for s in samples],
        "results": results,
        "best_version": best_v,
        "best_f1": results[best_v]
    }
    with open(r"C:\Users\LiShuai\Desktop\Agents\starmap\tests\e2e\prompt_ab_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to tests/e2e/prompt_ab_results.json")

if __name__ == "__main__":
    main()
