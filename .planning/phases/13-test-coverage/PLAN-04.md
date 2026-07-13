---
wave: 4
depends_on: [PLAN-01, PLAN-02, PLAN-03]
files_modified:
  - backend/pyproject.toml
autonomous: true
requirements: [TEST-06]
---

# PLAN-04: CI Gate Verification

**Wave:** 4 (blocked on Waves 1+2+3 — all tests must pass and coverage must be sufficient)
**Goal:** Update CI coverage gate from 60% to 70% per DEC-025, verify full test suite passes, verify coverage >= 70%.

## Tasks

### Task 4.1: Update --cov-fail-under to 70 in pyproject.toml

<read_first>
- backend/pyproject.toml (find current --cov-fail-under setting)
</read_first>

<action>
In `backend/pyproject.toml`, find the `--cov-fail-under=60` setting in the `[tool.pytest.ini_options]` section (or `[tool.coverage.run]` section) and change it to `--cov-fail-under=70`.

This implements DEC-025: CI gate 70%, which is 8% below the current actual coverage (~78%) to leave buffer for Phase 14/15 which will add new files with initially 0% coverage.
</action>

<acceptance_criteria>
- `backend/pyproject.toml` contains `--cov-fail-under=70` (not 60)
- The setting is in the correct pytest configuration section
</acceptance_criteria>

---

### Task 4.2: Run full backend test suite with coverage gate

<read_first>
- backend/pyproject.toml (verify the updated gate)
</read_first>

<action>
Run the full backend test suite with the new coverage gate:

```bash
cd backend && poetry run pytest --cov=app --cov-report=term-missing -q 2>&1 | tail -20
```

This must:
1. Show 0 failed tests
2. Show coverage >= 70%
3. NOT exit with error code (the --cov-fail-under=70 gate must pass)

If coverage is below 70%, identify which modules are dragging it down and add targeted tests to bring them above the threshold. Focus on modules with the lowest coverage that have the most lines.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest --cov=app --cov-fail-under=70 -q` exits with code 0
- Coverage report shows >= 70% total coverage
- 0 failed tests
- No error exit from coverage gate
</acceptance_criteria>

---

### Task 4.3: Run full frontend test suite

<read_first>
- frontend/vite.config.ts (test configuration)
</read_first>

<action>
Run the full frontend test suite:

```bash
cd frontend && npx vitest run 2>&1 | tail -10
```

This must show 0 failed tests. Verify that all new store and composable tests from PLAN-03 are included and passing.
</action>

<acceptance_criteria>
- `cd frontend && npx vitest run` — 0 failed
- All new store tests (learning, loop, evolution, dashboard, pipeline) are included
- All new composable tests (useSSE, useLearningFilters, useLearningActions) are included
</acceptance_criteria>

---

### Task 4.4: Final comprehensive verification

<read_first>
- All PLAN-01, PLAN-02, PLAN-03 artifacts
- backend/pyproject.toml
</read_first>

<action>
Run a comprehensive final verification covering all Phase 13 success criteria:

1. **Backend full suite**: `cd backend && poetry run pytest -q` — 0 failed, >= 1500 total tests
2. **Backend coverage gate**: `cd backend && poetry run pytest --cov-fail-under=70 -q` — exits 0
3. **Backend coverage report**: `cd backend && poetry run pytest --cov=app --cov-report=term-missing --tb=no -q 2>&1 | grep -E "TOTAL"` — >= 70%
4. **Frontend full suite**: `cd frontend && npx vitest run` — 0 failed
5. **Core module coverage targets**:
   - `poetry run pytest --cov=app/core/pipeline/orchestrator -q` — >= 60%
   - `poetry run pytest --cov=app/core/extraction/llm_client -q` — >= 50%
   - `poetry run pytest --cov=app/api/v1/extract -q` — >= 60%
   - `poetry run pytest --cov=app/api/v1/graph -q` — >= 65%
6. **Auth guard tests**: `poetry run pytest tests/unit/test_auth_guard.py -v` — all pass
7. **Frontend store tests**: all 5 new store test files exist and pass
8. **Frontend composable tests**: all 3 new composable test files exist and pass

Document the final coverage numbers for the phase completion report.
</action>

<acceptance_criteria>
- Backend: 0 failed, >= 1500 total tests, coverage >= 70%
- Backend: --cov-fail-under=70 gate passes (exit code 0)
- Backend: core module coverage targets met (orchestrator >= 60%, llm_client >= 50%, extract >= 60%, graph >= 65%)
- Frontend: 0 failed, test count increased by 60+
- Frontend: 5 new store test files + 3 new composable test files all exist and pass
- All 41 previously-failing tests now pass
- No regressions in any previously-passing tests
</acceptance_criteria>

---

## Verification

1. Backend full suite: `cd backend && poetry run pytest -q` — 0 failed
2. Backend coverage gate: `cd backend && poetry run pytest --cov-fail-under=70 -q` — exit 0
3. Backend coverage report: `cd backend && poetry run pytest --cov=app --cov-report=term-missing --tb=no -q 2>&1 | grep TOTAL` — >= 70%
4. Frontend full suite: `cd frontend && npx vitest run` — 0 failed
5. All Phase 13 requirement IDs verified: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06

## Must-Haves

- [ ] `--cov-fail-under=70` set in `backend/pyproject.toml`
- [ ] Backend coverage >= 70% with 0 failed tests
- [ ] Frontend 0 failed tests with 60+ new tests
- [ ] All 41 previously-failing backend tests now pass
- [ ] No regressions in any previously-passing tests
- [ ] Core module coverage targets met (orchestrator, llm_client, extract, graph)
- [ ] Auth guard tests cover all major endpoint groups
- [ ] 5 frontend store tests + 3 composable tests exist and pass

## Artifacts This Phase Produces

- Updated `backend/pyproject.toml` — `--cov-fail-under=70`
- Verified test suite (0 failures, coverage >= 70%)
- Phase 13 completion evidence (coverage report, test counts)
