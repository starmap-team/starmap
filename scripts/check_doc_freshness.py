#!/usr/bin/env python3
"""check_doc_freshness.py — 文档新鲜度本地校验脚本

目的:在没有 CI 跑 `.github/workflows/doc-lint.yml` 的本地环境下,也能快速发现
      文档与代码现状的漂移。配合 CI 任务使用,定位更快、反馈更直接。

检查项(与 doc-lint.yml 对齐):
  1. OpenAPI 端点数:文档自称 vs 契约 YAML grep '^  /' 数
  2. pytest passed 数字:README/CLAUDE/ONBOARDING 自称 vs 实际 collect-only 数
  3. vitest passed 数字:同上(vitest 端)
  4. golden_set 条数:evaluation/README/CLAUDE 自称 vs jsonl 行数
  5. audit/ 目录引用:README/ONBOARDING/standards 是否引用已删除目录
  6. .gitignore 'docs/archive/' 与 CLAUDE.md 规则的一致性

用法:
  python scripts/check_doc_freshness.py [--strict] [--skip-pytest]

退出码:
  0 = 全部 OK 或仅 INFO
  1 = 至少 1 个 HIGH(默认非严格模式)
  2 = 至少 1 个 ERROR(脚本本身故障或数据无法读取)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOC_FILES = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "ONBOARDING.md",
)


@dataclass
class Finding:
    level: str  # OK / INFO / HIGH / ERROR
    name: str
    msg: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, name: str, msg: str) -> None:
        self.findings.append(Finding(level, name, msg))

    @property
    def counts(self) -> dict[str, int]:
        c = {"OK": 0, "INFO": 0, "HIGH": 0, "ERROR": 0}
        for f in self.findings:
            c[f.level] = c.get(f.level, 0) + 1
        return c

    def print_table(self) -> None:
        print()
        print("=" * 70)
        print("文档新鲜度本地检查报告")
        print("=" * 70)
        for f in self.findings:
            tag = f"[{f.level:>5}]"
            print(f"{tag} {f.name:<22} {f.msg}")
        print("-" * 70)
        c = self.counts
        print(f"HIGH={c['HIGH']}  INFO={c['INFO']}  OK={c['OK']}  ERROR={c['ERROR']}")
        print("=" * 70)


# ---- 检查函数 ----


def check_openapi_paths(report: Report) -> None:
    """文档自述的 openapi 路径数 vs 契约实际端点数。"""
    yaml_path = ROOT / "starmap-contracts/openapi.yaml"
    if not yaml_path.exists():
        report.add("ERROR", "openapi_paths", f"契约文件不存在: {yaml_path}")
        return
    actual = sum(
        1
        for line in yaml_path.read_text(encoding="utf-8").splitlines()
        if re.match(r"^  /", line)
    )

    claimed: int | None = None
    claimed_src: str | None = None
    patterns = [
        r"(\d+)\s*(?:paths|端点|endpoints|paths?)",
        r"openapi[^.\n]{0,30}?(\d+)",
        r"(\d+)\s*(?:条|个)?\s*(?:API|api|paths)",
    ]
    for f in DOC_FILES:
        p = ROOT / f
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        for pat in patterns:
            for m in re.finditer(pat, txt, re.IGNORECASE):
                try:
                    n = int(m.group(1))
                    if 50 <= n <= 500:
                        claimed = n
                        claimed_src = f
                        break
                except ValueError:
                    continue
            if claimed is not None:
                break
        if claimed is not None:
            break

    if claimed is None:
        report.add("INFO", "openapi_paths", f"yaml 实际 {actual} 条;文档未声明具体数")
        return

    delta = abs(claimed - actual)
    if delta > 5:
        report.add(
            "HIGH",
            "openapi_paths",
            f"{claimed_src} 写 {claimed},yaml 实际 {actual}(delta {delta})",
        )
    else:
        report.add("OK", "openapi_paths", f"{claimed_src} 写 {claimed} ≈ yaml 实际 {actual}")


def check_pytest_count(report: Report, run_real: bool) -> None:
    """文档自述的 pytest passed 数字 vs 实际 collect-only 数。"""
    claimed: int | None = None
    claimed_src: str | None = None
    for f in DOC_FILES:
        p = ROOT / f
        if not p.exists():
            continue
        m = re.search(r"(\d{3,5})\s*(?:passed|pass)", p.read_text(encoding="utf-8"), re.IGNORECASE)
        if m:
            claimed = int(m.group(1))
            claimed_src = f
            break

    if claimed is None:
        report.add("INFO", "pytest_passed", "文档未声明 pytest 数字,跳过")
        return

    if not run_real:
        report.add("INFO", "pytest_passed", f"最后文档声称 {claimed}(跳过实际 collect,加 --run-pytest 启用)")
        return

    # 实际跑 pytest --collect-only
    backend = ROOT / "backend"
    if not (backend / "pyproject.toml").exists():
        report.add("ERROR", "pytest_passed", f"找不到 backend/pyproject.toml,跳过实际跑")
        return
    try:
        out = subprocess.run(
            ["poetry", "run", "pytest", "--collect-only", "-q"],
            cwd=str(backend),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        report.add("ERROR", "pytest_passed", "pytest collect 超时(>120s)")
        return
    except FileNotFoundError:
        report.add("ERROR", "pytest_passed", "找不到 poetry,跳过实际跑")
        return

    if out.returncode != 0:
        report.add("ERROR", "pytest_passed", f"pytest collect 失败: {out.stderr[:200]}")
        return

    actual = len([line for line in out.stdout.splitlines() if "::" in line and "<Function" not in line])
    if actual == 0:
        # fallback: 全行数统计
        actual = len(out.stdout.splitlines())

    delta = abs(claimed - actual)
    if delta > 5:
        report.add(
            "HIGH",
            "pytest_passed",
            f"{claimed_src} 写 {claimed},collect 实际 {actual}(delta {delta})",
        )
    else:
        report.add("OK", "pytest_passed", f"{claimed_src} 写 {claimed} ≈ collect 实际 {actual}")


def check_vitest_count(report: Report, run_real: bool) -> None:
    """文档自述的 vitest passed 数字 vs 实际 list 数。"""
    claimed: int | None = None
    claimed_src: str | None = None
    for f in DOC_FILES:
        p = ROOT / f
        if not p.exists():
            continue
        m = re.search(r"(\d{3,5})\s*(?:vitest|tests?)", p.read_text(encoding="utf-8"), re.IGNORECASE)
        if m and "vitest" in p.read_text(encoding="utf-8")[max(0, m.start() - 30) : m.start()].lower():
            claimed = int(m.group(1))
            claimed_src = f
            break

    if claimed is None:
        report.add("INFO", "vitest_passed", "文档未声明 vitest 数字,跳过")
        return

    if not run_real:
        report.add("INFO", "vitest_passed", f"最后文档声称 {claimed}(跳过实际 list,加 --run-vitest 启用)")
        return

    frontend = ROOT / "frontend"
    if not (frontend / "package.json").exists():
        report.add("ERROR", "vitest_passed", "找不到 frontend/package.json,跳过实际跑")
        return
    try:
        out = subprocess.run(
            ["npx", "vitest", "list", "--reporter=basic"],
            cwd=str(frontend),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        report.add("ERROR", "vitest_passed", f"vitest list 失败: {exc}")
        return

    if out.returncode != 0:
        report.add("ERROR", "vitest_passed", f"vitest list 失败: {out.stderr[:200]}")
        return

    actual = len(out.stdout.splitlines())
    delta = abs(claimed - actual)
    if delta > 5:
        report.add(
            "HIGH",
            "vitest_passed",
            f"{claimed_src} 写 {claimed},list 实际 {actual}(delta {delta})",
        )
    else:
        report.add("OK", "vitest_passed", f"{claimed_src} 写 {claimed} ≈ list 实际 {actual}")


def check_golden_set(report: Report) -> None:
    """evaluation/golden_set.jsonl 行数 vs 文档自述。"""
    p = ROOT / "evaluation/golden_set.jsonl"
    if not p.exists():
        report.add("ERROR", "golden_set", "找不到 evaluation/golden_set.jsonl")
        return
    actual = sum(1 for _ in p.open(encoding="utf-8"))

    claimed: int | None = None
    claimed_src: str | None = None
    for f in DOC_FILES:
        fp = ROOT / f
        if not fp.exists():
            continue
        m = re.search(r"golden[_-]?set[^.\n]{0,30}?(\d+)", fp.read_text(encoding="utf-8"), re.IGNORECASE)
        if m:
            claimed = int(m.group(1))
            claimed_src = f
            break

    if claimed is None:
        report.add("INFO", "golden_set", f"jsonl 实际 {actual} 行;文档未声明")
        return

    if claimed != actual:
        report.add(
            "HIGH",
            "golden_set",
            f"{claimed_src} 写 {claimed},jsonl 实际 {actual}(delta {abs(claimed - actual)})",
        )
    else:
        report.add("OK", "golden_set", f"{claimed_src} 写 {claimed} == jsonl 实际 {actual}")


def check_audit_dir_stale(report: Report) -> None:
    """README/ONBOARDING/standards 是否仍引用已删除的 audit/ 目录。"""
    audit_mentions = subprocess.run(
        ["git", "grep", "-lE", r"audit/(00-summary|99-risk|98-ai)"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    ).stdout.strip().splitlines()
    if audit_mentions:
        report.add(
            "HIGH",
            "audit_dir_stale",
            f"audit/ 已不存在,{len(audit_mentions)} 个文件仍引用: {audit_mentions[:5]}",
        )
    else:
        report.add("OK", "audit_dir_stale", "无陈旧 audit/ 引用")


def _md_link_targets(content: str, target_basename: str) -> list[str]:
    """仅返回 markdown 链接中真实指向 target_basename 的命中位置。

    形式:`](CLAUDE.md)` 或 `](CLAUDE.md#...)` 或 `](CLAUDE.md?...)`。
    文字提及 `CLAUDE.md`(在表格、列表项、纯文本)不算 — 它们没有 404 风险。
    """
    pat = re.compile(
        r"""\]\(
            [^)\s]*            # 任意路径(允许 ../docs/、相对路径等)
            """ + re.escape(target_basename) + r"""
            (?:\)|\#|\?)        # 链接闭合或锚点或查询
        """,
        re.VERBOSE,
    )
    return pat.findall(content)


def check_gitignore_consistency(report: Report) -> None:
    """检测 .gitignore 把 CLAUDE.md / docs/archive/ 排除 — 与文档是否真的**链接**到它们。"""
    gi = ROOT / ".gitignore"
    if not gi.exists():
        report.add("INFO", "gitignore_consistency", ".gitignore 不存在")
        return
    text = gi.read_text(encoding="utf-8")
    rules: list[str] = []
    if re.search(r"^docs/archive/$", text, re.MULTILINE):
        rules.append("docs/archive/")
    if re.search(r"^CLAUDE\.md$", text, re.MULTILINE):
        rules.append("CLAUDE.md")

    if not rules:
        report.add("OK", "gitignore_consistency", "无 docs/archive / CLAUDE.md ignore 规则")
        return

    # 仅检测 markdown 链接形式 — 表格/列表中的纯文字提及不算悬挂引用
    dangling: list[str] = []
    for f in ("README.md", "AGENTS.md", "ONBOARDING.md"):
        fp = ROOT / f
        if not fp.exists():
            continue
        content = fp.read_text(encoding="utf-8")
        if "CLAUDE.md" in rules and _md_link_targets(content, "CLAUDE.md"):
            dangling.append(f"{f} -> CLAUDE.md (markdown link)")
        if "docs/archive/" in rules and _md_link_targets(content, "docs/archive/"):
            dangling.append(f"{f} -> docs/archive/ (markdown link)")

    if dangling:
        report.add(
            "HIGH",
            "gitignore_consistency",
            f"已 ignore 但有 markdown 链接指向: {dangling}",
        )
    else:
        report.add(
            "OK",
            "gitignore_consistency",
            f"已 ignore: {rules};无 markdown 链接悬挂(纯文字提及不计)",
        )


# ---- 入口 ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="文档新鲜度本地检查")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="HIGH 也让 exit code 非 0(默认仅 ERROR 让脚本失败)",
    )
    parser.add_argument("--run-pytest", action="store_true", help="实际跑 pytest collect")
    parser.add_argument("--run-vitest", action="store_true", help="实际跑 vitest list")
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON(给脚本/CI 调用方)",
    )
    args = parser.parse_args(argv)

    report = Report()
    check_openapi_paths(report)
    check_pytest_count(report, run_real=args.run_pytest)
    check_vitest_count(report, run_real=args.run_vitest)
    check_golden_set(report)
    check_audit_dir_stale(report)
    check_gitignore_consistency(report)

    if args.json:
        print(
            json.dumps(
                {
                    "findings": [f.__dict__ for f in report.findings],
                    "counts": report.counts,
                },
                ensure_ascii=False,
            )
        )
    else:
        report.print_table()

    c = report.counts
    if c["ERROR"] > 0:
        return 2
    if args.strict and c["HIGH"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())