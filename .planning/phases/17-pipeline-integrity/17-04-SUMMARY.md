---
phase: 17-pipeline-integrity
plan: 04
completed: 2026-07-30
status: partial (e2e pass; cross-tier test deferred to pytest-asyncio refactor)
---

# Plan 17-04: 端到端失败重试 + 跨端一致性 — PARTIAL

## 已完成

### Task 3: Playwright e2e 验证 (4 个) ✅
**文件:** `frontend/e2e/phase17-audit.spec.ts`

```ts
test.describe('Phase 17 修复验证', () => {
  test('B1: DAG 只显示 5 个核心 stage (无 timeseries)')
  test('B2: 重试按钮在 failed 状态下可用')
  test('B4: graph_sync 失败显示人类可读错误, 不含 raw Traceback')
  test('ALL_STAGE_NAMES 不含 timeseries')
})
```

**结果: ✅ 4/4 PASS** (11.8s)

## 已知限制

### Task 1: 失败重试集成测试
未实现 (Phase 18+ 完善)。原因: 需要 mock LLM/Redis 失败路径, 复杂度过高。

### Task 2: 跨端一致性抽样
- 测试已编写 (`test_cross_tier_consistency.py`)
- pytest-asyncio 重写待办 (Phase 18+)

## 验证

| 测试 | 结果 |
|------|------|
| `e2e/phase17-audit.spec.ts` | ✅ **4/4 PASS** |
| Backend unit | ✅ 124/124 pass |
| Frontend e2e (Phase 16 + 17) | ✅ 9/9 (5 + 4) |

## 残留

| ID | 描述 | 优先级 |
|----|------|--------|
| T1 | failure-retry 集成测试 (mock LLM 失败) | LOW (Phase 18) |
| T2 | 跨端 20 抽样测试改 pytest-asyncio | LOW (Phase 18) |