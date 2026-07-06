# Phase 3: 前端功能闭环 - Research

**Researched:** 2026-07-06
**Domain:** Vue 3 + Element Plus frontend wiring (API calls, state management, user feedback)
**Confidence:** HIGH

## Summary

Phase 3 is a pure frontend wiring phase: every backend API endpoint is already implemented and functional. The work is to connect existing Vue page handlers to real API calls, add missing handlers, implement evolution edge rendering in 3D graph, and ensure consistent user feedback (toast, loading, drawer). The codebase already has strong patterns: Pinia stores with `request.get/post/put/delete`, `ElMessage` for toasts, `ElMessageBox.confirm` for confirmations, and `el-drawer` for detail panels. The `useSSE` composable already handles SSE with polling fallback. The `graphStore` already has `evolutionEdges` and `fetchEvolutionEdges()` wired — the 3D rendering of EVOLVES_TO edges is the main new visual feature.

**Primary recommendation:** Wire each page's stub handlers to existing store methods and API calls. Reuse established patterns (ElMessage, request, Pinia stores). The evolution edge rendering in Graph3D.vue is the only non-trivial new code — add EVOLVES_TO links to the `graph3DLinks` computed in Home.vue and color them by trend in Graph3D.vue.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: EVOLVES_TO edges as independent overlay layer, not a 4th overview mode
- D-02: Evolution layer focuses on selected position, calls `/evolution/paths/{position}`, not full render
- D-03: Evolution layer only in 3D view (viewMode='3d'), no 2D evolution edges
- D-04: Evolution edges only within current knowledge domain, cross-domain not rendered
- D-05: Evolution edge coloring: rising=green, stable=gray, declining=red; trust_score adjusts opacity
- D-06: Learning plan uses localStorage to store plan_id
- D-07: plan_id validated on every LearningCenter open (GET call), invalid -> clear + empty state
- D-08: Single plan mode; "add to plan" with existing plan -> confirm overwrite
- D-09: "Add to plan" calls POST /learning/plan, progress from GET /learning/plan/{plan_id}
- D-10: EvolutionDashboard timeline slider controls snapshot time point
- D-11: Click EVOLVES_TO edge -> evolution detail popup (el-drawer per D-12)
- D-12: Edit dialogs unified as el-drawer (right slide), for Admin/PIPE/MATCH
- D-13: After save -> auto-refresh list + toast
- D-14: Toast text: success='保存成功', failure='保存失败，请重试'

### Claude's Discretion
- Evolution layer toggle UI position (suggested: next to existing radio-group)
- Evolution edge arrow style and loading animation
- Default state when no position selected (suggested: "点击岗位查看演化路径")
- Degraded display when no data for snapshot time point
- EVOLVES_TO edge click detail field layout
- LearningCenter empty state guidance text
- Learning progress visualization form (progress bar / ring chart)

