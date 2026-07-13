---
wave: 3
depends_on: []
files_modified:
  - frontend/src/stores/__tests__/learning.test.ts
  - frontend/src/stores/__tests__/loop.test.ts
  - frontend/src/stores/__tests__/evolution.test.ts
  - frontend/src/stores/__tests__/dashboard.test.ts
  - frontend/src/stores/__tests__/pipeline.test.ts
  - frontend/src/composables/__tests__/useSSE.test.ts
  - frontend/src/composables/__tests__/useLearningFilters.test.ts
  - frontend/src/composables/__tests__/useLearningActions.test.ts
autonomous: true
requirements: [TEST-04, TEST-05]
---

# PLAN-03: Frontend Tests

**Wave:** 3 (no dependencies — can run in parallel with Wave 1 and 2)
**Goal:** Add tests for 5 core Pinia stores and 3 key composables per DEC-024 (Store + 3 composable all write).

## Tasks

### Task 3.1: Learning Store tests (learning.ts)

<read_first>
- frontend/src/stores/learning.ts (full file — identify all actions, state, computed)
- frontend/src/stores/__tests__/prompt.test.ts (reference pattern for async action testing)
- frontend/src/stores/__tests__/match.test.ts (reference pattern for API mocking)
</read_first>

<action>
Create `frontend/src/stores/__tests__/learning.test.ts` with the following test structure:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLearningStore } from '../learning'

