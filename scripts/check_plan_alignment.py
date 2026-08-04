"""check_plan_alignment.py — 计划书 vs 代码 机械事实对比（v3.0 附录F 迭代协议配套）。

校验三类可机械验证的事实，输出偏差清单，防止计划与代码再漂移：
  1. Golden Set 规模 vs 计划 §14.2 目标（JD>=100 / 简历>=50 / 匹配>=100）
  2. OpenAPI 契约端点完整性（实现已存在、契约必须收录的关键端点）
  3. Alembic 迁移链规模（报告口径，漂移预警）

用法:
    python scripts/check_plan_alignment.py            # 报告模式，恒 exit 0
    python scripts/check_plan_alignment.py --strict   # 任一失败 exit 1（CI 门禁用）

ponytail: 原型只做机械事实比对；语义级偏差（公式族/策略）由附录E 裁决表人工维护。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 计划 §14.2.1 目标（2026-08-05 实测状态见附录E DEV-04）
GOLDEN_TARGETS = {
    "evaluation/golden_set.jsonl": ("JD-Golden", 100),
    "evaluation/golden_set_resume.jsonl": ("Resume-Golden", 50),
    "evaluation/golden_set_match.jsonl": ("Match-Golden", 100),
}

# NEW-12：实现已存在、契约必须收录的端点（缺失即契约漂移）
REQUIRED_CONTRACT_PATHS = [
    "/health-monitor/sources",
    "/import/jd",
    "/admin/data-truth",
    "/positions/industries",
]


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def check_golden_sets() -> list[tuple[bool, str]]:
    results = []
    for rel, (name, target) in GOLDEN_TARGETS.items():
        actual = count_jsonl_lines(ROOT / rel)
        ok = actual >= target
        results.append((ok, f"{name}: 实际 {actual} 条 / 计划 >={target} 条 [{'达标' if ok else '缺口 ' + str(target - actual)}]"))
    return results


def openapi_paths() -> set[str]:
    yaml_file = ROOT / "starmap-contracts/openapi.yaml"
    if not yaml_file.exists():
        return set()
    paths: set[str] = set()
    in_paths = False
    for line in yaml_file.read_text(encoding="utf-8").splitlines():
        if re.match(r"^paths:\s*$", line):
            in_paths = True
            continue
        if in_paths:
            m = re.match(r"^  (/[^:]*):\s*$", line)
            if m:
                paths.add(m.group(1))
            elif re.match(r"^\S", line):  # 下一个顶层键
                in_paths = False
    return paths


def check_contract() -> list[tuple[bool, str]]:
    paths = openapi_paths()
    results = [(bool(paths), f"openapi.yaml 收录 {len(paths)} 个 path（0 = 解析失败或缺文件）")]
    for p in REQUIRED_CONTRACT_PATHS:
        ok = p in paths
        results.append((ok, f"契约端点 {p}: {'已收录' if ok else '缺失（NEW-12 漂移）'}"))
    return results


def check_migrations() -> list[tuple[bool, str]]:
    versions = ROOT / "backend/alembic/versions"
    count = len(list(versions.glob("*.py"))) if versions.exists() else 0
    # 报告口径：只报数量与最新编号，不做硬门禁
    latest = sorted(versions.glob("[0-9]*.py"))[-1].name if versions.exists() and list(versions.glob("[0-9]*.py")) else "n/a"
    return [(True, f"Alembic 迁移 {count} 个，最新编号 {latest}（口径报告，非门禁）")]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台防乱码
    strict = "--strict" in sys.argv
    sections = {
        "Golden Set 规模 vs 计划 §14.2": check_golden_sets(),
        "OpenAPI 契约完整性": check_contract(),
        "迁移链规模": check_migrations(),
    }
    failures = 0
    print("# Plan-vs-Code 对比报告")
    print(f"生成方式: scripts/check_plan_alignment.py{' --strict' if strict else ''}\n")
    for title, results in sections.items():
        print(f"## {title}")
        for ok, msg in results:
            mark = "PASS" if ok else "FAIL"
            if not ok:
                failures += 1
            print(f"- [{mark}] {msg}")
        print()
    print(f"结论: {failures} 项失败" if failures else "结论: 全部通过")
    if strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
