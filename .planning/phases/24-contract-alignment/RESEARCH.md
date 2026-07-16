# RESEARCH.md — Phase 24: Contract Alignment

**Date:** 2026-07-16
**Scope:** ALIGN-01 (OpenAPI gaps), ALIGN-04 (ChangeType), ALIGN-05 (Evolution types), EmergingAlerts mismatch

## Precise Audit Results

### Backend Endpoints: 111 (under /api/v1)
### OpenAPI Paths: 93 (includes /health root + 3 stale paths)
### Missing: 22 new endpoints + 1 param rename + 2 admin_router paths
### Extra/Stale: 4 paths

### Missing from OpenAPI (22 + admin_router paths)

**Auth module (7 — entirely missing):**
- POST /auth/login, POST /auth/refresh, POST /auth/logout
- GET /auth/me, POST /auth/change-password
- POST /auth/forgot-password, POST /auth/reset-password

**Admin review/pipeline (9):**
- POST /admin/audit/batch
- GET /admin/review-items
- POST /admin/review/{entity_type}/{entity_id}/submit|approve|reject|unpublish
- GET /admin/review-stats
- GET /admin/pipeline/status, POST /admin/pipeline/trigger-full

**Admin users (8):**
- GET /admin/users, POST /admin/users
- GET /admin/users/{user_id}, PATCH /admin/users/{user_id}
- DELETE /admin/users/{user_id}
- POST /admin/users/{user_id}/unlock, POST /admin/users/{user_id}/reset-password
- GET /admin/audit-events

**Datasource (1):**
- GET /datasources/health

**Admin datasource (2 — from admin_router):**
- PUT /admin/datasources/{source_id}
- POST /admin/datasources/{source_id}/sync

**Param rename (1):**
- /evolution/changelog/{position} → {identifier}

### Extra/Stale in OpenAPI (4)
- /admin/sources — does not exist in backend
- /datasources/{source_id}/sync — wrong prefix (should be /admin/datasources/...)
- /evolution/changelog/{position} — param should be {identifier}
- /health — root-level, valid but not under /api/v1

### ChangeType Enum: PARTIAL MISMATCH
- Backend: added_required, added_preferred, removed, promoted, demoted, retained
- Frontend schema.ts: matches backend ✅
- ChangelogDrawer: has 6 legacy labels (proficiency_change, etc.) that no backend value produces
- Fix: update label map to use backend values, keep Chinese labels

### EmergingAlerts: MISSING 3 FIELDS
- Missing: source_count, trend, portability_score
- Level type: frontend omits "stable" which backend includes
- Backend uses "rising" not "growing"

### Evolution Trends: ALIGNED ✅
