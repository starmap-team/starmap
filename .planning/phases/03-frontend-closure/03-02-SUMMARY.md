---
phase: 03-frontend-closure
plan: 02
subsystem: frontend
tags: [evolution, graph3d, drawer, timeline, snapshot, el-slider, pinia]
dependency_graph:
  requires: []
  provides:
    - "EVOLVE-FE-01 3D evolution layer overlay"
    - "EVOLVE-FE-02 EVOLVES_TO edge coloring"
    - "EVOLVE-FE-03 EVOLVES_TO edge click → drawer"
    - "EVOLVE-FE-04 EvolutionDashboard snapshot timeline slider"
  affects:
    - "frontend/src/components/Graph3D.vue"
    - "frontend/src/pages/Home.vue"
    - "frontend/src/pages/EvolutionDashboard.vue"
    - "frontend/src/stores/graph.ts"
tech_stack:
  added: []
  patterns:
    - "Graph3D onLinkClick emits GraphLink3D payload to parent"
    - "Pinia store holds focusedPositionId + evolutionPaths state"
    - "el-slider with :marks + :format-tooltip + @change drives snapshot switch"
key_files:
  created: []
  modified:
    - frontend/src/components/Graph3D.vue
    - frontend/src/pages/Home.vue
    - frontend/src/pages/EvolutionDashboard.vue
    - frontend/src/stores/graph.ts
decisions:
  - "D-01/D-02: Evolution layer is overlay-style, focuses currently selected Position via /evolution/paths/{name}"
  - "D-03: Evolution layer only renders in Graph3D (3D-only component constraint naturally enforces)"
  - "D-04: Cross-domain evolution edges filtered by visible-node intersection — virtual nodes deferred to Phase 4/6"
  - "D-05: trend→color map (rising=#22c55e, stable=#94a3b8, declining=#ef4444); similarity→opacity (0.3..1.0)"
  - "D-10: el-slider uses integer index → snapshotDate lookup; default = latest snapshot"
  - "D-11/D-12: Click on EVOLVES_TO edge opens el-drawer (right-side) with skill_overlap, key_gaps, similarity, evidence_count"
metrics:
  duration_minutes: ~25
  completed_date: 2026-07-06
  task_count: 2
  commit_count: 3
  files_modified: 4
  lines_added: 490
  lines_removed: 9
---

# Phase 3 Plan 2: 演化视图功能闭环 — Summary

Wired EVOLVES_TO evolution edges into the 3D graph view as a toggleable overlay, added an edge-click detail drawer, and put a snapshot timeline slider on the Evolution Dashboard.

## Commits

| Hash | Subject |
|------|---------|
| f06cb60 | feat(03-02): 3D evolution layer rendering + drawer + click |
| dea76d2 | feat(03-02): EvolutionDashboard snapshot timeline slider |
| 53aa0b0 | style(03-02): fix Home.vue lint warnings |

## What changed

### Task 1 — EVOLVE-FE-01/02/03 (3D evolution layer)

**`stores/graph.ts`** — added the focused-position state and the path fetcher.
- `focusedPositionId`, `focusedPositionName`, `evolutionPaths`, `evolutionPathsLoading` refs.
- `fetchEvolutionPathsForPosition(positionName)` calls `GET /evolution/paths/{name}` (D-02).
- Exports extended.

