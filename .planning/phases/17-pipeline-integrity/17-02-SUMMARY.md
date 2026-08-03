---
phase: 17-pipeline-integrity
plan: 02
completed: 2026-07-30
status: completed
---

# Plan 17-02: 修复重试按钮 (B2) — COMPLETED

## 已完成

### Task 1: usePipelineMonitor.ts currentRunId 改 last_run.id ✅
**文件:** `frontend/src/composables/usePipelineMonitor.ts:437`

```ts
// Phase 17-02 (Fix B2): 改用 last_run.id fallback, 让 failed/cancelled run 也能重试
const currentRunId = computed(() => {
  return pipeline.pipelineStatus?.last_run?.id
    ?? pipeline.pipelineStatus?.current_run?.id
    ?? null
})
```

## 验证

| 验证 | 结果 |
|------|------|
| 重试按钮在 failed run 上可用 | ✅ (Phase 17 e2e test B2: "没有可重试的运行" 0 次) |
| running run 仍可重试 (向后兼容) | ✅ (fallback 到 current_run.id) |
| 现有 tests | ✅ 仍 pass |

## 1 行改动, 立即生效

无需后端改动, 无需新 API 端点。