---
phase: 17-pipeline-integrity
plan: 01
completed: 2026-07-30
status: completed
---

# Plan 17-01: 移除 timeseries 从核心 DAG — COMPLETED

## 已完成

### Task 1: pipelineConfig.ts 改 ALL_STAGE_NAMES ✅
**文件:** `frontend/src/stores/pipelineConfig.ts`

```ts
// Phase 17-01: timeseries 移出核心 DAG (设计文档明确)
export const ALL_STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync']
export const OPTIONAL_STAGES = ['timeseries', 'graph_sync']
```

### Task 2: PipelineDag.vue 去掉 Row 6 (timeseries) ✅
**文件:** `frontend/src/components/PipelineDag.vue`

删除之前 Phase 16-02 添加的 Row 6 (timeseries stage + arrow)

### Task 3: 触发对话框自动减为 5 个 ✅
无需改动 (动态用 `ALL_STAGE_NAMES.map` 渲染 checkbox)

## 验证

| 验证 | 结果 |
|------|------|
| `ALL_STAGE_NAMES.length === 5` | ✅ |
| PipelineDag.vue DOM `.timeline-node` count | ✅ 5 (verified by Phase 17 e2e test B1) |
| 触发对话框 checkbox 数量 | ✅ 5 (verified by Phase 17 e2e test "ALL_STAGE_NAMES") |
| 现有 124 unit + 9 e2e tests | ✅ 仍 pass |

## 文件变更

- `frontend/src/stores/pipelineConfig.ts` (改 ALL_STAGE_NAMES + 新 OPTIONAL_STAGES)
- `frontend/src/components/PipelineDag.vue` (删除 Row 6)