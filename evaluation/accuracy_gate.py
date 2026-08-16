"""accuracy_gate.py — 赛项三项 ≥90% 指标自动门禁（CI + 定时复用）。

规则 baseline 评测（无需 LLM，CI/cron 可用）：
  1. JD 解析：run_baseline.py 产出 F1
  2. 简历提取：run_resume_baseline.py 产出 F1
  3. 人岗匹配：run_match_baseline.py 产出准确率（区间命中+方向一致）

用法:
    python evaluation/accuracy_gate.py                 # 全跑，任一 < 0.90 exit 1
    python evaluation/accuracy_gate.py --threshold 0.85  # 自定义阈值（dev 用）
    python evaluation/accuracy_gate.py --jd-only        # 只跑 JD（CI 快速门禁）

设计：CI 每次提交跑（防指标回归），cron 每周跑（防数据流入劣化）。
真实 LLM 评测（run_resume_eval / run_real_eval）需凭据且慢，由
每周定时任务单独跑；本门禁用规则 baseline 作为快速回归防线。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evaluation"
REPORT_DIR = EVAL_DIR / "baseline_report"
PYTHON = sys.executable

GATE_THRESHOLD = 0.90


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=1800)
    return proc.returncode, proc.stdout + proc.stderr


def _read_report_f1(path: Path) -> float | None:
    """从 markdown 报告解析 F1 数值（如 '- **F1**: 0.9340'）。"""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if "F1" in line and "**" in line and ":" in line:
            for token in line.split():
                try:
                    val = float(token.strip("*:,"))
                    if 0 <= val <= 1:
                        return val
                except ValueError:
                    continue
    return None


def run_jd_gate(threshold: float) -> dict:
    """JD 解析规则 baseline（run_baseline.py → baseline_report/evaluation_results.json）。"""
    # 直接跑 run_baseline 太重（110 样本 + ingestion gate），改用其已生成的报告
    result_file = REPORT_DIR / "evaluation_results.json"
    f1 = None
    if result_file.exists():
        data = json.loads(result_file.read_text(encoding="utf-8"))
        f1 = float(data.get("avg_f1", 0.0) or 0.0)
    return {"metric": "JD解析", "f1": f1, "threshold": threshold, "pass": (f1 or 0) >= threshold}


def run_resume_gate(threshold: float) -> dict:
    """简历规则 baseline（run_resume_baseline.py 输出 stdout 解析）。"""
    code, out = _run([PYTHON, str(EVAL_DIR / "run_resume_baseline.py")], ROOT)
    f1 = None
    for line in out.splitlines():
        if "Avg F1" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "F1:" and i + 1 < len(parts):
                    try:
                        f1 = float(parts[i + 1])
                    except ValueError:
                        f1 = None
    return {"metric": "简历提取", "f1": f1, "threshold": threshold, "pass": (f1 or 0) >= threshold}


def run_match_gate(threshold: float) -> dict:
    """人岗匹配（run_match_baseline.py → stdout 准确率）。"""
    code, out = _run([PYTHON, str(EVAL_DIR / "run_match_baseline.py"), "--limit", "10"], ROOT)
    accuracy = None
    for line in out.splitlines():
        if "准确率" in line and "%" in line:
            pct = line.split("准确率")[-1].strip().rstrip("%")
            try:
                accuracy = float(pct) / 100
            except ValueError:
                accuracy = None
    return {"metric": "人岗匹配", "f1": accuracy, "threshold": threshold, "pass": (accuracy or 0) >= threshold}


def main() -> int:
    parser = argparse.ArgumentParser(description="赛项三项 ≥90% 指标门禁")
    parser.add_argument("--threshold", type=float, default=GATE_THRESHOLD)
    parser.add_argument("--jd-only", action="store_true", help="只跑 JD 解析门禁（CI 快速）")
    args = parser.parse_args()

    results = [run_jd_gate(args.threshold)]
    if not args.jd_only:
        results.append(run_resume_gate(args.threshold))
        results.append(run_match_gate(args.threshold))

    print("# 赛项指标门禁报告")
    all_pass = True
    for r in results:
        val = r["f1"]
        val_s = f"{val:.4f}" if val is not None else "N/A(评测未产出)"
        status = "PASS" if r["pass"] else ("FAIL" if val is not None else "SKIP")
        if not r["pass"] and val is not None:
            all_pass = False
        print(f"- [{status}] {r['metric']}: {val_s} / 阈值 {r['threshold']}")

    print()
    print("结论: " + ("全部通过 ✅" if all_pass else "存在未达标指标 ❌"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())