vi.mock('@/api/request', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
```

**Test groups:**

1. **Initial state** — `currentPlan`, `plans`, `recommendations`, `loading`, `error` all have expected defaults

2. **`createPlan` action** — mock `request.post` to return `{ plan_id, position, skills }`, verify `currentPlan` updated and `loading` toggles

3. **`fetchPlan` action** — mock `request.get` to return plan data, verify `currentPlan` set

4. **`fetchPlans` action** — mock `request.get` to return plan list, verify `plans` populated

5. **`updateProgress` action** — mock `request.put` to return updated progress, verify state updated

6. **`fetchRecommendations` action** — mock `request.get` to return recommendations, verify `recommendations` set

7. **`addSkillToPlan` action** — mock `request.post`, verify skill added

8. **`runBatchMatch` action** — mock `request.post` to return match results, verify state

9. **`fetchCompetitiveness` action** — mock `request.get`, verify competitiveness data

10. **`fetchCareerPath` action** — mock `request.get`, verify career path data

11. **`fetchIndustryTrends` action** — mock `request.get`, verify trends data

12. **`restorePlanFromLocalStorage`** — mock `localStorage.getItem`, verify plan restored from cache

13. **Error handling** — mock API to throw, verify `error` state set and `loading` reset

14. **Loading state** — verify `loading` is true during pending request, false after completion

Use `vi.mocked(request.get).mockResolvedValueOnce(...)` pattern. Use `await nextTick()` for reactive state assertions.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/stores/__tests__/learning.test.ts` — all tests pass
- At least 14 test cases covering all 11 actions + initial state + error handling + loading state
- No real API calls (all mocked via `vi.mock`)
- Pinia store is properly reset between tests via `setActivePinia(createPinia())`
</acceptance_criteria>

---

### Task 3.2: Loop Store tests (loop.ts)

<read_first>
- frontend/src/stores/loop.ts (full file — identify all actions, state, computed)
- frontend/src/stores/__tests__/prompt.test.ts (reference pattern)
</read_first>

<action>
Create `frontend/src/stores/__tests__/loop.test.ts` with the following test structure:

**Test groups:**

1. **Initial state** — `currentRun`, `history`, `loading`, `error` defaults

2. **`runLoop` action** — mock `request.post` to return `{ run_id, status, steps, ... }`, verify `currentRun` set

3. **`getStatus` action** — mock `request.get` to return loop status, verify `currentRun` updated

4. **`fetchHistory` action** — mock `request.get` to return history list, verify `history` populated

5. **`resetRun` action** — call resetRun, verify `currentRun` cleared

6. **`parseFlatResult` computed/method** — test with sample flat result data, verify step parsing produces correct `StepResult[]`

7. **Step status parsing** — verify `waiting`/`running`/`success`/`degraded`/`failed` status mapping

8. **Error handling** — mock API to throw, verify `error` state set

9. **Loading state** — verify `loading` toggles during async operations

10. **Timeout handling** — if store has timeout logic, test that it works correctly

Use `vi.mock('@/api/request')` pattern. For `parseFlatResult`, test with concrete sample data matching the API response shape.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/stores/__tests__/loop.test.ts` — all tests pass
- At least 10 test cases covering all actions + computed + error handling
- No real API calls
- Pinia store properly reset between tests
</acceptance_criteria>

---

### Task 3.3: Evolution Store tests (evolution.ts)

<read_first>
- frontend/src/stores/evolution.ts (full file — identify all actions, state, computed)
</read_first>

<action>
Create `frontend/src/stores/__tests__/evolution.test.ts` with the following test structure:

**Test groups:**

1. **Initial state** — `trends`, `snapshots`, `changelog`, `emergingAlerts`, `loading`, `error` defaults

2. **`fetchTrends` action** — mock `request.get` to return trend data, verify `trends` set

3. **`fetchSnapshots` action** — mock `request.get` to return snapshot list, verify `snapshots` populated

4. **`fetchChangelog` action** — mock `request.get` to return changelog entries, verify `changelog` set

5. **`fetchEmergingAlerts` action** — mock `request.get` to return alerts, verify `emergingAlerts` set

6. **Error handling** — mock API to throw, verify `error` state set

7. **Loading state** — verify `loading` toggles during async operations

8. **Multiple fetch actions** — test calling multiple fetch actions in sequence

Use `vi.mock('@/api/request')` pattern.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/stores/__tests__/evolution.test.ts` — all tests pass
- At least 8 test cases covering all 4 fetch actions + initial state + error + loading
- No real API calls
- Pinia store properly reset between tests
</acceptance_criteria>

---

### Task 3.4: Dashboard Store tests (dashboard.ts)

<read_first>
- frontend/src/stores/dashboard.ts (full file — identify all actions, state, computed)
</read_first>

<action>
Create `frontend/src/stores/__tests__/dashboard.test.ts` with the following test structure:

**Test groups:**

1. **Initial state** — `overview`, `trends`, `distribution`, `loading`, `error` defaults

2. **`fetchOverview` action** — mock `request.get` to return overview data (positions, skills, pipeline_runs counts), verify `overview` set

3. **`fetchTrends` action** — mock `request.get` to return trend data, verify `trends` set

4. **`fetchDistribution` action** — mock `request.get` to return skill domain distribution, verify `distribution` set

5. **`fetchAll` action** — mock all three fetch endpoints, verify all state populated after `fetchAll` completes

6. **`addRealtimeEvent` action** — call with a sample SSE event, verify event added to state (e.g., prepended to events list or updates relevant data)

7. **Error handling** — mock API to throw, verify `error` state set

8. **Loading state** — verify `loading` toggles during async operations

Use `vi.mock('@/api/request')` pattern.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/stores/__tests__/dashboard.test.ts` — all tests pass
- At least 8 test cases covering all 5 actions + initial state + error + loading
- No real API calls
- Pinia store properly reset between tests
</acceptance_criteria>

---

### Task 3.5: Pipeline Store tests (pipeline.ts)

<read_first>
- frontend/src/stores/pipeline.ts (full file — identify all actions, state, computed)
</read_first>

<action>
Create `frontend/src/stores/__tests__/pipeline.test.ts` with the following test structure:

**Test groups:**

1. **Initial state** — `status`, `currentRun`, `runs`, `loading`, `error` defaults

2. **`fetchStatus` action** — mock `request.get` to return pipeline status, verify `status` set

3. **`fetchRuns` action** — mock `request.get` to return run list, verify `runs` populated

4. **`triggerRun` action** — mock `request.post` to return trigger response, verify state updated

5. **`cancelRun` action** — mock `request.post` to return cancel response, verify state updated

6. **SSE integration** — if store has SSE-related actions, mock EventSource and test event handling

7. **Error handling** — mock API to throw, verify `error` state set

8. **Loading state** — verify `loading` toggles during async operations

Use `vi.mock('@/api/request')` pattern.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/stores/__tests__/pipeline.test.ts` — all tests pass
- At least 8 test cases covering all actions + initial state + error + loading
- No real API calls
- Pinia store properly reset between tests
</acceptance_criteria>

---

### Task 3.6: useSSE composable tests

<read_first>
- frontend/src/composables/useSSE.ts (full file)
- RESEARCH.md Section 4 (Vitest composable testing approach, Pattern 3)
</read_first>

<action>
Create `frontend/src/composables/__tests__/useSSE.test.ts` with the following test structure:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock EventSource globally
const mockEventSource = {
  close: vi.fn(),
  onopen: null as (() => void) | null,
  onmessage: null as ((ev: MessageEvent) => void) | null,
  onerror: null as ((ev: Event) => void) | null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  url: '',
  readyState: 0,
  withCredentials: false,
}
vi.stubGlobal('EventSource', vi.fn(() => {
  mockEventSource.url = ''
  mockEventSource.readyState = 0
  return mockEventSource
}))
```

**Test groups:**

1. **Connection creation** — `useSSE('/api/v1/test', { onMessage: vi.fn() })` creates EventSource with correct URL including `?token=` query param

2. **Token in query param** — verify EventSource URL includes the auth token for SSE auth (DEC-015)

3. **Message handling** — simulate `onmessage` event, verify `onMessage` callback called with parsed data

4. **Error handling** — simulate `onerror` event, verify error state or reconnection triggered

5. **Disconnect on unmount** — call the returned `disconnect` function, verify `mockEventSource.close` called

6. **Reconnection with backoff** — if composable has exponential backoff, test that reconnection delays increase

7. **Polling fallback** — if composable falls back to polling when SSE fails, test that `request.get` is called as fallback

8. **Event type dispatch** — if composable dispatches different event types, test that `storeHandlers` map routes events correctly

Use `withSetup` helper pattern from RESEARCH.md for composables with lifecycle hooks, or test the composable's returned functions directly if it doesn't use `onMounted`/`onUnmounted`.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/composables/__tests__/useSSE.test.ts` — all tests pass
- At least 8 test cases covering connection, auth, message handling, error, disconnect, reconnection, polling fallback
- EventSource is mocked globally (no real SSE connections)
- Token is passed via query parameter (DEC-015 compliance)
</acceptance_criteria>

---

### Task 3.7: useLearningFilters composable tests

<read_first>
- frontend/src/composables/useLearningFilters.ts (full file)
- RESEARCH.md Section 4 (Pattern 1: Pure composables)
</read_first>

<action>
Create `frontend/src/composables/__tests__/useLearningFilters.test.ts` with the following test structure:

**Test groups:**

1. **Default tab** — `activeTab` defaults to `'all'`

2. **Filter by tab** — set `activeTab` to `'in_progress'`, verify `filteredSkills` returns only skills with matching status

3. **All tab** — `activeTab='all'` returns all skills

4. **Mastered tab** — `activeTab='mastered'` returns only mastered skills

5. **Not started tab** — `activeTab='not_started'` returns only not_started skills

6. **Empty skills list** — with no skills, `filteredSkills` returns empty array

7. **Tab change reactivity** — changing `activeTab` updates `filteredSkills` reactively

This is a pure composable (no API calls, no lifecycle hooks), so it can be tested directly without `withSetup`:
```typescript
const currentPlan = computed(() => ({ skills: [...] }))
const { activeTab, filteredSkills } = useLearningFilters(currentPlan)
```
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/composables/__tests__/useLearningFilters.test.ts` — all tests pass
- At least 7 test cases covering all tab filters + edge cases
- No API mocking needed (pure computed logic)
- Reactive behavior is reactive to `activeTab` changes
</acceptance_criteria>

---

### Task 3.8: useLearningActions composable tests

<read_first>
- frontend/src/composables/useLearningActions.ts (full file)
- frontend/src/stores/learning.ts (for understanding store interaction)
</read_first>

<action>
Create `frontend/src/composables/__tests__/useLearningActions.test.ts` with the following test structure:

**Test groups:**

1. **`handleUpdateStatus`** — mock learning store's `updateProgress`, call `handleUpdateStatus(skillId, newStatus)`, verify store action called with correct args

2. **`handleAddToPlan`** — mock learning store's `addSkillToPlan`, call `handleAddToPlan(skillName)`, verify store action called

3. **Success message** — after successful action, verify `ElMessage.success` called (mock Element Plus)

4. **Error message** — when store action throws, verify `ElMessage.error` called

5. **Confirmation dialog** — if `handleUpdateStatus` shows `ElMessageBox.confirm`, mock it and test both confirm and cancel paths

6. **Loading state** — verify loading ref toggles during async operations

Mock both the Pinia store and Element Plus:
```typescript
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}))
```

Use `setActivePinia(createPinia())` in `beforeEach` and mock the store actions.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run src/composables/__tests__/useLearningActions.test.ts` — all tests pass
- At least 6 test cases covering both actions + success/error messages + confirmation + loading
- Element Plus is mocked (no real UI components)
- Pinia store is mocked for action verification
</acceptance_criteria>

