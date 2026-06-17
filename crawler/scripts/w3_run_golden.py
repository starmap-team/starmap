"""W3 Golden Set 验证脚本：跑 50 条 evaluation/golden_set.jsonl 验证 F1。

流 A (R1) 调用 backend，流 D (R7) 验收。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("w3-golden")

DEFAULT_BACKEND = "http://localhost:8000"
GOLDEN_PATH = "evaluation/golden_set.jsonl"


def load_golden() -> list[dict]:
    p = Path(GOLDEN_PATH)
    if not p.exists():
        raise FileNotFoundError(f"找不到 Golden Set: {p}")
    items = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def call_extract(jd_text: str, backend_url: str) -> dict:
    try:
        resp = httpx.post(
            f"{backend_url}/api/v1/extract/jd",
            json={
                "jd_content": jd_text,
                "options": {"anti_hallucination_enabled": False, "normalize_skills_enabled": True},
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def skill_set(skills: list[dict]) -> set[str]:
    """从 [{name, level, category}, ...] 取出标准化 name 集合。"""
    return {s.get("name", "").strip() for s in skills if s.get("name")}


def compute_f1(predicted: set, golden: set) -> dict:
    """计算 Precision / Recall / F1。"""
    if not predicted and not golden:
        return {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted:
        return {"tp": 0, "fp": 0, "fn": len(golden), "precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not golden:
        return {"tp": 0, "fp": len(predicted), "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = len(predicted & golden)
    fp = len(predicted - golden)
    fn = len(golden - predicted)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def evaluate_golden(limit: int, backend_url: str) -> dict:
    golden = load_golden()
    if limit > 0:
        golden = golden[:limit]
    log.info("加载 %d 条 Golden Set", len(golden))

    results = []
    aggregate = {
        "total": 0,
        "errors": 0,
        "sum_p": 0.0,
        "sum_r": 0.0,
        "sum_f1": 0.0,
    }

    for i, item in enumerate(golden, 1):
        golden_required = set(item.get("required_skills", []))
        golden_bonus = set(item.get("bonus_skills", []))

        log.info("[%d/%d] %s — %s", i, len(golden), item["id"], item["job_title"])

        api_result = call_extract(item["raw_jd"], backend_url)
        if "error" in api_result:
            log.warning("  ❌ API 错误: %s", api_result["error"])
            aggregate["errors"] += 1
            results.append({"id": item["id"], "error": api_result["error"]})
            continue

        pred_required = skill_set(api_result.get("required_skills", []))
        pred_bonus = skill_set(api_result.get("preferred_skills", []))

        # 必需技能 F1（主要评估指标）
        f1_req = compute_f1(pred_required, golden_required)
        # 加分技能 F1（辅助指标）
        f1_bonus = compute_f1(pred_bonus, golden_bonus)

        log.info(
            "  required: P=%.2f R=%.2f F1=%.2f (%d 命中 / %d 预测 / %d 真值)",
            f1_req["precision"], f1_req["recall"], f1_req["f1"],
            f1_req["tp"], len(pred_required), len(golden_required),
        )

        results.append({
            "id": item["id"],
            "job_title": item["job_title"],
            "required": f1_req,
            "bonus": f1_bonus,
            "pred_required_count": len(pred_required),
            "golden_required_count": len(golden_required),
        })

        aggregate["total"] += 1
        aggregate["sum_p"] += f1_req["precision"]
        aggregate["sum_r"] += f1_req["recall"]
        aggregate["sum_f1"] += f1_req["f1"]

    n = aggregate["total"] or 1
    macro_f1 = aggregate["sum_f1"] / n
    has_errors = aggregate["errors"] > 0
    f1_met = macro_f1 >= 0.80
    summary = {
        "total_evaluated": aggregate["total"],
        "errors": aggregate["errors"],
        "macro_precision": aggregate["sum_p"] / n,
        "macro_recall": aggregate["sum_r"] / n,
        "macro_f1": macro_f1,
        "target_f1": 0.80,  # M2 验收阈值
        "passed": f1_met and not has_errors,
        "per_item": results,
    }
    return summary


def main() -> int:
    p = argparse.ArgumentParser(prog="w3-golden")
    p.add_argument("--max", type=int, default=50, help="最多跑多少条")
    p.add_argument("--backend", default=DEFAULT_BACKEND)
    p.add_argument("--report", default="crawler/output/w3_golden_report.json")
    args = p.parse_args()

    log.info("=== W3 Golden Set 验证启动 ===")
    log.info("backend: %s, max: %d", args.backend, args.max)

    # 连通性检查
    try:
        httpx.get(f"{args.backend}/api/v1/health", timeout=5.0).raise_for_status()
    except Exception as e:
        log.error("❌ backend 不通: %s", e)
        return 1

    summary = evaluate_golden(args.max, args.backend)

    log.info("=" * 50)
    log.info("Golden Set 验证完成")
    log.info("  evaluated: %d / errors: %d", summary["total_evaluated"], summary["errors"])
    log.info("  Macro Precision: %.4f", summary["macro_precision"])
    log.info("  Macro Recall:    %.4f", summary["macro_recall"])
    log.info("  Macro F1:        %.4f (target=%.2f)", summary["macro_f1"], summary["target_f1"])
    log.info("  Result:          %s", "✅ PASS" if summary["passed"] else "❌ FAIL")
    log.info("=" * 50)

    report_path = Path(args.report)
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("详细报告: %s", report_path)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
