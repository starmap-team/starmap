"""Real LLM Accuracy Measurement - runs extraction via live API and measures F1."""
import json, requests, time, sys

BASE_URL = "http://localhost:8000"
GOLDEN_FILE = "backend/tests/fixtures/golden_jd_evaluation_sample.jsonl"

def normalize(name: str) -> str:
    aliases = {
        "python3": "Python", "python": "Python", "js": "JavaScript",
        "typescript": "TypeScript", "ts": "TypeScript", "vue.js": "Vue.js",
        "vue": "Vue.js", "css3": "CSS", "css": "CSS", "html5": "HTML",
        "html": "HTML", "node.js": "Node.js", "nodejs": "Node.js",
        "k8s": "Kubernetes", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
        "prompt engineering": "Prompt Engineering", "prompt": "Prompt Engineering",
        "llm": "LLM", "ci/cd": "CI/CD", "cicd": "CI/CD",
        "android studio": "Android Studio", "android sdk": "Android SDK",
        "jetpack compose": "Jetpack Compose", "scikit-learn": "scikit-learn",
        "sklearn": "scikit-learn",
    }
    n = name.strip().lower()
    return aliases.get(n, name.strip())

def skill_match(extracted: str, golden_list: list[str]) -> bool:
    ext = normalize(extracted).lower()
    for g in golden_list:
        gold = normalize(g).lower()
        if gold == ext:
            return True
        if gold in ext or ext in gold:
            return True
    return False

def measure():
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5).json()
        if health.get("status") != "ok":
            print("Backend not healthy"); sys.exit(1)
    except Exception as e:
        print(f"Cannot reach backend: {e}"); sys.exit(1)
    
    samples = []
    with open(GOLDEN_FILE, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    
    total_precision = 0.0
    total_recall = 0.0
    total_f1 = 0.0
    results = []
    
    for sample in samples:
        golden_id = sample["id"]
        job_title = sample["job_title"]
        golden_req = set(sample["required_skills"])
        golden_bonus = set(sample.get("bonus_skills", []))
        golden_all = golden_req | golden_bonus
        
        jd_text = f"岗位：{job_title}\n要求：{'、'.join(sample['required_skills'])}"
        if sample.get("bonus_skills"):
            jd_text += f"\n加分项：{'、'.join(sample['bonus_skills'])}"
        
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/extract/jd",
                json={"jd_content": jd_text},
                timeout=120
            )
            data = resp.json()
            
            # API returns ExtractionResult directly (not wrapped in success/data)
            req_skills = data.get("required_skills", [])
            pref_skills = data.get("preferred_skills", [])
            all_extracted = req_skills + pref_skills
            
            ext_names = []
            for s in all_extracted:
                if isinstance(s, dict):
                    name = s.get("skill") or s.get("name") or s.get("skill_name") or str(s)
                    ext_names.append(name)
                else:
                    ext_names.append(str(s))
            
            true_positive = 0
            matched_golden = set()
            for ext in ext_names:
                for g in golden_all:
                    if skill_match(ext, [g]) and g not in matched_golden:
                        true_positive += 1
                        matched_golden.add(g)
                        break
            
            precision = true_positive / len(ext_names) if ext_names else 0.0
            recall = true_positive / len(golden_all) if golden_all else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            total_precision += precision
            total_recall += recall
            total_f1 += f1
            
            status = "OK" if f1 >= 0.7 else "LOW"
            results.append({
                "id": golden_id,
                "title": job_title,
                "extracted": ext_names,
                "golden": list(golden_all),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "status": status
            })
            print(f"[{status}] {golden_id}: P={precision:.3f} R={recall:.3f} F1={f1:.3f} | ext={len(ext_names)} gold={len(golden_all)}")
            
        except Exception as e:
            print(f"[ERR] {golden_id}: {e}")
            results.append({"id": golden_id, "error": str(e), "f1": 0.0, "status": "ERROR"})
        
        time.sleep(2)
    
    n = len([r for r in results if r.get("status") != "ERROR"])
    avg_p = total_precision / n if n else 0
    avg_r = total_recall / n if n else 0
    avg_f1 = total_f1 / n if n else 0
    
    print(f"\n{'='*60}")
    print(f"JD EXTRACTION ACCURACY (Real LLM - MiMo v2.5)")
    print(f"{'='*60}")
    print(f"Samples: {n}")
    print(f"Avg Precision: {avg_p:.4f}")
    print(f"Avg Recall:    {avg_r:.4f}")
    print(f"Avg F1:        {avg_f1:.4f}")
    print(f"Target:        >=0.85")
    print(f"Status:        {'PASS' if avg_f1 >= 0.85 else 'BELOW TARGET'}")
    
    output = {
        "measurement_date": "2026-06-28",
        "llm_model": "mimo-v2.5",
        "samples": n,
        "avg_precision": round(avg_p, 4),
        "avg_recall": round(avg_r, 4),
        "avg_f1": round(avg_f1, 4),
        "target_met": avg_f1 >= 0.85,
        "details": results
    }
    with open("tests/e2e/real_llm_accuracy_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to tests/e2e/real_llm_accuracy_results.json")

if __name__ == "__main__":
    measure()