---

### Task 3.9: Verify all frontend tests pass

<read_first>
- All test files created in Tasks 3.1-3.8
- frontend/vite.config.ts (test configuration)
</read_first>

<action>
Run the full frontend test suite to verify:
1. All new tests pass
2. No regressions in existing store/component tests
3. Test count increased by 60+ (8 files * ~8 tests each)

Commands:
```bash
cd frontend && npx vitest run 2>&1 | tail -10
```

If any tests fail, investigate and fix. Common issues:
- Missing `vi.mock` for API modules
- Pinia store not reset between tests
- Element Plus components not properly stubbed
- TypeScript type errors in test files
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run` — 0 failed
- Test count increased by 60+ new tests
- All 5 store test files exist and pass
- All 3 composable test files exist and pass
- No regressions in existing tests (graph, match, prompt, quality, admin, graphNode, resume stores + component tests)
</acceptance_criteria>

---

## Verification

1. Full frontend test suite: `cd frontend && npx vitest run` — 0 failed
2. Per-store verification:
   - `npx vitest run src/stores/__tests__/learning.test.ts`
   - `npx vitest run src/stores/__tests__/loop.test.ts`
   - `npx vitest run src/stores/__tests__/evolution.test.ts`
   - `npx vitest run src/stores/__tests__/dashboard.test.ts`
   - `npx vitest run src/stores/__tests__/pipeline.test.ts`
3. Per-composable verification:
   - `npx vitest run src/composables/__tests__/useSSE.test.ts`
   - `npx vitest run src/composables/__tests__/useLearningFilters.test.ts`
   - `npx vitest run src/composables/__tests__/useLearningActions.test.ts`
4. No regressions: existing store and component tests still pass

## Must-Haves

- [ ] 5 core Store test files exist: learning, loop, evolution, dashboard, pipeline
- [ ] 3 composable test files exist: useSSE, useLearningFilters, useLearningActions
- [ ] Each store test covers all actions + initial state + error handling + loading state
- [ ] useSSE test covers connection, auth (query-param token), message handling, disconnect, reconnection
- [ ] useLearningFilters test covers all tab filters with reactive computed
- [ ] useLearningActions test covers both actions + Element Plus message mocking
- [ ] All frontend tests pass with 0 failures
- [ ] No regressions in existing tests

## Artifacts This Phase Produces

- `frontend/src/stores/__tests__/learning.test.ts` — 14+ tests for learning store
- `frontend/src/stores/__tests__/loop.test.ts` — 10+ tests for loop store
- `frontend/src/stores/__tests__/evolution.test.ts` — 8+ tests for evolution store
- `frontend/src/stores/__tests__/dashboard.test.ts` — 8+ tests for dashboard store
- `frontend/src/stores/__tests__/pipeline.test.ts` — 8+ tests for pipeline store
- `frontend/src/composables/__tests__/useSSE.test.ts` — 8+ tests for SSE composable
- `frontend/src/composables/__tests__/useLearningFilters.test.ts` — 7+ tests for filters composable
- `frontend/src/composables/__tests__/useLearningActions.test.ts` — 6+ tests for actions composable
