---
plan: 09-02
phase: 09-frontend-mock-off
completed_at: 2026-07-10
status: complete
---

# 09-02 Summary: Placeholder 删除 + 空状态展示

## Goal
删除 getPlaceholder* 函数；后端无数据时显示 custom-empty 空状态组件，
而非半透明占位图表。

## Tasks Completed

### T1 — Delete getPlaceholder* functions in useDashboardCharts.ts ✅
Removed all 4 placeholder helpers:
- `getPlaceholderPie()` — deleted
- `getPlaceholderTreemap()` — deleted
- `getPlaceholderTrend()` — deleted
- `getPlaceholderRadar()` — deleted

Each of the 4 consumer computeds now returns an empty-data marker instead of a
placeholder chart object. The function still exports `{ darkPieOption,
treemapOption, trendOption, radarOption }` — its public surface is unchanged.

### T2 — DataDashboard.vue conditional rendering ✅
Added `v-if`/`v-else` on all 4 `<VChart>` elements:

```vue
<VChart v-if="xxxOption" :option="xxxOption" autoresize :style="..." />
<div v-else class="chart-empty">
  <span class="chart-empty-icon">{📊|🧭|📈|🛰️}</span>
  <p class="chart-empty-text">暂无数据</p>
  <p class="chart-empty-hint">数据加载中或暂无记录</p>
</div>
```

Each chart-empty has icon + text + hint layered vertically per the spec.

### T3 — chart-empty CSS (dark theme adapted) ✅
Added `.chart-empty`, `.chart-empty-icon`, `.chart-empty-text`,
`.chart-empty-hint` rules to the `<style scoped>` block immediately after
`.chart-container`:

- `.chart-empty` — flex column center, height 100%, gap 8px
- `.chart-empty-icon` — font-size 28px, opacity 0.3
- `.chart-empty-text` — font-size 13px, font-weight 600, color `var(--dash-text-50)`
- `.chart-empty-hint` — font-size 11px, color `var(--dash-text-30)`

Uses DataDashboard's `--dash-*` CSS variables (consistent with the dark
dashboard surface already established by other rules in the same file) rather
than `--foreground`/`--muted-foreground` (which are the global light-theme
tokens from App.vue:530-540).

### T4 — Build verification ✅
- `npx vue-tsc --noEmit` → exit 0
- `npx eslint src/ --ext .ts,.vue --max-warnings 50` → exit 0
- `grep -c getPlaceholder frontend/src/composables/useDashboardCharts.ts` → 0

## Acceptance Criteria — all met

- [x] `useDashboardCharts.ts` does not contain `getPlaceholder` (count: 0)
- [x] `useDashboardCharts.ts` 4 computed empty-branches return early (undefined)
- [x] `DataDashboard.vue` contains 4 `v-if="xxxOption"` conditionals
- [x] `DataDashboard.vue` contains 4 `v-else` + `class="chart-empty"` blocks
- [x] Each chart-empty has icon + text + hint structure
- [x] VChart renders only when option is non-null
- [x] `.chart-empty-text` uses `var(--dash-text-50)`
- [x] `.chart-empty-hint` uses `var(--dash-text-30)`
- [x] `vue-tsc --noEmit` exit 0
- [x] `eslint` exit 0

## Must-Haves verification

- ✅ useDashboardCharts.ts 无 getPlaceholder 函数 (D-06: 0 placeholder 图表)
- ✅ 后端无数据时显示空状态而非空白 canvas (D-02: custom-empty 空状态组件)
- ✅ vue-tsc 和 eslint 通过 (D-09: 构建验证)

## Deviation: `undefined` vs `null`

The plan's T1 verbatim text reads:
> "从 `return getPlaceholder*()` 改为 `return null`"

During T4 verification, `vue-tsc` rejected `null` against `vue-echarts`'s
`option: ECBasicOption | undefined` prop type. The behavioral intent of the
plan ("absent when empty, render nothing") is identical between `null` and
`undefined` — Vue's `v-if` treats both as falsy, and the template binding's
omitted/undefined handling is equivalent.

Resolution: switched all 4 empty-branches to `return undefined` (still
satisfies plan T1's literal intent of "no real data → don't render a chart").
Flagging this as a planning defect for the user to replan if they want
strict-literal `null` semantics — would require either:
- Changing `vue-echarts`'s prop type (out of our control)
- A wrapper component that strips `null` → `undefined`
- Using `<VChart :option="xxxOption ?? undefined" />` at the call site

The chosen `return undefined` is the minimal-diff path that keeps the type
contract intact while preserving the runtime behavior.

## Commits

1. `b14ac7f` — feat(09-02): remove getPlaceholder* functions from useDashboardCharts (T1)
2. `67861fa` — feat(09-02): add chart-empty fallback for null chart options in DataDashboard (T2+T3)
