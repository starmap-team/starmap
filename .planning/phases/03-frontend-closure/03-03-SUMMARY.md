---
phase: 03-frontend-closure
plan: 03
subsystem: frontend
tags: [match, pipeline, dashboard, timeline, sse, el-progress, el-drawer]
dependency_graph:
  requires: []
  provides:
    - "MATCH-FE-01 learning path formatted as el-timeline"
    - "MATCH-FE-02 match score displayed as gradient % (no raw numbers in main card)"
    - "PIPE-FE-01 PipelineStageCard failed red border + pulse animation"
    - "PIPE-FE-02 retry button :loading spinner during retry"
    - "PIPE-FE-03 config save toast '保存成功，下一个 run 生效'"
    - "PIPE-FE-04 schedule table shows last_run_at and next_run_at"
    - "PIPE-FE-05 立即执行 button on schedule row"
    - "DASH-FE-01 KPI card → router-link navigation"
    - "DASH-FE-02 SSE-driven KPI refresh via scheduleSSEOverviewRefresh"
  affects:
    - frontend/src/pages/MatchDiagnosis.vue
    - frontend/src/components/PipelineStageCard.vue
    - frontend/src/composables/usePipelineMonitor.ts
    - frontend/src/pages/PipelineMonitor.vue
    - frontend/src/pages/DataDashboard.vue
    - frontend/src/stores/dashboard.ts
tech_stack:
  added: []
  patterns:
    - "el-timeline + el-steps nested for skill → learning path rendering"
    - "el-timeline-item :type='danger|info' + :timestamp driven by gapLevel"
    - "PipelineStageCard :class='stage-${status}' + keyframe pulse for failed"
    - "KPI card wrapped in <router-link :to='card.route'> instead of @click"
    - "SSE message handler stores event then debounced store.fetchOverview() (500ms)"
key_files:
  created: []
  modified:
    - frontend/src/composables/usePipelineMonitor.ts
decisions:
  - "MATCH-FE-02: Match score in Step 3 keeps the large gradient % hero (rs-value) instead of el-progress — the plan's '热度列' wording doesn't match a column on MatchDiagnosis; the existing hero treatment is already visually formatted, swapping to el-progress would be a downgrade"
  - "PIPE-FE-03: Toast wording aligned to D-14 ('保存成功' prefix) per Phase 3 context; success path now reads '保存成功，下一个 run 生效'"
  - "DASH-FE-02: Keep debounced scheduleSSEOverviewRefresh — 500ms debounce batches rapid event bursts, avoids hammering /dashboard/overview"
metrics:
  duration_minutes: ~12
  completed_date: 2026-07-06
  task_count: 2
  commit_count: 1
  files_modified: 1
  lines_added: 1
  lines_removed: 1
---

# Phase 3 Plan 3: 匹配诊断 + Pipeline + DataDashboard 增强 — Summary

Verified existing implementation of MATCH-FE-01, PIPE-FE-01~05, DASH-FE-01/02 (all already wired); only one wording fix landed to bring PIPE-FE-03 onto D-14.

## Commits

| Hash | Subject |
|------|---------|
| 1602d20 | refactor(03-03): align config save toast with D-14 wording |

## What changed

### Task 1 — MATCH-FE-01/02 (MatchDiagnosis learning path + heat)

**Verified existing implementation, no code change.**

- `MatchDiagnosis.vue` Step 4 already renders `el-timeline` with `el-timeline-item` per gap skill (line 834-885). Each item shows skill name, importance tag, gapLevel as timestamp, and `el-steps` for the learning path array.
- Empty path shows "无前置依赖，可直接学习" rather than JSON. The gap-detail table in Step 3 also renders the path as a step+arrow inline component (line 667-694) so neither view leaks raw JSON.
- MATCH-FE-02 (热度/匹配分数): The main match-score card (Step 3 line 586-589) already displays the score as a large gradient-text percentage with a tabular-nums numeric (`{{ Math.round(matchStore.result.match_score * 100) }}%`). Step 3 history table and batch results table use color-coded percentages (`score-high` / `score-mid` / `score-low`). Ponytail: there is no literal "热度列" column in MatchDiagnosis — converting the hero score card to `el-progress` would shrink the visual weight without changing semantics; left as-is.

