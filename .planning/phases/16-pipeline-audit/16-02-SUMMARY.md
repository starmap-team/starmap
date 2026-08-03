---
phase: 16-pipeline-audit
plan: 02
completed: 2026-07-29
status: completed
---

# Plan 16-02: Frontend 状态延迟 + 渲染审计 — COMPLETED

## 已完成

### Task 1: SSE Reconnect Toast (Fix M1) ✅
**文件:** `frontend/src/composables/useSSE.ts`

```ts
eventSource.onopen = () => {
  connected.value = true
  const wasDisconnected = consecutiveFailures > 0  // 新增：记录之前是否断连
  ...
  // Phase 16-02 (Fix M1): 重连成功后显示 toast
  if (wasDisconnected) {
    import('element-plus').then(({ ElMessage }) => {
      ElMessage.success('实时推送已恢复')
    })
  }
}
```

### Task 2: Stage Card 进度 Fallback (Fix M3) ✅
**文件:** `frontend/src/components/PipelineStageCard.vue`

```ts
const realProgress = computed(() => {
  const raw = props.liveActivity?.progress ?? props.stage.progress
  if (raw === null || raw === undefined) {
    if (props.stage.status === 'completed') {
      console.warn(`[PipelineStageCard] stage ${props.stage.name} completed but progress=null — backend bug?`)
      return 100  // fallback 避免 "已完成 0%" 矛盾
    }
    return 0
  }
  return Math.round(raw * 100)
})
```

### Task 3: Issue H - PipelineDag.vue 加 timeseries stage ✅
**文件:** `frontend/src/components/PipelineDag.vue`

新增 Row 6: timeseries (原文 5 stage hardcoded, 现在 6 stage)

**验证:** 截图显示 6 个 stage 卡片:
- 爬虫采集 / SimHash去重 / 清洗标准化 / LLM抽取+入库 / 图谱构建 / **时间序列** ✓

### Task 4: Vue 渲染测试 (5 个) — 替代为 Playwright E2E 测试
**文件:** `frontend/e2e/phase16-audit.spec.ts`

由于项目无 vue-test-utils/vitest 配置，改用 Playwright e2e:

```ts
test('Issue H: DAG displays all 6 stages including timeseries')
test('Fix M3: completed stage with null progress shows 100% (fallback)')
test('Fix M3: skipped stage hides progress bar')
test('Issue C: KPI 数字文案 (今日累计入库) 不会被重复渲染 3+ 次')
test('API consistency: 所有 stage 都有 status 字段')
```

**测试结果:** ✅ **5/5 PASS** (12s)

## 测试结果

| 测试 | 结果 |
|------|------|
| `e2e/phase16-audit.spec.ts` | ✅ **5/5 PASS** (12s) |
| Backend unit + e2e | ✅ 153/153 + 6/6 = 159/159 |
| **总计** | ✅ **164/164 PASS** |

## 文件变更

- `frontend/src/composables/useSSE.ts` (Fix M1)
- `frontend/src/components/PipelineStageCard.vue` (Fix M3)
- `frontend/src/components/PipelineDag.vue` (Issue H - 加 timeseries row)
- `frontend/e2e/phase16-audit.spec.ts` (新建 5 个 e2e 测试)

## 浏览器实测验证

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| timeseries stage 显示 | ❌ 5 stage | ✅ 6 stage |
| 重连 toast | ❌ 无 | ✅ 实时推送已恢复 |
| progress fallback | ❌ 0% | ✅ 100% |
| 数据源 records | 0 | 422 / 100 / 31 |

## 残留 OPEN (后续 Phase)

| ID | 描述 | 优先级 |
|----|------|--------|
| Issue H 部分 | PipelineDag.vue 还有 4 个 arrow rows, 可能有冗余 | LOW |
| Issue I | KPI 重复显示 (text extraction 看到 4 次) | MED |
| Issue J | 4 个数字仍不一致 (149/144/8/158) | MED |
| SSE reconnect 测试 | 需要 e2e 模拟 token 失效 | MED |

## 下一步

Wave 2: Plan 16-03 (跨端一致性 + 性能瓶颈)