### Deferred Ideas (OUT OF SCOPE)
- User system (login/register/permissions) — Phase 7+
- 2D view evolution edge rendering — Phase 5/6
- Cross-domain evolution target rendering — Phase 4/6
- Evolution animation playback — future enhancement
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADMIN-01 | handleSaveSource calls actual API | Admin.vue already calls `admin.updateSource()` which calls `request.put` — this is ALREADY wired. Need to verify the edit dialog uses el-drawer (D-12) instead of el-dialog |
| ADMIN-02 | Audit queue "Edit" button implements edit drawer + API call | ReviewQueuePanel.vue needs investigation — currently has approve/reject but edit may be missing |
| ADMIN-03 | Data source "Edit" save refreshes list | handleSaveSource already calls `admin.fetchSources()` after save — ALREADY done |
| LEARN-FE-01 | "Add to plan" button binds handler -> POST /learning/plans | learningStore.createPlan() exists and calls POST /learning/plan. Need to wire the "Add to plan" button in recommendations to call createPlan, and implement localStorage plan_id storage (D-06) |
| LEARN-FE-02 | Remove hardcoded demo data -> load from API | learningStore.fetchPlans() already calls GET /learning/plans. The onMounted in LearningCenter.vue already calls it. No hardcoded demo data found in current code — may already be done |
| LEARN-FE-03 | Learning progress display -> GET /learning/progress/{plan_id} | learningStore.updateProgress() calls PUT /learning/plan/{plan_id}/progress. The SkillProgressCard already emits update-status. Need to verify progress reading from GET endpoint |
| LEARN-FE-04 | Empty state guidance (no learning plan) | LearningCenter.vue already has empty state template with "暂无学习计划" and button to /match. May need localStorage plan_id validation (D-07) |
| EVOLVE-FE-01 | Graph page "evolution" view renders EVOLVES_TO edges | graphStore.evolutionEdges + fetchEvolutionEdges() exist. Home.vue has showEvolution toggle. Need to add EVOLVES_TO edges to graph3DLinks computed and render in Graph3D.vue with trend coloring |
| EVOLVE-FE-02 | EVOLVES_TO edge coloring: rising=green, stable=gray, declining=red | Graph3D.vue linkColor function needs to check link.type === 'EVOLVES_TO' and apply D-05 coloring |
| EVOLVE-FE-03 | Click EVOLVES_TO edge -> evolution detail drawer | HomeEvolutionPopup.vue already exists with full detail layout. Need to wire edge click in Graph3D.vue to emit event, Home.vue to handle it |
| EVOLVE-FE-04 | Evolution dashboard timeline slider (snapshot time point) | EvolutionDashboard.vue needs el-slider for snapshot selection. Backend has GET /evolution/snapshots endpoint |
| MATCH-FE-01 | Learning path from JSON array -> formatted timeline/card | MatchDiagnosis.vue Step 4 already has el-timeline with el-steps for learning path. The learning_path array is already rendered as steps. May need enhanced formatting |
| MATCH-FE-02 | Position detail "heat" column from raw number -> progress bar/star | Need to check PositionDetail.vue or PositionList.vue for heat column rendering |
| PIPE-FE-01 | PipelineStageCard failed -> red border highlight | PipelineDag.vue / PipelineStageCard.vue — need to check current styling for failed state |
| PIPE-FE-02 | Retry button click -> loading spinner | usePipelineMonitor composable has retryingStages Set — already tracks retrying state. Need to verify spinner is shown |
| PIPE-FE-03 | Config save -> toast "已更新，下一个 run 生效" | handleSaveConfig in usePipelineMonitor already shows ElMessage.success('配置已更新，下一个 run 生效') — ALREADY done |
| PIPE-FE-04 | Schedule list shows last_run_at and next_run_at | PipelineMonitor.vue schedule table already has columns for 上次运行 and 下次运行 — ALREADY done |
| PIPE-FE-05 | Support "立即执行" button | PipelineMonitor.vue schedule table already has "立即执行" button calling handleTriggerSchedule — ALREADY done |
| DASH-FE-01 | KPI card click -> navigate to detail page | DataDashboard.vue kpiCards already have `route` property and are wrapped in `<router-link>` — ALREADY done |
| DASH-FE-02 | SSE event drives KPI real-time update | DataDashboard.vue already uses useSSE composable, calls store.addRealtimeEvent, and scheduleSSEOverviewRefresh — ALREADY done |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API call wiring (Admin/Learning/Pipeline) | Browser / Client | — | Pure frontend handler-to-store binding |
| Evolution edge rendering | Browser / Client | — | Graph3D.vue link rendering + Home.vue data computation |
| localStorage plan_id persistence | Browser / Client | — | Client-side storage, no backend involvement |
| SSE event handling | Browser / Client | Frontend Server | useSSE composable already handles this |
| Toast/drawer feedback | Browser / Client | — | Element Plus UI components |
| Timeline slider (snapshots) | Browser / Client | API / Backend | Frontend renders slider, backend provides snapshot data |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vue 3 | ^3.4.0 | UI framework | Project standard [VERIFIED: package.json] |
| Element Plus | ^2.6.0 | UI component library | Project standard, provides el-drawer, el-timeline, el-slider, ElMessage [VERIFIED: package.json] |
| Pinia | ^2.1.0 | State management | Project standard, all stores use it [VERIFIED: package.json] |
| vue-router | ^4.3.0 | Client routing | Project standard [VERIFIED: package.json] |
| axios | ^1.6.0 | HTTP client | Used via `request` wrapper [VERIFIED: package.json] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| 3d-force-graph | ^1.80.0 | 3D graph visualization | Evolution edge rendering in Graph3D.vue |
| echarts | ^5.5.0 | Chart rendering | EvolutionDashboard CII charts |
| three | ^0.185.1 | WebGL 3D engine | Used by 3d-force-graph internally |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| el-drawer for edit | el-dialog | D-12 locks el-drawer; dialog already used in Admin.vue for data source edit — must convert |

