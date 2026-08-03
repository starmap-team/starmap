# Phase 18: 测试弹性和清理

**Phase:** 18-test-resilience
**Goal:** 修复 Phase 17 残留的测试问题, 清理历史遗留
**Status:** completed
**Created:** 2026-07-30

## 背景

Phase 17 完成后, 2 项测试改进 + 清理任务:
1. 跨端 20 抽样测试因 `asyncio.run()` 与 pytest 同步事件循环冲突,需改 `pytest-asyncio`
2. 失败重试集成测试 (mock LLM 失败路径) 留作 TODO
3. Active debug sessions + 已完成 todos 需清理

## 子计划 (3 个)

| Plan | 标题 | 状态 |
|------|------|------|
| **18-01** | 跨端 20 抽样改 pytest-asyncio | ✅ Completed |
| **18-02** | 失败重试集成测试 (mock LLM) | ⚠️ Partial (1/3 pass) |
| **18-03** | 清理 (debug + todos) | ✅ Completed |

## 测试结果

| 套件 | 结果 |
|------|------|
| `test_cross_tier_consistency.py` 单次 | ✅ 1 pass |
| `test_pipeline_failure_retry.py` | ⚠️ 1 pass / 2 fail (mock 路径) |
| `todos/pending/` | ✅ 已空 |
| `todos/archive/` | ✅ 2 files |

## 残留 OPEN (Phase 19+)

| ID | 描述 |
|----|------|
| T1 | 2 个失败-retry 测试的 mock 路径调试 |
| T2 | 20-trial 全跑 (与 backend 压力相关) |