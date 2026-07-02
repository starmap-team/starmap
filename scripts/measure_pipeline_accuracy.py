"""Pipeline 推荐准确率测量脚本 (AC-6)。

使用 golden_set_pipeline.jsonl 验证推荐引擎 Top-5 准确率≥60%。

用法：
    python scripts/measure_pipeline_accuracy.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx


async def measure_accuracy(base_url: str) -> dict:
    """逐条执行 golden set 并测量准确率。"""
    golden_path = Path(__file__).resolve().parent.parent / "evaluation" / "golden_set_pipeline.jsonl"
    if not golden_path.exists():
        print(f"❌ Golden set not found: {golden_path}")
        return {}

    cases = [json.loads(line) for line in golden_path.read_text().splitlines() if line.strip()]
    results = []

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        for i, case in enumerate(cases):
            input_data = case["input"]
            expected = case["expected"]

            print(f"\n--- Case {i+1}/{len(cases)} ---")
            resume_text = input_data["resume_text"]
            first_line = resume_text.split("\n")[0]
            print(f"  Resume: {first_line}")

            # 创建临时简历文件
            files = {"resume_file": ("resume.txt", resume_text.encode(), "text/plain")}
            target = input_data.get("target_positions", [])
            form_data = {}
            if target:
                form_data["target_positions"] = ",".join(target)

            # 调用 pipeline/export (JSON)
            start = time.time()
            try:
                r = await client.post("/api/v1/pipeline/export", files=files, data=form_data)
                elapsed = time.time() - start
            except Exception as exc:
                print(f"  ❌ Request failed: {exc}")
                results.append({"case": i + 1, "passed": False, "error": str(exc)})
                continue

            if r.status_code != 200:
                print(f"  ❌ HTTP {r.status_code}")
                results.append({"case": i + 1, "passed": False, "error": f"HTTP {r.status_code}"})
                continue

            data = r.json()
            case_result = {"case": i + 1, "elapsed": round(elapsed, 2), "checks": []}

            # 检查 extracted_skills 数量
            skills_count = len(data.get("extracted_skills", []))
            min_skills = expected.get("extracted_skills_min", 0)
            skills_ok = skills_count >= min_skills
            case_result["checks"].append({
                "name": "extracted_skills",
                "expected": f">={min_skills}",
                "actual": skills_count,
                "passed": skills_ok,
            })
            print(f"  [{'PASS' if skills_ok else 'FAIL'}] Skills: {skills_count} (expected >= {min_skills})")

            # 检查 top_matches 是否包含期望岗位
            top_matches = [m["position"] for m in data.get("top_matches", [])]
            expected_matches = expected.get("top_matches_contains", [])
            matches_ok = all(em in top_matches for em in expected_matches)
            case_result["checks"].append({
                "name": "top_matches",
                "expected": expected_matches,
                "actual": top_matches[:5],
                "passed": matches_ok,
            })
            print(f"  [{'PASS' if matches_ok else 'FAIL'}] Top matches contain {expected_matches}")

            # 检查推荐是否包含期望岗位
            recommendations = [r["position"] for r in data.get("recommended_positions", [])]
            expected_recs = expected.get("top_recommendations_contains", [])
            recs_ok = all(er in recommendations for er in expected_recs) if expected_recs else True
            case_result["checks"].append({
                "name": "recommendations",
                "expected": expected_recs,
                "actual": recommendations[:5],
                "passed": recs_ok,
            })
            print(f"  [{'PASS' if recs_ok else 'FAIL'}] Recommendations contain {expected_recs}")

            # 检查差距数量
            gaps = [g for g in data.get("skill_gaps", []) if g.get("gap_level") != "已掌握"]
            min_gaps = expected.get("min_gaps", 0)
            gaps_ok = len(gaps) >= min_gaps
            case_result["checks"].append({
                "name": "skill_gaps",
                "expected": f">={min_gaps}",
                "actual": len(gaps),
                "passed": gaps_ok,
            })
            print(f"  [{'PASS' if gaps_ok else 'FAIL'}] Gaps: {len(gaps)} (expected >= {min_gaps})")

            # 检查是否有错误
            errors = data.get("errors", [])
            no_errors = len(errors) == 0
            case_result["checks"].append({
                "name": "no_errors",
                "expected": 0,
                "actual": len(errors),
                "passed": no_errors,
            })
            print(f"  [{'PASS' if no_errors else 'WARN'}] Errors: {len(errors)}")

            all_passed = all(c["passed"] for c in case_result["checks"])
            case_result["passed"] = all_passed
            results.append(case_result)

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r.get("passed", False))
    accuracy = passed / total if total else 0.0

    print(f"\n{'=' * 60}")
    print(f"📊 Pipeline Accuracy Report")
    print(f"{'=' * 60}")
    print(f"  Total cases: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {total - passed}")
    print(f"  Accuracy: {accuracy:.1%}")
    print(f"  Threshold: 60%")
    print(f"  Result: {'✅ PASS' if accuracy >= 0.6 else '❌ FAIL'}")

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(accuracy, 4),
        "threshold": 0.6,
        "result": "PASS" if accuracy >= 0.6 else "FAIL",
        "cases": results,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline 推荐准确率测量")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default=None, help="输出报告路径")
    args = parser.parse_args()

    report = await measure_accuracy(args.base_url)

    if args.output and report:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n📄 报告已保存到: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