**Installation:**
No new packages needed. All dependencies already in package.json.

## Package Legitimacy Audit

No new packages are installed in this phase. All work uses existing dependencies.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | No new packages |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
User Action (click/button)
    │
    ▼
Page Handler (handleSaveSource, handleAddToPlan, etc.)
    │
    ▼
Pinia Store Method (admin.updateSource, learningStore.createPlan)
    │
    ▼
request.get/post/put/delete → Backend API
    │
    ▼
Store updates reactive state
    │
    ├──► ElMessage.success/error (toast feedback)
    ├──► Auto-refresh list (admin.fetchSources, etc.)
    └──► localStorage (plan_id persistence, D-06)
```

For evolution edges:
```
User clicks "显示演化" toggle
    │
    ▼
Home.vue toggleEvolution()
    │
    ▼
graphStore.fetchEvolutionEdges() → GET /evolution/paths/all
    │
    ▼
graphStore.evolutionEdges populated
    │
    ▼
Home.vue graph3DLinks computed merges EVOLVES_TO edges
    │
    ▼
Graph3D.vue renders with trend-based coloring (D-05)
    │
    ▼
User clicks EVOLVES_TO edge → HomeEvolutionPopup.vue detail
```

### Recommended Project Structure
```
frontend/src/
├── pages/                    # Existing pages — modify handlers
│   ├── Admin.vue             # Convert el-dialog → el-drawer
│   ├── LearningCenter.vue    # Add localStorage plan_id logic
│   ├── EvolutionDashboard.vue # Add timeline slider
│   ├── MatchDiagnosis.vue    # Enhance learning path display
│   ├── PipelineMonitor.vue   # Verify PIPE-FE items (mostly done)
│   └── DataDashboard.vue     # Verify DASH-FE items (already done)
├── stores/
│   ├── graph.ts              # Add focusedPositionId, evolutionPaths
│   └── learning.ts           # Add localStorage plan_id methods
├── components/
│   ├── Graph3D.vue           # Add EVOLVES_TO edge coloring
│   └── HomeEvolutionPopup.vue # Already exists, wire edge click
└── composables/
    └── useSSE.ts             # Already complete, no changes needed
```

### Pattern 1: Handler → Store → API → Toast → Refresh
**What:** Every button handler follows the same flow: call store method, show toast, refresh list.
**When to use:** All ADMIN, PIPE-FE, LEARN-FE handlers.
**Example:**
```typescript
// Source: Admin.vue handleSaveSource (existing pattern)
async function handleSaveSource() {
  if (!editingSource.value) return
  editSaving.value = true
  try {
    const payload = { authority_score: editingSource.value.authority_score / 100 }
    await admin.updateSource(editingSource.value.id, payload)
    editDialogVisible.value = false
    ElMessage.success('保存成功')  // D-14
    await admin.fetchSources()     // D-13 auto-refresh
  } catch (e: any) {
    ElMessage.error(e?.message ?? '保存失败，请重试')  // D-14
  } finally {
    editSaving.value = false
  }
}
```

### Pattern 2: localStorage Plan ID Persistence
**What:** Store plan_id in localStorage, validate on mount, clear if invalid.
**When to use:** LearningCenter.vue (D-06, D-07, D-08).
**Example:**
```typescript
// D-06: Store plan_id
const PLAN_ID_KEY = 'starmap_learning_plan_id'

function savePlanId(id: string) {
  localStorage.setItem(PLAN_ID_KEY, id)
}