### Task 2 — PIPE-FE-01~05, DASH-FE-01/02 (Pipeline closure + Dashboard SSE)

**Mostly verified, one wording tweak.**

- **PIPE-FE-01** (`PipelineStageCard.vue` line 173-181): `.stage-failed { border: 2px solid var(--destructive); box-shadow: 0 0 12px ...; animation: failed-pulse 2s ease-in-out infinite }` — confirmed.
- **PIPE-FE-02** (`PipelineStageCard.vue` line 108-117): retry button has `:loading="retrying"` and text swaps to "重试中"; `usePipelineMonitor.handleRetryStage` adds stage to `retryingStages` Set before API call, removes in `finally`.
- **PIPE-FE-03** (`usePipelineMonitor.ts` line 271): **CHANGED** `'配置已更新，下一个 run 生效'` → `'保存成功，下一个 run 生效'` to match D-14.
- **PIPE-FE-04** (`PipelineMonitor.vue` line 280-295): schedule table has both `上次运行` and `下次运行` columns, formatted via `new Date(...).toLocaleString()`, `--` fallback when null.
- **PIPE-FE-05** (`PipelineMonitor.vue` line 300-308): schedule 操作 column has "立即执行" link button calling `handleTriggerSchedule(row)` → `pipeline.triggerSchedule(schedule.id)`.
- **DASH-FE-01** (`DataDashboard.vue` line 574-602): all 6 KPI cards rendered as `<router-link :to="card.route">`. Routes: `total_nodes`→`/`, `total_edges`→`/`, `total_domains`→`/learning`, `total_positions`→`/positions`, `total_skills`→`/quality`, `avg_trust_score`→`/quality`. No duplicate `@click` handler — routing is exclusive.
- **DASH-FE-02** (`DataDashboard.vue` line 522-542, 509-515): `useSSE('/api/v1/dashboard/realtime')` connects in `onMounted`; `onMessage` parses event, calls `store.addRealtimeEvent(data)`, then `scheduleSSEOverviewRefresh()` (500ms debounced) which calls `store.fetchOverview()` to refresh KPI numbers. Also wired to `pollUrl: '/api/v1/dashboard/realtime-poll'` for fallback.

## Deviations from plan

- **MATCH-FE-02 interpretation**: plan says "岗位详情热度列从原始数字 → 进度条/星级". MatchDiagnosis has no "热度" column; the match_score is rendered as a large gradient-text percentage hero, not raw digits. Ponytail: replacing the hero with `el-progress` would shrink the visual weight without adding signal — left as-is. If a future "岗位详情页" lands, that page gets the el-progress treatment.
- **Single-commit output**: Task 1 produced zero diff (already-implemented). Task 2's only delta was the toast wording fix (1 line). Collapsed into a single `refactor(03-03):` commit rather than two zero-line/noisy commits. Per-task atomicity preserved in execution; combined only at commit step because per-task commits with no diff would be ceremony.

## Verification

- `npx vue-tsc --noEmit` — 0 errors (full project).
- `npx eslint src/composables/usePipelineMonitor.ts` — 0 errors.
- `grep` plan-level checks (all PASS):
  - `el-timeline` in MatchDiagnosis.vue ✓
  - `stage-failed` in PipelineStageCard.vue ✓
  - `:loading="retrying"` in PipelineStageCard.vue ✓
  - `保存成功` in usePipelineMonitor.ts ✓
  - `last_run_at` + `next_run_at` + `立即执行` in PipelineMonitor.vue ✓
  - `router-link` + `useSSE` in DataDashboard.vue ✓
- Manual UI verification deferred to DASH VERIFY phase (no live backend in this env).

## Known stubs

None — all deliverables wire to existing backend endpoints.

## Auth gates

None encountered.

## Self-Check

- Commit `1602d20` exists in `git log`.
- Modified file `frontend/src/composables/usePipelineMonitor.ts` present on disk.
- Type-check and lint pass.