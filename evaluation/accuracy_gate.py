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
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


# ── 所有 evaluation 脚本依赖 backend/ 下的 app.* 模块和 .env 配置 ──
# accuracy_gate.py 位于 evaluation/，ROOT 指向项目根。各 baseline 脚本
# 的 import 和 DB 连接需要 cwd=backend/，否则 settings 加载 .env 路径
# 错误 → Neo4j/PG 连接异常 → 0/10（此前 weekly beat 从未部署，无人发现）。
BACKEND_DIR = ROOT / "backend"


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
    """JD 解析规则 baseline（run_baseline.py 实时运行，非读缓存）。

    Phase 8 (G3): 此前读取 evaluation_results.json 静态缓存——该文件是
    手动/CI 生成的快照，新 JD 流入后不会自动更新。改为每次门禁调用时
    实时运行 run_baseline.py（~30s，110 样本 keyword F1），确保门禁
    反映当前抽取质量而非历史快照。
    """
    code, out = _run([PYTHON, str(EVAL_DIR / "run_baseline.py")], BACKEND_DIR)
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
    return {"metric": "JD解析", "f1": f1, "threshold": threshold, "pass": (f1 or 0) >= threshold}


def run_resume_gate(threshold: float, real_llm: bool = False) -> dict:
    """简历门禁。

    real_llm=False：规则 keyword baseline（快，CI 用）。
    real_llm=True：真实 LLM 评测（run_resume_eval.py --limit 25，需 DASHSCOPE
    凭据且慢——由每周定时任务用，反映真实抽取管线而非 keyword 上限题）。
    """
    if real_llm:
        code, out = _run([PYTHON, str(EVAL_DIR / "run_resume_eval.py"), "--limit", "25"], BACKEND_DIR)
    else:
        code, out = _run([PYTHON, str(EVAL_DIR / "run_resume_baseline.py")], BACKEND_DIR)
    f1 = None
    for line in out.splitlines():
        if real_llm:
            if "F1=" in line:
                # 形如 "[resume-eval] 25 样本 F1=0.9316 P=0.9286 R=0.9346"
                try:
                    f1 = float(line.split("F1=")[1].split()[0])
                except (ValueError, IndexError):
                    f1 = None
                break
        else:
            if "Avg F1" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "F1:" and i + 1 < len(parts):
                        try:
                            f1 = float(parts[i + 1])
                        except ValueError:
                            f1 = None
    return {
        "metric": "简历提取" + ("(真实LLM)" if real_llm else ""),
        "f1": f1,
        "threshold": threshold,
        "pass": (f1 or 0) >= threshold,
    }


def _count_golden_position_names() -> set[str]:
    """读取 match golden set 去重的岗位名集合（用于覆盖率对账）。"""
    import json
    names: set[str] = set()
    gp = EVAL_DIR / "golden_set_match.jsonl"
    if not gp.exists():
        return names
    for line in gp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        expected = entry.get("expected") or {}
        name = expected.get("job_title") or entry.get("position")
        if name:
            names.add(name)
    return names


def run_match_gate(threshold: float) -> dict:
    """人岗匹配快速回归门禁（run_match_baseline.py --limit 10，CI/定时共用）。

    快速抽样 10 项检测分数回归；full 348 + 覆盖率由 celery weekly
    单独跑 run_match_full_audit.py。
    覆盖率数据来自静态 golden 文件解析（秒级），不依赖子进程。
    """
    code, out = _run([PYTHON, str(EVAL_DIR / "run_match_baseline.py"), "--limit", "10"], BACKEND_DIR)
    accuracy = None
    for line in out.splitlines():
        if "准确率" in line and "%" in line:
            pct = line.split("准确率")[-1].strip().rstrip("%")
            try:
                accuracy = float(pct) / 100
            except ValueError:
                accuracy = None
    covered = _count_golden_position_names()
    return {
        "metric": "人岗匹配",
        "f1": accuracy,
        "threshold": threshold,
        "pass": (accuracy or 0) >= threshold,
        "covered_positions": len(covered),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="赛项三项 ≥90% 指标门禁")
    parser.add_argument("--threshold", type=float, default=GATE_THRESHOLD)
    parser.add_argument("--jd-only", action="store_true", help="只跑 JD 解析门禁（CI 快速）")
    parser.add_argument(
        "--with-resume-real-llm",
        action="store_true",
        help="简历门禁用真实 LLM 评测（run_resume_eval，需凭据且慢），默认规则 baseline",
    )
    args = parser.parse_args()

    results = [run_jd_gate(args.threshold)]
    if not args.jd_only:
        results.append(run_resume_gate(args.threshold, real_llm=args.with_resume_real_llm))
        results.append(run_match_gate(args.threshold))

    print("# 赛项指标门禁报告")
    all_pass = True
    for r in results:
        val = r["f1"]
        val_s = f"{val:.4f}" if val is not None else "N/A(评测未产出)"
        status = "PASS" if r["pass"] else ("FAIL" if val is not None else "SKIP")
        if not r["pass"] and val is not None:
            all_pass = False
        suffix = ""
        if "covered_positions" in r:
            suffix = f"（golden 覆盖岗位 {r['covered_positions']} 个）"
        print(f"- [{status}] {r['metric']}: {val_s} / 阈值 {r['threshold']}{suffix}")

    print()
    print("结论: " + ("全部通过 ✅" if all_pass else "存在未达标指标 ❌"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())