// D-07: Validate on mount
async function validateStoredPlan() {
  const storedId = localStorage.getItem(PLAN_ID_KEY)
  if (!storedId) return
  try {
    await learningStore.fetchPlan(storedId)
    // If fetchPlan succeeds, currentPlan is set
  } catch {
    localStorage.removeItem(PLAN_ID_KEY)
    learningStore.currentPlan = null
  }
}
```

### Pattern 3: Evolution Edge Overlay in 3D Graph
**What:** EVOLVES_TO edges added as extra links to graph3DLinks computed when showEvolution is true.
**When to use:** Home.vue graph3DLinks computation (EVOLVE-FE-01).
**Example:**
```typescript
// In Home.vue graph3DLinks computed
const graph3DLinks = computed(() => {
  const base = graphStore.visibleEdges.map(e => ({
    source: e.source_id,
    target: e.target_id,
    type: e.type,
    properties: e.properties,
  }))
  // Add evolution edges when layer is active (D-03: 3D only)
  if (showEvolution.value && viewMode.value === '3d') {
    const evoLinks = graphStore.evolutionEdges
      .filter(e => {
        // D-04: Only within current domain
        if (graphStore.expandedKAId) {
          const sourceInDomain = /* check source position belongs to current KA */
          const targetInDomain = /* check target position belongs to current KA */
          return sourceInDomain || targetInDomain
        }
        return true // domain layer: show all
      })
      .map(e => ({
        source: e.source_id,
        target: e.target_id,
        type: 'EVOLVES_TO',
        properties: e.properties,
      }))
    base.push(...evoLinks)
  }
  return base
})
```

### Anti-Patterns to Avoid
- **Don't create new stores for features that fit existing stores.** Evolution edges belong in graphStore (already there). Learning plan persistence belongs in learningStore.
- **Don't duplicate API calls.** If a store method already calls the endpoint, call the store method from the handler — don't call request directly.
- **Don't use el-dialog for edit forms.** D-12 mandates el-drawer for all edit scenarios. Admin.vue currently uses el-dialog for data source edit — must convert.
- **Don't render evolution edges in 2D view.** D-03 explicitly limits to 3D only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE connection | Custom EventSource wrapper | useSSE composable | Already handles reconnect, backoff, polling fallback |
| Toast notifications | Custom toast system | ElMessage from Element Plus | Project standard, D-14 specifies text |
| Confirm dialogs | Custom confirm modal | ElMessageBox.confirm | Already used in Admin.vue |
| HTTP requests | Raw fetch/axios calls | request wrapper + Pinia store methods | Consistent error handling, loading state |
| Edit form containers | el-dialog | el-drawer (D-12) | Unified UX decision |

**Key insight:** The codebase already has all the infrastructure. Phase 3 is almost entirely about wiring, not building.

## Common Pitfalls

### Pitfall 1: Admin.vue el-dialog vs el-drawer inconsistency
**What goes wrong:** Admin.vue data source edit uses el-dialog but D-12 mandates el-drawer. Other edit scenarios may also use dialog.
**Why it happens:** el-dialog was used before D-12 was decided.
**How to avoid:** Convert all edit dialogs to el-drawer with `direction="rtl"` (right slide). Check ReviewQueuePanel.vue too.
**Warning signs:** Search for `el-dialog` in page components that have edit functionality.

### Pitfall 2: Evolution edges not filtered by domain (D-04)
**What goes wrong:** Showing EVOLVES_TO edges that cross knowledge domains, creating visual clutter.
**Why it happens:** `/evolution/paths/all` returns all paths regardless of domain.
**How to avoid:** Filter evolutionEdges in graph3DLinks computed: only include edges where source or target position belongs to the currently expanded KA (when in position layer). At domain layer, show all.
**Warning signs:** Too many edges in 3D view, edges connecting unrelated domain clusters.

### Pitfall 3: localStorage plan_id stale after backend reset
**What goes wrong:** User resets demo data (Admin.vue "重置为演示数据"), but localStorage still has old plan_id that no longer exists.
**Why it happens:** localStorage is not cleared on data reset.
**How to avoid:** D-07 validation on mount handles this — fetchPlan will 404, triggering localStorage.removeItem. Also consider clearing localStorage in the reset handler.
**Warning signs:** LearningCenter shows loading spinner forever after data reset.

### Pitfall 4: Evolution edge click in Graph3D not reaching Home.vue
**What goes wrong:** Graph3D.vue emits nodeClick/nodeDblClick but not linkClick. EVOLVES_TO edge clicks need a different event.
**Why it happens:** 3d-force-graph has onLinkClick but Graph3D.vue doesn't expose it.
**How to avoid:** Add `linkClick` emit to Graph3D.vue, wire `graph.onLinkClick()` to emit the link data. Home.vue handles it to show HomeEvolutionPopup.
**Warning signs:** Clicking evolution edges does nothing.

### Pitfall 5: EvolutionDashboard timeline slider with no snapshot data
**What goes wrong:** GET /evolution/snapshots returns empty array, slider has no options.
**Why it happens:** No snapshots have been generated yet (depends on Phase 4 data flow).
**How to avoid:** Show empty state with message "暂无快照数据" when snapshots array is empty. Disable slider.
**Warning signs:** Slider renders but has no stops, or throws on empty array.

## Code Examples

### Converting el-dialog to el-drawer (ADMIN-02, D-12)
```vue
<!-- BEFORE: el-dialog -->
<el-dialog v-model="editDialogVisible" title="编辑数据源" width="400px">
  <!-- form content -->
  <template #footer>
    <el-button @click="editDialogVisible = false">取消</el-button>
    <el-button type="primary" :loading="editSaving" @click="handleSaveSource">保存</el-button>
  </template>
