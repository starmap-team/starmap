---
plan: 04-02
phase: 04-dataflow
status: complete
requirements:
  - EVAL-01
  - EVAL-03
  - EVAL-04
---

# Plan 04-02 Summary: EVAL-01/03/04 — quality_report.py --ci 子命令

## What was built

为 `scripts/quality_report.py` 添加了 `--ci` 子命令（D-05），输出 git HEAD + 三方准确率 markdown + JSON（D-07），任一指标 fail 则 exit 1（D-08）。

## Changes

### scripts/quality_report.py
- `main()`: 添加 `--ci` argparse 参数
- CI 模式：获取 `git rev-parse --short HEAD`，添加 `git_head` 字段到报告
- CI 模式：markdown 输出添加 `> CI Run: {git_hash}` 行
- CI 模式：同时输出 `quality_report_ci.json`（含 git_head 字段）
- CI 模式：遍历 `report["metrics"]`，任一 `status == "fail"` 则 `sys.exit(1)`，否则 `sys.exit(0)`
- 添加 `import subprocess`

## Verification

- `python scripts/quality_report.py --ci --golden evaluation/ --system evaluation/ --output scripts/reports/` 正常执行
- `scripts/reports/quality_report_ci.json` 包含 `"git_head": "a68cb9a"`
- `scripts/reports/quality_report.md` 包含 `> CI Run: a68cb9a`
- 退出码为 1（无数据文件时指标全 fail，符合预期）
- `ruff check scripts/quality_report.py` 无错误

## Key files

- `scripts/quality_report.py` — --ci 子命令 + git HEAD + exit 策略

## Deviations

None — implementation matches D-05~D-08 exactly.
