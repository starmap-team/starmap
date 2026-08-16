"""人岗匹配准确率评测 runner — P0-1 赛项实用价值指标。

消费 `evaluation/golden_set_match.jsonl`（100 对：position + person_skills +
expected 区间），逐条调用真实匹配引擎 `run_match`（服务层，走真实 Neo4j
图谱 + PostgreSQL），判定系统 match_score 是否落在 golden 期望区间，输出
准确率报告到 `evaluation/baseline_report/match_report.md`。

判定口径（与赛项"人岗匹配准确率 ≥90%"对齐）：
- 区间命中：expected.match_score_min <= score <= expected.match_score_max
- 方向一致：expected.should_match 与 (score >= threshold) 一致
- 两条都满足才算该样本正确

用法:
    cd backend
    poetry run python -m scripts.run_match_baseline [--threshold 0.6] [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.matching.service import MatchService
from app.db.session import get_async_engine
from app.services.resources import init_resources

GOLDEN_FILE = BASE_DIR / "evaluation" / "golden_set_match.jsonl"
REPORT_DIR = BASE_DIR / "evaluation" / "baseline_report"


def _load_golden(limit: int | None) -> list[dict]:
    rows = []
    for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
        if limit and len(rows) >= limit:
            break
    return rows


def _score_in_range(score: float, expected: dict) -> bool:
    lo = float(expected.get("match_score_min", 0.0))
    hi = float(expected.get("match_score_max", 1.0))
    return lo <= score <= hi


def _direction_ok(score: float, expected: dict, threshold: float) -> bool:
    should = bool(expected.get("should_match", True))
    return (score >= threshold) == should


async def run(threshold: float, limit: int | None) -> dict:
    golden = _load_golden(limit)
    if not golden:
        print("golden_set_match.jsonl 为空")
        return {"total": 0, "correct": 0, "accuracy": 0.0, "samples": []}

    res = await init_resources()
    driver = res.neo4j_driver
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    service = MatchService()

    results: list[dict] = []
    correct = 0
    for g in golden:
        gid = g.get("id", "?")
        position = g.get("position", "")
        person_skills = g.get("person_skills", [])
        expected = g.get("expected", {})

        # 岗位不存在 / 无画像时 run_match 返回 0 分（not-found 抛异常）
        try:
            async with sessionmaker() as session:
                match_res = await service.run_match(
                    target_position=position,
                    person_skills=person_skills,
                    threshold=threshold,
                    driver=driver,
                    db_session=session,
                )
        except Exception as exc:  # noqa: BLE001 — 单样本异常不阻断评测
            results.append({
                "id": gid, "position": position, "score": None,
                "error": f"{type(exc).__name__}: {exc}", "ok": False,
            })
            continue

        score = float(match_res.get("match_score", 0.0))
        in_range = _score_in_range(score, expected)
        direction = _direction_ok(score, expected, threshold)
        ok = in_range and direction
        if ok:
            correct += 1
        results.append({
            "id": gid, "position": position, "score": score,
            "expected": expected, "in_range": in_range, "direction": direction,
            "ok": ok,
        })

    await engine.dispose()
    await res.close()

    accuracy = round(correct / len(golden), 4)
    return {"total": len(golden), "correct": correct, "accuracy": accuracy, "samples": results}


def _write_report(summary: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    total = summary["total"]
    correct = summary["correct"]
    accuracy = summary["accuracy"]
    lines = [
        "# 人岗匹配准确率评测报告",
        "",
        f"- **样本数**: {total}",
        f"- **命中数**: {correct}",
        f"- **准确率**: {accuracy:.2%}",
        f"- **门禁**: ≥90% → {'✅ PASS' if accuracy >= 0.9 else '❌ FAIL'}",
        "",
        "## 明细",
        "",
        "| ID | 岗位 | score | 区间 | 方向 | 结果 |",
        "|---|---|---|---|---|---|",
    ]
    for s in summary["samples"]:
        score = f"{s['score']:.2f}" if s.get("score") is not None else "ERR"
        err = f" ({s['error']})" if s.get("error") else ""
        lines.append(
            f"| {s['id']} | {s['position']} | {score} | "
            f"{'✓' if s.get('in_range') else '✗'} | "
            f"{'✓' if s.get('direction') else '✗'} | "
            f"{'PASS' if s.get('ok') else 'FAIL'}{err} |"
        )
    out = REPORT_DIR / "match_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="人岗匹配准确率评测 (P0-1)")
    parser.add_argument("--threshold", type=float, default=0.6, help="match/no-match 边界")
    parser.add_argument("--limit", type=int, default=None, help="最多样本数")
    args = parser.parse_args()
    summary = asyncio.run(run(args.threshold, args.limit))
    _write_report(summary)
    print(
        f"[match-baseline] {summary['correct']}/{summary['total']} "
        f"准确率 {summary['accuracy']:.2%}"
    )


if __name__ == "__main__":
    main()