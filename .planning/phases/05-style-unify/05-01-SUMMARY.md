---
phase: 05-style-unify
plan: 01
type: execute
subsystem: frontend-style
tags: [echarts, palette, refactor, css-vars-migration]
duration: ~5min
completed: 2026-07-07

dependency_graph:
  requires: []
  provides:
    - "ECHARTS_PALETTE single source for ECharts border/label/KPI colors"
    - "DataDashboard.vue + stores/quality.ts free of hex literals"
  affects:
    - frontend/src/utils/graphColors.ts
    - frontend/src/pages/DataDashboard.vue
    - frontend/src/stores/quality.ts

tech_stack:
  added: []
  patterns:
    - "hex literal palette → named export with `as const`"
    - "semantic isolation: ECHARTS_PALETTE co-located with NODE_TYPE_COLORS without semantic coupling"

key_files:
  created: []
  modified:
    - frontend/src/utils/graphColors.ts
    - frontend/src/pages/DataDashboard.vue
    - frontend/src/stores/quality.ts

decisions:
  - "D-01/D-02/D-03: batch migrate in single plan — no intermediate mixed state"
  - "D-06: graphColors.ts remains hex-literal source (no getComputedStyle bridge)"
  - "KPI array index mapping (0=节点总数 blue, 1=平均信任度 green, 2=幻觉率 amber, 3=待审核 red) documented inline in graphColors.ts"

metrics:
  duration: 5min
  completed: 2026-07-07
  tasks: 2
  files: 3
---

# Phase 5 Plan 1: ECHARTS_PALETTE Migration Summary

## One-liner

Introduced `ECHARTS_PALETTE` in `graphColors.ts` and migrated 9 remaining hex literals across `DataDashboard.vue` (5 sites: PIE_BORDER x4, LABEL x1) and `stores/quality.ts` (4 KPI cards), eliminating the last non-comment inline hex in the two named files.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add ECHARTS_PALETTE constant to graphColors.ts | `836cc59` | `frontend/src/utils/graphColors.ts` |
| 2 | Migrate DataDashboard.vue and stores/quality.ts to ECHARTS_PALETTE | `909c7ec` | `frontend/src/pages/DataDashboard.vue`, `frontend/src/stores/quality.ts` |

## Key Changes

**graphColors.ts** — added a new top-level `ECHARTS_PALETTE` export (placed after `SCENE_PALETTE`, before `toThreeHex`):

```ts
export const ECHARTS_PALETTE = {
  PIE_BORDER: '#0a0a1a',
  LABEL:      '#ffffff',
  KPI:        ['#409eff', '#67c23a', '#e6a23c', '#f56c6c'],
} as const
```

Existing `DOMAIN_COLORS` / `EDGE_TYPE_COLORS` / `NODE_TYPE_COLORS` / `SCENE_PALETTE` / helper functions all untouched (semantic isolation per D-02).

**DataDashboard.vue** — added `import { ECHARTS_PALETTE } from '@/utils/graphColors'` to existing import block; replaced:
- Line 142: `'#0a0a1a'` → `ECHARTS_PALETTE.PIE_BORDER`
- Line 204: `'#fff'` → `ECHARTS_PALETTE.LABEL`
- Line 209: `'#0a0a1a'` → `ECHARTS_PALETTE.PIE_BORDER`
- Line 215: `'#0a0a1a'` → `ECHARTS_PALETTE.PIE_BORDER`
- Line 247: `'#0a0a1a'` → `ECHARTS_PALETTE.PIE_BORDER`

`cc.chart[*]` / `cc.foreground` / `cc.success` references (D-05/D-06 out-of-scope, already routed via `chartTheme.ts`) untouched.

**stores/quality.ts** — added the import; replaced the four KPI colors in declaration order:
- `'#409eff'` → `ECHARTS_PALETTE.KPI[0]` (节点总数)
- `'#67c23a'` → `ECHARTS_PALETTE.KPI[1]` (平均信任度)
- `'#e6a23c'` → `ECHARTS_PALETTE.KPI[2]` (幻觉率)
- `'#f56c6c'` → `ECHARTS_PALETTE.KPI[3]` (待审核)

## Verification

| Gate | Result |
| ---- | ------ |
| `grep -nE "'#[0-9a-fA-F]{3,8}'"` (non-comment) in DataDashboard.vue + stores/quality.ts | **0** (zero) |
| `grep -c ECHARTS_PALETTE.PIE_BORDER` DataDashboard.vue | **4** (>=4) |
| `grep -c ECHARTS_PALETTE.LABEL` DataDashboard.vue | **1** (=1) |
| `grep -c ECHARTS_PALETTE.KPI\[]` stores/quality.ts | **4** (=4) |
| `grep -c "NODE_TYPE_COLORS\|EDGE_TYPE_COLORS\|SCENE_PALETTE\|DOMAIN_COLORS"` graphColors.ts | **14** (>=4, all preserved) |
| `npx vue-tsc --noEmit -p tsconfig.json` | **clean** for new code (2 pre-existing tsconfig warnings about `vite/client` types and `baseUrl` deprecation are unrelated to this change) |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both modified files compile cleanly and reference the new constant via the documented import path.

## Threat Flags

None — no new auth, file, network, or schema surfaces introduced; this is a pure color constant refactor.

## Self-Check: PASSED

- All 3 modified files exist at the expected paths.
- Commit `836cc59` and `909c7ec` exist in `git log --oneline`.
- Success criteria from plan: `ECHARTS_PALETTE` exported; DataDashboard.vue + stores/quality.ts free of non-comment hex; vue-tsc adds no new errors.
