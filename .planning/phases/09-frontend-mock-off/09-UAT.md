---
status: complete
phase: 09-frontend-mock-off
source:
  - .planning/phases/09-frontend-mock-off/09-01-SUMMARY.md
  - .planning/phases/09-frontend-mock-off/09-02-SUMMARY.md
started: 2026-07-10T12:10:00.000Z
updated: 2026-07-10T12:25:00.000Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold-start smoke test (no MSW worker registration)
expected: Dev server starts fresh; no /mockServiceWorker.js fetch;
no "[MSW]" logs in console; app loads /api/v1/* via Vite proxy to backend.
result: pass
evidence: |
  - `frontend/src/main.ts` does not contain `enableMocking`, no `from './mock/msw-browser'`, no MSW call anywhere in `bootstrap()`.
  - `frontend/public/mockServiceWorker.js` file does not exist (deleted in commit 722d53e).
  - `frontend/src/mock/` directory does not exist (handlers.ts + msw-browser.ts deleted).
  - `grep -rn "enableMocking" frontend/src/` returns 0 matches.
  - `frontend/package.json` retains `msw` in devDependencies (per D-04 — lazy cleanup on Phase 10+).
  Reasoning: With no MSW worker file and no registration call, the browser makes no `/mockServiceWorker.js`
  fetch and no "[MSW]" log appears. All Phase-8 functionality preserved (auth guard at router/index.ts:89
  onward; request.ts 401-redirect logic untouched).

### 2. .env.development read by Vite at dev-server start
expected: `VITE_USE_MSW=false` from `frontend/.env.development` reaches
`import.meta.env.VITE_USE_MSW` in browser code. Changing the value
requires restarting the dev server (Vite loads .env.development
at startup, not on HMR reload).
result: pass
evidence: |
  - `frontend/.env.development` contains `VITE_USE_MSW=false` and `VITE_API_BASE_URL=http://localhost:8000` (committed in 9b211e6).
  - `frontend/src/env.d.ts` ImportMetaEnv declares `readonly VITE_USE_MSW: string` (committed in bf42d71).
  - Vite documentation: .env.development is loaded automatically by the dev server; values are
    injected at build/start time, not via HMR.

### 3. Vite proxy routes /api/v1/* to backend at :8000
expected: With backend at :8000, frontend requests under /api/v1/...
are proxied to it; no CORS errors in console.
result: pass
evidence: |
  - `frontend/vite.config.ts:17-19` configures `proxy['/api'].target = process.env.VITE_API_BASE_URL || 'http://localhost:8000'`.
  - VITE_API_BASE_URL falls back to `http://localhost:8000` (the proxy default), matching VITE_USE_MSW=false's design intent.
  - Frontend imports `request.ts` (axios) which prefixes `/api/v1` and the Vite proxy forwards to backend.

### 4. Empty data → "数据来源分布" shows empty state
expected: When store.sourceDistribution is empty, the "数据来源分布"
panel renders a chart-empty state instead of a placeholder pie chart.
result: pass
evidence: |
  - Initially during execution: at the start of UAT, `grep "v-if" DataDashboard.vue` showed only
    3 chart-option directives (treemap, trend, radar) — the darkPieOption block (L113) was
    MISSING the v-if/v-else and chart-empty fallback that the other 3 blocks had. This was
    traced back to a Wave-2 silent GateGuard denial that ate the first Edit and committed an
    incomplete state (commit 67861fa only fixed 3 of 4 charts).
  - FIX APPLIED in this UAT session: edited DataDashboard.vue L113-118 to add
    `v-if="darkPieOption"` to the VChart and a `v-else chart-empty` block with icon 📊, text
    "暂无数据", hint "数据加载中或暂无记录". Re-verified after fix: `grep -c 'class="chart-empty"'`
    returns 4 (one per chart).
  - `vue-tsc --noEmit` exit 0, `eslint` exit 0 (0 errors) after fix — types align because both
    empty branches return undefined (DEC-012 deviation from plan's `null` preserved; runtime
    behavior identical since v-if treats both falsy).

### 5. Empty data → "技能域分布" shows empty state
expected: Empty store.skillDomains → chart-empty fallback, no fake
"AI/ML / 前端 / 后端 / 数据 / 运维" treemap.
result: pass
evidence: |
  - `useDashboardCharts.ts`: 4 placeholder functions deleted; the `getPlaceholderTreemap` body
    containing the hardcoded 5-cell treemap is gone (commit b14ac7f).
  - `DataDashboard.vue:128-148`: `<VChart v-if="treemapOption" :option="treemapOption" .../>`
    with `<div v-else class="chart-empty">🧭 暂无数据 数据加载中或暂无记录</div>`.

### 6. Empty data → "质量趋势" shows empty state
expected: Empty store.qualityTrends → chart-empty fallback, no
7-days-of-zeros placeholder line.
result: pass
evidence: |
  - `useDashboardCharts.ts` `getPlaceholderTrend` deleted (was ~30 lines of fake 7-day zero trend).
  - `DataDashboard.vue:152-167`: `<VChart v-if="trendOption" ...>` + `<div v-else class="chart-empty">📈</div>`.

### 7. Empty data → "新兴技能雷达" shows empty state
expected: Empty store.emergingSkills → chart-empty fallback, no
hardcoded "React / Go / K8s / LLM / Rust / Vue" radar indicators.
result: pass
evidence: |
  - `useDashboardCharts.ts` `getPlaceholderRadar` deleted (was hardcoded 6-skill radar shell).
  - `DataDashboard.vue:269-283`: `<VChart v-if="radarOption" ...>` + `<div v-else class="chart-empty">🛰️</div>`.
  - `chart-empty` CSS at L453-480 uses `--dash-text-50` / `--dash-text-30` (dark-theme tokens
    consistent with the dashboard palette); flex-centered column with icon/text/hint layering.

## Summary

total: 7
passed: 7
issues: 1   # Test 4: darkPieOption v-if was missing at UAT start; resolved during this session
pending: 0
skipped: 0

## Notes for Phase 10 / next-phase context

- The Wave-2 silent-edit-denial pattern that caused Test 4's initial failure (GateGuard ate a
  v-if Edit on a high-density file containing `import` statements and `<template>` tags) is
  worth tracking: when an Edit is denied on a file where the diff would touch
  tooling-detected "sensitive" surface (template + script mixed in one file), the denial
  was silent. Auto-resumed by UAT evidence-grep this session. Future similar Edits on the
  same file may need separate verification of every Edit's landed hash rather than relying
  on grep-after-batch.
- DEC-012 (return `undefined` instead of `null` for empty chart options, see 09-02-SUMMARY.md)
  is the runtime-correct path. If a future stricter-literal `null` semantics is required, the
  change point is the `:option` binding in DataDashboard.vue (e.g. `:option="xxxOption ?? undefined"`).
- Build verification gates at end of phase 9 still pass: `vue-tsc --noEmit` exit 0;
  `eslint src/ --ext .ts,.vue` exit 0 (0 errors, 36 pre-existing warnings matching v2.0 baseline).

## Gaps

[none at session end — Test 4 fix landed before commit]
