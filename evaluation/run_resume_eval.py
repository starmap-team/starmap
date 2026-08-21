"""简历提取准确率评测 runner — P0-2 赛项实用价值指标。

调用真实 LLM 抽取管线（app.core.extraction.jd_extract.extract_from_jd，与
线上 /resume/upload 同路径）对 golden_set_resume.jsonl（50 份简历）做
技能提取，compute F1 并与赛项 ≥90% 门禁比对，输出报告。

对比 run_resume_baseline.py（纯关键字，F1=0.78 不过线），本 runner 走
真实 LLM 语义理解，能处理「熟练掌握Python」等非字面表述，是赛项
「简历提取准确率 ≥90%」的可信证据。

用法:
    cd backend
    poetry run python ../evaluation/run_resume_eval.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.core.extraction.resume_eval import GoldenSample, evaluate_f1
from app.core.extraction.jd_extract import extract_from_jd

GOLDEN_FILE = BASE_DIR / "evaluation" / "golden_set_resume.jsonl"
REPORT_DIR = BASE_DIR / "evaluation" / "baseline_report"


def load_golden_jsonl(path: Path) -> list[GoldenSample]:
    """golden_set_resume.jsonl 是 JSONL（每行 input/expected），build_golden_set
    期望 JSON 数组 —— 这里按 JSONL 逐行解析并适配 GoldenSample 字段。"""
    samples: list[GoldenSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        # golden expected.skills 是字符串数组；GoldenSample 期望 [{name:...}]
        raw_skills = entry.get("expected", {}).get("skills", [])
        skill_objs = [
            {"name": s} if isinstance(s, str) else s for s in raw_skills
        ]
        samples.append(GoldenSample(
            resume_text=entry.get("input", ""),
            expected_skills=skill_objs,
            position=entry.get("expected", {}).get("job_title", ""),
            sample_id=entry.get("id", f"sample_{len(samples):03d}"),
        ))
    return samples


def _skill_names(container: list) -> set[str]:
    out: set[str] = set()
    for s in container or []:
        name = s.get("name", "") if isinstance(s, dict) else str(s)
        if name:
            out.add(name)
    return out


async def _evaluate(samples: list, dry_run: bool) -> dict:
    predictions: list[set[str]] = []
    errors: list[dict] = []
    for i, sample in enumerate(samples):
        if dry_run:
            predictions.append(set())
            print(f"  [dry] {sample.sample_id} -> (待抽取)")
            continue
        try:
            result = await extract_from_jd(sample.resume_text, options={"source": "resume"})
            if result.get("success") and result.get("data"):
                data = result["data"]
                predictions.append(
                    _skill_names(data.get("required_skills", []))
                    | _skill_names(data.get("preferred_skills", []))
                )
            else:
                predictions.append(set())
                errors.append({"sample_id": sample.sample_id, "error": result.get("error", "?"), "warnings": result.get("warnings", [])})
        except Exception as exc:  # noqa: BLE001
            predictions.append(set())
            errors.append({"sample_id": sample.sample_id, "error": str(exc)})
        if (i + 1) % 5 == 0:
            print(f"  进度 {i+1}/{len(samples)}")

    metrics = evaluate_f1(predictions, samples)
    return {"metrics": metrics, "errors": errors}


def _write_report(summary: dict, total: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    m = summary["metrics"]
    f1 = m.get("f1", 0.0)
    lines = [
        "# 简历提取准确率评测报告（真实 LLM 管线）",
        "",
        f"- **样本数**: {total}",
        f"- **Precision**: {m.get('precision', 0.0):.4f}",
        f"- **Recall**: {m.get('recall', 0.0):.4f}",
        f"- **F1**: {f1:.4f}",
        f"- **门禁**: ≥90% → {'✅ PASS' if f1 >= 0.9 else '❌ FAIL'}",
        "",
        "> 评测走真实 LLM 抽取管线（extract_from_jd，与 /resume/upload 同路径），",
        "> 非关键字 baseline。对比 run_resume_baseline.py（关键字 F1≈0.78）。",
        "",
        "## 抽取错误样本",
        "",
    ]
    for e in summary["errors"]:
        lines.append(f"- `{e['sample_id']}`: {e['error']} {e.get('warnings', [])}")
    if not summary["errors"]:
        lines.append("- 无")
    out = REPORT_DIR / "resume_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="简历提取准确率评测 (P0-2, 真实 LLM)")
    parser.add_argument("--limit", type=int, default=None, help="最多样本数")
    parser.add_argument("--dry-run", action="store_true", help="只遍历不调 LLM")
    args = parser.parse_args()

    samples = load_golden_jsonl(GOLDEN_FILE)
    if args.limit:
        samples = samples[: args.limit]
    print(f"[resume-eval] 加载 {len(samples)} 份简历 golden" + ("（dry-run）" if args.dry_run else ""))

    summary = asyncio.run(_evaluate(samples, args.dry_run))
    if args.dry_run:
        return
    _write_report(summary, len(samples))
    m = summary["metrics"]
    print(f"[resume-eval] {len(samples)} 样本 F1={m.get('f1', 0):.4f} "
          f"P={m.get('precision', 0):.4f} R={m.get('recall', 0):.4f}")


if __name__ == "__main__":
    main()