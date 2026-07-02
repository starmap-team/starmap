"""Pipeline 性能测试脚本 (AC-1)。

测量冷缓存和热缓存的端到端延迟。
验收标准：冷缓存≤60s，热缓存≤10s。

用法：
    python scripts/measure_pipeline_performance.py [--base-url http://localhost:8000] [--runs 3]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx


async def measure_latency(base_url: str, runs: int = 3) -> dict:
    """测量 Pipeline 端到端延迟。"""
    resume_path = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures" / "test_resume_backend.txt"
    if not resume_path.exists():
        print(f"❌ Test resume not found: {resume_path}")
        return {}

    resume_bytes = resume_path.read_bytes()
    cold_times = []
    hot_times = []

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        # 冷缓存测试（第1次调用）
        print(f"\n{'=' * 60}")
        print(f"⏱️  Cold Cache Test ({runs} runs)")
        print(f"{'=' * 60}")
        for i in range(runs):
            files = {"resume_file": ("test_resume.txt", resume_bytes, "text/plain")}
            start = time.time()
            try:
                r = await client.post("/api/v1/pipeline/export", files=files)
                elapsed = time.time() - start
                if r.status_code == 200:
                    cold_times.append(elapsed)
                    print(f"  Run {i + 1}: {elapsed:.2f}s ✅")
                else:
                    print(f"  Run {i + 1}: HTTP {r.status_code} ❌")
            except Exception as exc:
                print(f"  Run {i + 1}: Failed - {exc} ❌")

        # 热缓存测试（相同简历再次调用）
        print(f"\n{'=' * 60}")
        print(f"⏱️  Hot Cache Test ({runs} runs)")
        print(f"{'=' * 60}")
        for i in range(runs):
            files = {"resume_file": ("test_resume.txt", resume_bytes, "text/plain")}
            start = time.time()
            try:
                r = await client.post("/api/v1/pipeline/export", files=files)
                elapsed = time.time() - start
                if r.status_code == 200:
                    hot_times.append(elapsed)
                    print(f"  Run {i + 1}: {elapsed:.2f}s ✅")
                else:
                    print(f"  Run {i + 1}: HTTP {r.status_code} ❌")
            except Exception as exc:
                print(f"  Run {i + 1}: Failed - {exc} ❌")

    # 汇总
    cold_avg = sum(cold_times) / len(cold_times) if cold_times else float("inf")
    hot_avg = sum(hot_times) / len(hot_times) if hot_times else float("inf")

    print(f"\n{'=' * 60}")
    print(f"📊 Performance Report")
    print(f"{'=' * 60}")
    print(f"  Cold cache:  avg={cold_avg:.2f}s  threshold=60s  {'✅ PASS' if cold_avg <= 60 else '❌ FAIL'}")
    print(f"  Hot cache:   avg={hot_avg:.2f}s  threshold=10s  {'✅ PASS' if hot_avg <= 10 else '❌ FAIL'}")

    if cold_times:
        print(f"  Cold times: {[f'{t:.2f}s' for t in cold_times]}")
    if hot_times:
        print(f"  Hot times:  {[f'{t:.2f}s' for t in hot_times]}")

    return {
        "cold_cache": {
            "times": [round(t, 2) for t in cold_times],
            "avg": round(cold_avg, 2),
            "threshold": 60,
            "passed": cold_avg <= 60,
        },
        "hot_cache": {
            "times": [round(t, 2) for t in hot_times],
            "avg": round(hot_avg, 2),
            "threshold": 10,
            "passed": hot_avg <= 10,
        },
        "overall": "PASS" if cold_avg <= 60 and hot_avg <= 10 else "FAIL",
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline 性能测试")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = await measure_latency(args.base_url, args.runs)

    if args.output and report:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n📄 报告已保存到: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