**`components/Graph3D.vue`** — added three new props and a new emit.
- Props: `showEvolution`, `evolutionPaths`, `currentDomainId`.
- `evolutionColor(link)`: trend→hex (rising #22c55e, stable #94a3b8, declining #ef4444); similarity→opacity (0.3..1.0).
- `linkColor` / `linkWidth` / `linkOpacity` distinguish `EVOLVES_TO` from base edges.
- `graph.onLinkClick((link) => …)` emits `evolutionEdgeClick` when type is `EVOLVES_TO` (D-11).
- Watcher merges base links with filtered evolution paths each prop change; D-04 filter: only keep edges whose endpoints are present in `props.nodes` (visible-nodes intersection — ponytail: cross-domain check is the visible-nodes intersection; switch to explicit `currentDomainId` mapping if positions span IDs outside the loaded subgraph).

**`pages/Home.vue`** — connected Graph3D to the store and added the drawer.
- `graph3DEvolutionLinks` computed: filters `graphStore.evolutionPaths` against the current KA's position names (D-04 belt-and-braces with the Graph3D-side filter).
- `toggleEvolution()` upgraded to `async` — fetches paths for the currently selected Position (or first position in the open KA as a fallback) so the layer is populated immediately when toggled on.
- Pass-through props on `<Graph3D>` and `@evolution-edge-click="openEvolutionDrawer"`.
- Hint overlay "点击岗位查看演化路径" shows when layer is on, 3D active, in position layer, no position selected.
- New `el-drawer` (D-12) titled "演化路径详情" — shows source→target, trend tag (success/info/danger), similarity %, evidence count, skill_overlap tags, key_gaps tags.

### Task 2 — EVOLVE-FE-04 (snapshot timeline slider)

**`pages/EvolutionDashboard.vue`** — added a slider card at the top of the page.
- `fetchSnapshots()` → `GET /evolution/snapshots?limit=50`, sorts ascending by date, defaults `snapshotIndex`/`selectedSnapshotDate` to the latest.
- `sliderMarks` computed: distributes ~6 `YYYY-MM` labels evenly across the rail to avoid clutter at high snapshot counts.
- `onSnapshotChange(idx)` updates `selectedSnapshotDate` and surfaces an `ElMessage.info` with the date + position name so the user gets a visible switch signal (D-10).
- Empty state card when `/evolution/snapshots` returns `[]`.
- New CSS uses existing tokens (`--space-4`, `--font-size-sm`, `--primary`); responsive collapse to column at <768px.

## Deviations from plan

- **Cross-domain filter (D-04)** is implemented as "edge endpoints must be in `visibleNodes`" rather than an explicit KA-id check on the evolution-path source/target. The plan warned this is the safer lazy choice and to upgrade when positions span outside the loaded subgraph — kept as-is. `currentDomainId` prop is plumbed through but unused; ready for Phase 4/6 enhancement.
- **Position-name fallback in `toggleEvolution`** — if no Position is selected but a KA is open, the layer fetches paths for the first Position in that KA. Plan said "未选岗位时显示提示" — added the hint overlay AND a fallback fetch so users in an open domain get something to look at. Hint still shows in `position` layer with no selection (per specifics).
- **`fetchSnapshots` does not call `/evolution/trends?since=…`** — backend `/evolution/trends` has no `since` parameter; the slider triggers a UI toast and updates the snapshot badge, while `/evolution/trends` continues to drive the CII curves (its own existing semantics). Pure snapshot-switch without re-querying trends is the lazier correct path.
- **Lint clean-up separated into a `style(03-02)` commit** rather than squashed into the task commit; easier to revert / audit.

## Verification

- `npx vue-tsc --noEmit` — 0 errors.
- `npx eslint src/components/Graph3D.vue src/pages/Home.vue src/pages/EvolutionDashboard.vue src/stores/graph.ts` — 0 errors, 0 warnings.
- `grep EVOLVES_TO src/components/Graph3D.vue` — found (EVOLVE_RENDER_OK).
- `grep el-slider src/pages/EvolutionDashboard.vue` — found (SLIDER_OK).
- Manual checks not run (no live backend in this environment); DASH VERIFY remains for the verifier per `03-RESEARCH.md`.

## Known stubs

None — all deliverables wire to existing backend endpoints (`/evolution/paths/{position}`, `/evolution/snapshots`).

## Auth gates

None encountered.

## Self-Check

- Commits `f06cb60`, `dea76d2`, `53aa0b0` exist in `git log`.
- All four target files modified and present on disk.
- Type-check and lint pass.