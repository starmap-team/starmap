---
phase: 08-backend-cleanup
plan: 01
subsystem: backend-admin-demo-cleanup
tags: [backend, admin, demo-cleanup, openapi, contract]
requires:
  - "Phase 1 review_queue table migration (PERSIST-03)"
  - "Phase 5 dead-endpoint deletion pattern (CLEANUP-01)"
provides:
  - "admin.py with no demo/auto-seed logic (empty review_queue returns [])"
  - "openapi.yaml without /admin/seed/reset path"
  - "9 archived demo seed scripts (ARCHIVE comment, in-place per D-06)"
affects:
  - "frontend Admin.vue reset-demo button (D-03 cleanup routed to Plan 08-04)"
  - "frontend schema.ts resetDemoData type (Plan 08-04 manual sync)"
tech_stack:
  added: []
  patterns:
    - "empty-list-on-empty-table (no env flag, per D-01 / DEC-003)"
    - "in-place archival via # ARCHIVE comment (D-06, preserves module path)"
key_files:
  modified:
    - backend/app/api/v1/admin.py
    - backend/app/api/v1/quality.py
    - backend/scripts/expand_graph.py
    - backend/scripts/seed_pipeline_runs_demo.py
    - backend/scripts/seed_expansion_data_demo.py
    - backend/scripts/seed_datasources_demo.py
    - backend/scripts/seed_cross_domain_demo.py
    - scripts/seed_demo_data.py
    - scripts/seed_jd_data.py
    - scripts/seed_position_skill_records.py
    - scripts/seed_skill_timeseries.py
    - scripts/seed_hardcoded_profiles.py
    - starmap-contracts/openapi.yaml
    - backend/tests/unit/test_admin_endpoints.py
decisions:
  - "D-01 honored: fully removed _DEMO_REVIEW_SEED + auto-seed; empty table returns [] (no opt-in flag)"
  - "D-02 honored: data_sources table untouched; only seed_datasources_demo.py archived"
  - "D-03 honored: /seed/reset + /reset-demo endpoints, ResetDemoResponse model, reset_demo_seed function, and openapi.yaml path all deleted"
  - "D-06 honored: 9 demo scripts archived in-place with # ARCHIVE comment (no file moves)"
metrics:
  duration: 7m
  completed: 2026-07-09
  tasks: 3
  files_modified: 14
  tests: 76 passed
---

# Phase 8 Plan 01: 后端 Demo 数据清理 Summary

Removed all backend demo/auto-seed data-generation logic, cleaned seed-script recommendations, archived 9 demo scripts in-place, and synced the API contract — closing DEMO-01/02/03/04 for the backend layer.

## What Was Done

### Task 1 — admin.py demo removal (DEMO-01, DEMO-02)
- Deleted `ResetDemoResponse` model, `_DEMO_REVIEW_SEED` constant, `total_count` auto-seed block in `get_review_queue`, and the `reset_demo_seed` function with both its `/seed/reset` and `/reset-demo` decorators.
- `get_review_queue` now returns `[]` when the table is empty (docstring updated).
- `test_admin_endpoints.py`: renamed `test_review_queue_auto_seeds_when_empty` → `test_review_queue_returns_empty_when_table_empty` (asserts `items == []`), deleted `TestAdminResetDemo` class, updated header endpoint count 26 → 24 (admin.py 10 → 8).
- Commit: `bdec102`

### Task 2 — seed-script recommendation cleanup (DEMO-03)
- `quality.py:557`: recommendation now says "建议触发 pipeline run 采集真实数据" instead of recommending `seed_expansion_data_demo.py`.
- `expand_graph.py:719`: print now says "(Trigger a pipeline run to fill remaining gaps)".
- Commit: `870ab72`