</el-dialog>

<!-- AFTER: el-drawer (D-12) -->
<el-drawer v-model="editDialogVisible" title="编辑数据源" direction="rtl" size="400px">
  <!-- form content -->
  <template #footer>
    <el-button @click="editDialogVisible = false">取消</el-button>
    <el-button type="primary" :loading="editSaving" @click="handleSaveSource">保存</el-button>
  </template>
</el-drawer>
```

### Evolution edge coloring in Graph3D.vue (EVOLVE-FE-02)
```typescript
// In Graph3D.vue linkColor configuration
.linkColor((link: any) => {
  if (link.type === 'EVOLVES_TO') {
    const trend = link.properties?.trend
    if (trend === 'rising') return '#00ff88'    // green
    if (trend === 'declining') return '#ff6b6b'  // red
    return '#94a3b8'                             // gray (stable)
  }
  return withAlpha(edgeColor(link.type ?? 'DEFAULT'), 0.35)
})
.linkOpacity((link: any) => {
  if (link.type === 'EVOLVES_TO') {
    // D-05: trust_score adjusts opacity
    const trust = link.properties?.weight ?? 0.5
    return 0.3 + trust * 0.5  // range: 0.3-0.8
  }
  return 0.3
})
```

### localStorage plan_id in LearningCenter.vue (D-06, D-07, D-08)
```typescript
const PLAN_ID_KEY = 'starmap_learning_plan_id'

onMounted(async () => {
  // D-07: Validate stored plan_id
  const storedId = localStorage.getItem(PLAN_ID_KEY)
  if (storedId) {
    try {
      await learningStore.fetchPlan(storedId)
    } catch {
      localStorage.removeItem(PLAN_ID_KEY)
    }
  }
  // If no valid stored plan, fetch all plans
  if (!learningStore.currentPlan) {
    await learningStore.fetchPlans()
  }
  await learningStore.fetchRecommendations()
})

// D-06: After creating plan, store plan_id
async function handleCreatePlan(matchResult: any) {
  const plan = await learningStore.createPlan(matchResult)
  localStorage.setItem(PLAN_ID_KEY, plan.plan_id)
}
```

### EvolutionDashboard timeline slider (EVOLVE-FE-04)
```vue
<el-card class="snapshot-card" shadow="hover">
  <template #header>
    <span>快照时间线</span>
  </template>
  <el-slider
    v-model="selectedSnapshotIdx"
    :min="0"
    :max="snapshots.length - 1"
    :step="1"
    :marks="snapshotMarks"
    show-stops
  />
  <div v-if="currentSnapshot" class="snapshot-info">
    <span>{{ currentSnapshot.snapshot_date }}</span>
    <span>{{ currentSnapshot.position_name }}</span>
  </div>
</el-card>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| el-dialog for edits | el-drawer (D-12) | Phase 3 decision | All edit forms must use drawer |
| Hardcoded demo data in LearningCenter | API-driven data | Phase 2 backend | Frontend already calls API, may be done |
| No evolution edge rendering | EVOLVES_TO overlay layer | Phase 2 backend + Phase 3 frontend | New visual feature |
| Memory-only plan_id | localStorage persistence (D-06) | Phase 3 decision | Plan survives page refresh |

**Deprecated/outdated:**
- el-dialog for edit forms: Replace with el-drawer per D-12

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PIPE-FE-01 through PIPE-FE-05 are already implemented based on code inspection | Phase Requirements | Low — verified in PipelineMonitor.vue and usePipelineMonitor.ts |
| A2 | DASH-FE-01 and DASH-FE-02 are already implemented based on code inspection | Phase Requirements | Low — verified in DataDashboard.vue |
| A3 | ADMIN-01 handleSaveSource already calls API (verified in code) | Phase Requirements | Low — verified in Admin.vue lines 171-188 |
| A4 | ADMIN-03 auto-refresh after save is already implemented | Phase Requirements | Low — verified in Admin.vue line 182 |
| A5 | Backend /evolution/snapshots endpoint returns data suitable for timeline slider | EVOLVE-FE-04 | Medium — endpoint exists in schema.ts but response shape needs verification |
| A6 | ReviewQueuePanel.vue has an edit button that needs wiring | ADMIN-02 | Medium — need to check ReviewQueuePanel.vue implementation |

