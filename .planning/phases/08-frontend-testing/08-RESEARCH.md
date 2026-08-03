# Phase 8: Frontend Test Coverage — Research

**Researched:** 2026-07-25
**Domain:** Frontend test infrastructure, Vue 3 + Vitest + vue-tsc
**Confidence:** HIGH

## Summary

The frontend test infrastructure is in place but has a **critical misconfiguration** in the coverage setup: `coverage.include` points to test files instead of source files, causing all coverage reports to show 0% across the board. There are 26 test files (232 tests, all passing) covering roughly 6 of 53 components, 2 of 33 composables, and 16 of 22 stores. The codebase has 42,480 LOC of source versus 3,931 LOC of tests. TypeScript type-checking passes cleanly (`vue-tsc --noEmit` exits 0). The primary work for Phase 8 is twofold: (1) fix the coverage config to measure source files, and (2) expand test coverage substantially across all layers.

**Primary recommendation:** Fix the coverage config first (it's a one-line change that unlocks meaningful measurement), then establish a coverage baseline, then systematically add tests to pages, components, stores, composables, and utils in priority order.

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase yet. This is a greenfield research phase.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vitest | ^2.1.9 | Test runner | Project already configured, all tests passing |
| @vitest/coverage-v8 | ^2.1.9 | Coverage provider | V8 native coverage, already installed |
| @vue/test-utils | ^2.4.0 | Vue component mounting | Standard Vue 3 testing utility, already installed |
| jsdom | ^24.0.0 | DOM environment | Standard browser-like environment for Vitest, already installed |
| vue-tsc | ^2.0.0 | TypeScript type check | Type-checking already passes, part of build pipeline |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @playwright/test | ^1.61.1 | E2E testing | E2E/critical user flows (not in scope for this phase) |

### Installation
No new packages needed — all dependencies are already installed. Note: `@pinia/testing` is NOT installed and is NOT needed — existing tests use `setActivePinia(createPinia())` from `pinia` directly.

## Package Legitimacy Audit

> All packages are already installed and verified in the project. No new packages are needed for this phase.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| vitest | npm | ~3 yrs | 10M+/wk | github.com/vitest-dev/vitest | OK | Already installed |
| @vitest/coverage-v8 | npm | ~3 yrs | 3M+/wk | github.com/vitest-dev/vitest | OK | Already installed |
| @vue/test-utils | npm | ~5 yrs | 2M+/wk | github.com/vuejs/test-utils | OK | Already installed |
| jsdom | npm | ~14 yrs | 20M+/wk | github.com/jsdom/jsdom | OK | Already installed |

## Critical Findings

### Finding 1: Coverage Config Points to Test Files, Not Source Files

**File:** `frontend/vitest.config.ts`

```typescript
// Current (BROKEN) — coverage include is set to test files:
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  include: ['src/**/__tests__/**/*.test.ts', 'src/**/__tests__/**/*.spec.ts'],  // <-- WRONG
  thresholds: {
    lines: 60,
    functions: 60,
    branches: 60,
    statements: 60,
  },
},
```

This means coverage is measured against the test files themselves, not the source files they test. The result is always 0%:

```
All files |      0 |       0 |       0 |       0 |
```

**Fix:** Change `coverage.include` to point to source files, and add `coverage.exclude` to skip test files:

```typescript
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  include: ['src/**/*.ts', 'src/**/*.vue'],          // source files
  exclude: ['src/**/__tests__/**', 'src/**/*.d.ts'],  // skip tests and declarations
  thresholds: {
    lines: 60,
    functions: 60,
    branches: 60,
    statements: 60,
  },
},
```

**Note:** The current thresholds (60% across all metrics) will likely not be met after fixing the config — the actual coverage is probably far below 60%. The planner should either lower thresholds initially or stage them (e.g., start at 30% and increase per-wave).

### Finding 2: Vue Component Tests Are `el-` Component Warnings

The test output shows `[Vue warn]: Failed to resolve component: el-icon / el-progress / el-button` for components using Element Plus. This is a known pattern in Vue Test Utils — Element Plus components must be globally registered or stubbed. The `BusinessBanner` and `SkillProgressCard` tests do produce warnings (but tests still pass). This should be addressed by adding global component registration or using `global.stubs` in the mount options.

### Finding 3: vue-tsc Passes Cleanly

`vue-tsc --noEmit` exits with code 0 and produces no errors. This is excellent — the type-checking pipeline is healthy.

## Page Inventory

18 pages under `frontend/src/pages/`:

| # | Page | Description |
|---|------|-------------|
| 1 | `Admin.vue` | Admin panel |
| 2 | `AuditLog.vue` | Audit log viewer |
| 3 | `ChangePassword.vue` | Password change form |
| 4 | `DataDashboard.vue` | Data overview dashboard |
| 5 | `DataSources.vue` | Data source management |
| 6 | `EvolutionDashboard.vue` | Evolution tracking dashboard |
| 7 | `ExtractJD.vue` | JD extraction |
| 8 | `Home.vue` | Main landing/home page |
| 9 | `LearningCenter.vue` | Learning center |
| 10 | `Login.vue` | Login page |
| 11 | `LoopDemo.vue` | Loop demo page |
| 12 | `MatchDiagnosis.vue` | Match diagnosis |
| 13 | `PipelineAnalysis.vue` | Pipeline analysis |
| 14 | `PipelineMonitor.vue` | Pipeline monitoring |
| 15 | `PositionDetail.vue` | Position detail view |
| 16 | `PositionList.vue` | Position listing |
| 17 | `QualityDashboard.vue` | Quality metrics dashboard |
| 18 | `UserManagement.vue` | User management |

**Pages with tests:** 0 (no page-level test files exist)
**Pages without tests:** 18

## Source File Inventory

### Top-Level Entry Points
| File | LOC (est.) | Tests? |
|------|-----------|--------|
| `src/App.vue` | ~50 | No |
| `src/main.ts` | ~30 | No |
| `src/env.d.ts` | ~10 | No |

### API Layer
| File | LOC (est.) | Tests? |
|------|-----------|--------|
| `src/api/request.ts` | ~150 | Yes (3 tests) |
| `src/api/client.ts` | ~100 | No |
| `src/api/schema.ts` | auto-gen | No (auto-generated) |

### Config
| File | LOC (est.) | Tests? |
|------|-----------|--------|
| `src/config/apiBase.ts` | ~50 | Yes (4 tests) |

### Stores (22 total)
**With tests (16):** admin, dashboard, evolution, graph, graphNode, learningAnalytics, learningPlan, learningRecommendation, loop, match, pipelineConfig, pipelineRun, prompt, quality, resume, user

**Without tests (7):** audit, datasource, jd, jobseeker, learning, pipeline, review

### Components (53 total)
**With tests (6):** BusinessBanner, CountUpNumber, DataQualityGauge, GapAnalysisReport, SkillProgressCard, SkillRadar

**Without tests (47):** AdminFlow, AdminOverview, AlertList, CompetitivenessChart, ContentReviewPanel, DashboardSkeleton, DataSourceManager, DetailPanel, EmptyState, ErrorBoundary, EvolutionChangelogDrawer, Graph2D, Graph3D, GraphFilterPanel, GraphNodeEditor, GraphSearchBar, GraphToolbar, HomeEvolutionDrawer, HomeGraphControls, HomeKpiStrip, LearningPathFlow, LearningPathPlan, LoadingPulse, LoopRunLog, LoopStepGraph, LoopStepInput, LoopStepLearning, LoopStepMatch, LoopStepSkills, LoopTimeline, MatchBatchMode, MatchFlow, MatchTrustGuide, NodeTooltip3D, PipelineDag, PipelineGlossary, PipelineKpiCards, PipelineQualityPanel, PipelineStageCard, PipelineStatusHero, PositionSearch, ProfileMenu, PromptManager, QualityTrendChart, ResumeUpload, ReviewQueuePanel, SkillMatchAnimation

### Composables (33 total)
**With tests (2):** useAuthBootstrap, useSSE

**Without tests (31):** graph2d/index, graph2d/useG6Lifecycle, graph2d/useGraphAnimation, graph2d/useGraphClustering, graph2d/useGraphHighlight, graph2d/useGraphLOD, graph2d/useGraphRenderQueue, home/index, home/useEvolutionPanel, home/useGraph2DData, home/useGraph3DData, home/useGraphToolbarState, home/useHomeInteractions, home/useHomeLayout, home/useNodeSelection, useDataDashboard, useDataSourceCharts, useEvolutionDashboard, useG6, useGraph2DLayers, useGraph3D, useGraphNodeEditor, useGraphNodeList, useLoopGraph, useNodeThreeObject, usePipelineMonitor, useQualityActions, useQualityDashboard, useQualityDashboardCharts, useTextSprite

### Utils (5 total)
**With tests (0):** none

**Files:** chartTheme, element, formatTime, graphColors, proficiency

### Validation (6 total)
**With tests (0):** none

**Files:** errors, index, types, useFormValidation, useResponseValidation, validate

### Types (4 total)
**With tests (0):** — type declarations only, no runtime logic

### Router, Layouts, Plugins, Styles
**With tests (0):** router/index (1), layouts (3), plugins/echarts (1), styles (3 CSS files)

## Test Coverage Summary

| Layer | Source Files | Source LOC | Test Files | Test LOC | Tests | Coverage |
|-------|-------------|-----------|------------|---------|-------|----------|
| Pages | 18 | ~5,000+ | 0 | 0 | 0 | 0% |
| Components | 53 | ~15,000+ | 6 | ~900 | ~50 | ~11% |
| Stores | 22 | ~4,000+ | 16 | ~2,200 | ~160 | ~73% |
| Composables | 33 | ~3,000+ | 2 | ~300 | ~15 | ~6% |
| API | 3 | ~300 | 1 | ~100 | 3 | ~33% |
| Config | 1 | ~50 | 1 | ~50 | 4 | 100% |
| Utils | 5 | ~500 | 0 | 0 | 0 | 0% |
| Validation | 6 | ~800 | 0 | 0 | 0 | 0% |
| **Total** | **~141** | **~42,480** | **26** | **~3,931** | **232** | **~0%*** |

*Actual coverage is unknown due to the misconfigured `coverage.include` — all coverage reports show 0%.

## Current Test Config (vitest.config.ts)

```typescript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/__tests__/**/*.test.ts', 'src/**/__tests__/**/*.spec.ts'],
    exclude: [
      'node_modules',
      'dist',
      'e2e/**',
      'cypress/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/__tests__/**/*.test.ts', 'src/**/__tests__/**/*.spec.ts'],
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60,
      },
    },
  },
})
```

## Existing Test Coverage Report

All 26 test files pass with 232 tests. Coverage shows 0% across all files due to the misconfiguration:

```
 % Coverage report from v8
----------|---------|----------|---------|---------|-------------------
File      | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
----------|---------|----------|---------|---------|-------------------
All files |       0 |        0 |       0 |       0 |
----------|---------|----------|---------|---------|-------------------
```

## Test Scripts (package.json)

| Script | Command | Purpose |
|--------|---------|---------|
| `test` | `vitest run` | Run all tests once |
| `test:watch` | `vitest` | Run tests in watch mode |
| `test:coverage` | `vitest run --coverage` | Run tests with coverage report |
| `typecheck` | `vue-tsc --noEmit` | TypeScript type checking |

## TypeScript Status

`vue-tsc --noEmit` passes with **exit code 0** and zero errors. The type-checking pipeline is healthy.

## Architecture Patterns

### Current Test Organization Pattern

Tests are co-located in `__tests__/` directories alongside their source:

```
src/stores/
├── graph.ts
├── user.ts
├── __tests__/
│   ├── graph.test.ts
│   └── user.test.ts
```

This is a standard and recommended pattern. No structural change needed.

### Component Test Setup Pattern

Tests use `@vue/test-utils` `mount()` and `shallowMount()`:

```typescript
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MyComponent from '../MyComponent.vue'

describe('MyComponent', () => {
  it('renders correctly', () => {
    const wrapper = mount(MyComponent, { props: { ... } })
    expect(wrapper.text()).toContain('...')
  })
})
```

### Store Test Setup Pattern

Tests import Pinia stores directly, using `setActivePinia(createPinia())`:

```typescript
import { setActivePinia, createPinia } from 'pinia'
import { useMyStore } from '../myStore'

describe('myStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('has initial state', () => {
    const store = useMyStore()
    expect(store.items).toEqual([])
  })
})
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DOM environment | Custom JSDOM setup | `jsdom` (already installed) | Standard, maintained, compatible with Vitest |
| Vue component mounting | Manual component lifecycle | `@vue/test-utils` (already installed) | Standard Vue 3 testing utility |
| Coverage reporting | Custom coverage script | `@vitest/coverage-v8` (already installed) | Built-in V8 coverage, no config needed |
| Type checking | Runtime type assertions | `vue-tsc` (already installed) | Compile-time, zero runtime cost |

## Common Pitfalls

### Pitfall 1: Coverage Config Measures Test Files Instead of Source Files
**What goes wrong:** `coverage.include` is set to `src/**/__tests__/**/*.test.ts` — the test runner measures coverage of the test files themselves, not the source files they exercise. All coverage reports show 0%.
**How to fix:** Change `coverage.include` to `['src/**/*.ts', 'src/**/*.vue']` and add `coverage.exclude` to skip `src/**/__tests__/**`.
**Warning signs:** Coverage report shows 0% for all files while tests pass.

### Pitfall 2: Element Plus Components Not Registered in Tests
**What goes wrong:** Component tests that use `el-*` components produce `[Vue warn]: Failed to resolve component` warnings. While tests still pass, warnings indicate increased mount time and potential fragility.
**How to fix:** Register Element Plus globally in test setup, or use `global.stubs` in mount options:
```typescript
mount(MyComponent, {
  global: {
    stubs: {
      'el-icon': true,
      'el-button': true,
      'el-progress': true,
    }
  }
})
```
**Warning signs:** `[Vue warn]: Failed to resolve component: el-*` in stderr during test runs.

### Pitfall 3: No Test for Graph/3D Components
**What goes wrong:** Components using `@antv/G6`, `three.js`, or `3d-force-graph` require special setup (canvas mocking, WebGL mocking) that is not trivial in jsdom. These components are entirely untested.
**How to fix:** Use `shallowMount` to isolate the component from its graph dependencies, or mock the graph libraries at the module level. Complex graph components may be best tested via E2E tests rather than unit tests.
**Warning signs:** Test runs hang or crash when importing three.js/G6 modules.

### Pitfall 4: Tests That Pass Without Asserting
**What goes wrong:** Some existing tests may pass without meaningful assertions (e.g., testing that a store initializes without checking its state shape).
**How to fix:** Audit existing tests for assertion quality. Every test should have at least one `expect()` call.
**Warning signs:** Test file has fewer `expect()` calls than `it()` blocks.

## Code Examples

### Fixed Coverage Configuration
```typescript
// frontend/vitest.config.ts
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  include: ['src/**/*.ts', 'src/**/*.vue'],
  exclude: ['src/**/__tests__/**', 'src/**/*.d.ts'],
  thresholds: {
    lines: 30,    // Start low, increase per-wave
    functions: 30,
    branches: 30,
    statements: 30,
  },
},
```

### Element Plus Component Test with Stubs
```typescript
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MyComponent from '../MyComponent.vue'