### Task 3 — demo script archival + openapi sync (DEMO-04, DEMO-02 contract)
- Added `# ARCHIVE: 非生产用，仅开发演示。v2.1 真实数据切换后不再推荐运行。` after the module docstring in all 9 demo scripts (4 in `backend/scripts/`, 5 in root `scripts/`).
- Deleted the `/admin/seed/reset` path + `resetDemoData` operationId (≈20 lines) from `starmap-contracts/openapi.yaml`; `/admin/graph/nodes` now follows `/admin/review-queue/{item_id}` directly. Did NOT run `npm run gen:api` (Plan 08-04 owns frontend schema.ts sync).
- `seed_chroma.py` and `seed_changelog.py` intentionally NOT archived (serve real vector-index init and changelog seeding).
- Commit: `ddc5277`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Aligned two stale FakeAsyncSession arg lists in test_admin_endpoints.py**
- **Found during:** Task 1
- **Issue:** The plan only specified updating the renamed `test_review_queue_returns_empty_when_table_empty` fixture, but `test_review_queue_returns_200` and `test_audit_queue_alias` still passed `[FakeResult(0), FakeResult([...])]` — the `FakeResult(0)` was for the now-deleted `total_count` query. After removing auto-seed, `get_review_queue` issues only one query; the stale `FakeResult(0)` got consumed by the pending-select call, sending the code through the `except Exception: return AuditQueueResponse(items=[])` path. Tests still passed (asserted only `status == 200`) but were exercising the error branch instead of the happy path.
- **Fix:** Changed both fixtures to single-element lists (`[FakeResult([row])]` and `[FakeResult([])]`) so each test exercises the path its name implies.
- **Files modified:** `backend/tests/unit/test_admin_endpoints.py`
- **Commit:** `bdec102` (bundled with Task 1)

No other deviations. Plan executed as written.

## Verification Results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_admin_endpoints.py` | 76 passed |
| `grep` demo refs in `app/` source (excl. pycache) | 0 matches — PASS |
| `grep seed_expansion_data_demo` in quality.py + expand_graph.py | 0 matches — PASS |
| `grep -c "seed/reset" starmap-contracts/openapi.yaml` | 0 — PASS |
| `grep -rl "ARCHIVE: 非生产用"` in backend/scripts/ + scripts/ | 9 files — PASS |
| `seed_chroma.py` / `seed_changelog.py` ARCHIVE check | 0 matches — PASS (not archived) |
| `ruff check` admin.py + quality.py + expand_graph.py + scripts/ | All checks passed |
| `mypy` admin.py + quality.py | Success: no issues in 2 source files |
| `openapi.yaml` YAML validity | Valid |

Notes:
- The 60% coverage gate fails when running a single test file in isolation (38% total) — this is the project-wide gate against the whole suite, not a regression from this plan; out of scope per SCOPE BOUNDARY.
- Pre-existing mypy "unused section(s)" notes in `mypy.ini` are unrelated config warnings.
- Stale `.pyc` files in `__pycache__/` still contain the old symbol names; they regenerate on next import and are gitignored, so they do not affect source verification.

## Known Stubs

None. This plan removed code rather than introducing new behavior; no stubs were created.

## Threat Flags

None. Threat model (T-08-01, T-08-02, T-08-SC) all `accept` disposition; removing the reset-demo endpoint reduces attack surface, `require_admin` dependency on the router is unchanged, and no new network/auth/file surface was introduced.

## Self-Check: PASSED

- FOUND: backend/app/api/v1/admin.py
- FOUND: backend/app/api/v1/quality.py
- FOUND: backend/scripts/expand_graph.py
- FOUND: backend/scripts/seed_pipeline_runs_demo.py
- FOUND: backend/scripts/seed_expansion_data_demo.py
- FOUND: backend/scripts/seed_datasources_demo.py
- FOUND: backend/scripts/seed_cross_domain_demo.py
- FOUND: scripts/seed_demo_data.py
- FOUND: scripts/seed_jd_data.py
- FOUND: scripts/seed_position_skill_records.py
- FOUND: scripts/seed_skill_timeseries.py
- FOUND: scripts/seed_hardcoded_profiles.py
- FOUND: starmap-contracts/openapi.yaml
- FOUND: backend/tests/unit/test_admin_endpoints.py
- FOUND commit: bdec102
- FOUND commit: 870ab72
- FOUND commit: ddc5277