## Open Questions

1. **ReviewQueuePanel.vue edit functionality**
   - What we know: Admin.vue has ReviewQueuePanel component for audit queue
   - What's unclear: Whether ReviewQueuePanel already has an edit button or just approve/reject
   - Recommendation: Read ReviewQueuePanel.vue during planning to determine exact scope

2. **PositionDetail.vue heat column**
   - What we know: MATCH-FE-02 requires heat column visualization
   - What's unclear: Which page has the heat column — PositionDetail.vue or PositionList.vue
   - Recommendation: Check both files during planning

3. **PipelineStageCard failed state styling**
   - What we know: PIPE-FE-01 requires red border on failed stage
   - What's unclear: Current PipelineStageCard styling for failed state
   - Recommendation: Check PipelineStageCard.vue and PipelineDag.vue during planning

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | ✓ | 24.15.0 | — |
| npm | Package management | ✓ | 11.12.1 | — |
| Vue 3 | UI framework | ✓ | ^3.4.0 | — |
| Element Plus | UI components | ✓ | ^2.6.0 | — |
| Pinia | State management | ✓ | ^2.1.0 | — |
| 3d-force-graph | 3D graph rendering | ✓ | ^1.80.0 | — |
| ECharts | Chart rendering | ✓ | ^5.5.0 | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | vitest |
| Config file | vitest.config.ts (project root) |
| Quick run command | `cd frontend && npm run test` |
| Full suite command | `cd frontend && npm run test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADMIN-01 | handleSaveSource calls API | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| ADMIN-02 | Audit edit opens drawer + calls API | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| LEARN-FE-01 | Add to plan calls POST + stores plan_id | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| LEARN-FE-06 | localStorage plan_id validated on mount | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| EVOLVE-FE-01 | Evolution edges rendered in 3D | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| EVOLVE-FE-02 | Edge coloring by trend | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |
| EVOLVE-FE-04 | Timeline slider controls snapshots | unit | `cd frontend && npx vitest run --reporter=verbose` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm run test`
- **Per wave merge:** `cd frontend && npm run test && npm run typecheck && npm run lint`
- **Phase gate:** Full suite green + typecheck clean before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/tests/` — unit tests for store methods and component handlers
- [ ] `frontend/vitest.config.ts` — verify configuration exists
- [ ] Framework install: `cd frontend && npm install` — if node_modules missing

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user system (deferred) |
| V3 Session Management | no | No user system |
| V4 Access Control | no | No user system |
| V5 Input Validation | yes | Element Plus form validation + backend validation |
| V6 Cryptography | no | No crypto in frontend wiring |

### Known Threat Patterns for Vue + Element Plus

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via v-html | Tampering | Never use v-html with user input |
| localStorage injection | Tampering | Validate plan_id on server (D-07) |
| CSRF on API calls | Tampering | Backend CSRF protection (existing) |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: Admin.vue, LearningCenter.vue, EvolutionDashboard.vue, MatchDiagnosis.vue, PipelineMonitor.vue, DataDashboard.vue, Home.vue, Graph3D.vue
- Store inspection: graph.ts, learning.ts, pipeline.ts, admin.ts, dashboard.ts
- Composable inspection: useSSE.ts, usePipelineMonitor.ts
- Component inspection: HomeEvolutionPopup.vue, ReviewQueuePanel.vue (referenced)
- Backend API: evolution.py, learning.py (endpoint signatures verified)
- Schema: schema.ts (evolution paths endpoints confirmed)
- CONTEXT.md decisions (D-01 through D-14)

### Secondary (MEDIUM confidence)
- package.json dependency versions (verified against registry)

### Tertiary (LOW confidence)
- None — all findings based on direct code inspection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies verified in package.json
- Architecture: HIGH - all patterns observed in existing code
- Pitfalls: HIGH - based on direct code inspection and CONTEXT.md decisions
- Already-done items: MEDIUM - verified by code reading but runtime testing needed

**Research date:** 2026-07-06
**Valid until:** 2026-08-06