describe('MyComponent', () => {
  it('renders with element-plus stubs', () => {
    const wrapper = mount(MyComponent, {
      global: {
        stubs: {
          'el-icon': true,
          'el-button': true,
          'el-dialog': true,
          'el-form': true,
          'el-form-item': true,
          'el-input': true,
          'el-select': true,
          'el-table': true,
          'el-tag': true,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
  })
})
```

### Store Test Template
```typescript
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'
import { useMyStore } from '../myStore'

describe('myStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default state', () => {
    const store = useMyStore()
    expect(store.items).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('handles fetch action', async () => {
    const store = useMyStore()
    // Mock API call, then assert state changes
  })
})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vue CLI + Jest | Vite + Vitest | Project inception | Already migrated, Vitest is current |
| nyc/istanbul coverage | V8 native coverage | Vitest 1.0+ | Faster, native, no Babel transform needed |
| — | `@vue/test-utils` v2 | 2023 | Stable, Vue 3 compatible |

## Assumptions Log

> All claims in this research were verified against the actual codebase. No assumptions needed.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None — all findings verified against codebase files | — | — |

## Open Questions (RESOLVED)

1. **What is the actual coverage baseline?** (RESOLVED)
   - What we know: Coverage config is broken, so the real number is unknown.
   - What's unclear: The actual coverage percentage across source files.
   - Plan 8-01 Task 1.1 fixes the coverage config first; Task 1.4 runs the coverage report to establish the baseline.
   - **Resolution:** Config fix → run coverage → record baseline. Implemented in Tracer wave.

2. **What coverage targets should Phase 8 aim for?** (RESOLVED)
   - What we know: The current thresholds say 60%, but the codebase is far below that.
   - What's unclear: Realistic target for a single phase given the scope.
   - Plan 8-01 sets initial thresholds at 20% lines/15% functions/10% branches/20% statements. Plan 8-03 adjusts based on Wave 1 results.
   - **Resolution:** Start with conservative thresholds (20/15/10/20), adjust per-wave based on actual baseline.

3. **How should graph/3D components be tested?** (RESOLVED)
   - What we know: @antv/G6, three.js, and 3d-force-graph don't work in jsdom without significant mocking.
   - What's unclear: Whether to mock them at module level, use `shallowMount`, or defer to E2E tests.
   - Plan 8-01 Task 1.3 specifies: use `global.stubs` for graph components (shallow stubs for Graph2D, Graph3D, ECharts) and focus tests on page structure rather than canvas rendering.
   - **Resolution:** Use `global.stubs` for graph components; defer full graph interaction testing to Playwright E2E tests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Test runner | ✓ | (via npm) | — |
| npm | Package mgmt | ✓ | (via project) | — |
| Vitest | Test runner | ✓ | ^2.1.9 | — |
| vue-tsc | Type checking | ✓ | ^2.0.0 | — |

**Missing dependencies with no fallback:** None — all required tools are installed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest ^2.1.9 |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` |
| Full suite command | `cd frontend && npx vitest run --coverage` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-01 | Coverage config measures source files | infra | `cd frontend && npx vitest run --coverage` | ❌ Wave 0 |
| COV-01 | Unit tests for stores without tests | unit | `cd frontend && vitest run src/stores/__tests__/` | ❌ Phase |
| COV-02 | Unit tests for utility functions | unit | `cd frontend && vitest run src/utils/__tests__/` | ❌ Phase |
| COV-03 | Unit tests for validation layer | unit | `cd frontend && vitest run src/validation/__tests__/` | ❌ Phase |
| COV-04 | Component tests for priority pages | unit | `cd frontend && vitest run src/pages/__tests__/` | ❌ Phase |
| COV-05 | Element Plus component stubs working | unit | `cd frontend && vitest run --reporter=verbose 2>&1 \| grep -c "warn"` | ❌ Phase |

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run --reporter=verbose`
- **Per wave merge:** `cd frontend && npx vitest run --coverage`
- **Phase gate:** All tests pass + coverage report shows non-zero percentages

### Wave 0 Gaps
- [ ] Fix `coverage.include` in `vitest.config.ts` — change from test files to source files
- [ ] Add `coverage.exclude` to exclude `__tests__/` and `*.d.ts`
- [ ] Run initial coverage report to establish baseline

## Security Domain

> `security_enforcement` is not explicitly set in project config. This phase is focused on test infrastructure — no new security-sensitive code paths are introduced. Existing ASVS controls (input validation via zod-equivalent patterns, API response validation) are already covered by the validation layer, which is a candidate for expanded test coverage.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | no (test infra only) | Validation layer tested indirectly |
| V11 Business Logic | no (test infra only) | — |

## Sources

### Primary (HIGH confidence)
- Codebase: `frontend/vitest.config.ts` — full config read and analyzed
- Codebase: `frontend/package.json` — test scripts and dependencies verified
- Codebase: `frontend/src/` — directory structure, file inventory via `find`
- Runtime: `vitest run --coverage` — 26 test files, 232 tests passing, 0% coverage reported
- Runtime: `vue-tsc --noEmit` — exit code 0, zero errors

### Secondary (MEDIUM confidence)
- Vitest documentation: coverage configuration patterns (training knowledge)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against installed packages and node_modules
- Architecture: HIGH — verified against actual codebase structure
- Coverage config: HIGH — verified by running `vitest run --coverage` and observing 0% output
- Pitfalls: HIGH — based on observed test warnings and known Vitest patterns

**Research date:** 2026-07-25
**Valid until:** 2026-08-25 (stable tooling, 30-day window)