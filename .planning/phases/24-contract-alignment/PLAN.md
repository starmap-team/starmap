---
phase: 24
name: Contract Alignment — OpenAPI 补齐 + 类型对齐
goal: 补齐 openapi.yaml 缺失的 22 端点，修复 4 个多余/错误路径，统一 ChangeType 枚举，修复 EmergingAlerts 字段缺失
priority: P1
mode: default
---

# PLAN.md — Phase 24: Contract Alignment

## Goal

补齐 `starmap-contracts/openapi.yaml` 缺失的 22 端点，修复 4 个多余/错误路径，统一 ChangeType 枚举标签，修复 EmergingAlerts 接口缺失字段。

## Audit Results (精确)

**Backend endpoints:** 111 (不含 /health 根路径)
**OpenAPI paths:** 93 (含 /health + 3 个多余路径)
**Missing from OpenAPI:** 22
**Extra in OpenAPI:** 4

### Missing (22 endpoints)

| # | Path | Module |
|---|------|--------|
| 1 | POST /admin/audit/batch | admin.py |
| 2 | GET /admin/audit-queue | admin.py (include_in_schema=False — skip) |
| 3 | GET /admin/review-items | admin.py |
| 4 | POST /admin/review/{entity_type}/{entity_id}/submit | admin.py |
| 5 | POST /admin/review/{entity_type}/{entity_id}/approve | admin.py |
| 6 | POST /admin/review/{entity_type}/{entity_id}/reject | admin.py |
| 7 | POST /admin/review/{entity_type}/{entity_id}/unpublish | admin.py |
| 8 | GET /admin/review-stats | admin.py |
| 9 | GET /admin/pipeline/status | admin.py |
| 10 | POST /admin/pipeline/trigger-full | admin.py |
| 11 | GET /admin/audit-events | admin_users.py |
| 12 | GET /admin/users | admin_users.py |
| 13 | POST /admin/users | admin_users.py |
| 14 | GET /admin/users/{user_id} | admin_users.py |
| 15 | PATCH /admin/users/{user_id} | admin_users.py |
| 16 | DELETE /admin/users/{user_id} | admin_users.py |
| 17 | POST /admin/users/{user_id}/unlock | admin_users.py |
| 18 | POST /admin/users/{user_id}/reset-password | admin_users.py |
| 19 | POST /auth/login | auth.py |
| 20 | POST /auth/refresh | auth.py |
| 21 | POST /auth/logout | auth.py |
| 22 | GET /auth/me | auth.py |
| 23 | POST /auth/change-password | auth.py |
| 24 | POST /auth/forgot-password | auth.py |
| 25 | POST /auth/reset-password | auth.py |
| 26 | GET /datasources/health | datasource.py |
| 27 | GET /evolution/changelog/{identifier} (path param rename) | evolution.py |

**Note:** /admin/audit-queue is `include_in_schema=False` — skip it. Actual missing = 26 new + 1 rename = 27 changes.

### Extra / Wrong (4 paths)

| Path | Issue |
|------|-------|
| /admin/sources | Does not exist in backend — remove |
| /datasources/{source_id}/sync | Mounted as admin_router at /admin/datasources/{source_id}/sync — fix prefix |
| /evolution/changelog/{position} | Backend uses {identifier} — rename param |
| /health | Root-level, not /api/v1 — keep but document |

## Success Criteria

1. openapi.yaml has ≥ 118 paths (93 - 4 extra + 27 new/rename - 1 skip)
2. No paths in openapi.yaml that don't exist in backend
3. `npm run gen:api` succeeds
4. `vue-tsc --noEmit` passes
5. EvolutionChangelogDrawer shows correct ChangeType labels
6. EmergingAlerts interface includes source_count, trend, portability_score

## Tasks

### Task 1: OpenAPI — Auth 模块 (7 endpoints) [~25min]

**Add paths to** `starmap-contracts/openapi.yaml`:
- POST /auth/login → LoginResponse
- POST /auth/refresh → RefreshResponse
- POST /auth/logout → 204
- GET /auth/me → UserInfo
- POST /auth/change-password → 200
- POST /auth/forgot-password → 200
- POST /auth/reset-password → 200

**Add schemas:** LoginRequest, LoginResponse, RefreshRequest, RefreshResponse, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest

**Reference:** `backend/app/api/v1/auth.py`

### Task 2: OpenAPI — Admin Review + Pipeline (9 endpoints) [~30min]

**Add paths to** `starmap-contracts/openapi.yaml`:
- POST /admin/audit/batch → list[AuditItem]
- GET /admin/review-items → ReviewListResponse
- POST /admin/review/{entity_type}/{entity_id}/submit → 200
- POST /admin/review/{entity_type}/{entity_id}/approve → 200
- POST /admin/review/{entity_type}/{entity_id}/reject → 200
- POST /admin/review/{entity_type}/{entity_id}/unpublish → 200
- GET /admin/review-stats → ReviewStatsResponse
- GET /admin/pipeline/status → PipelineStatusResponse
- POST /admin/pipeline/trigger-full → PipelineTriggerResponse

**Add schemas:** BatchAuditRequest, ReviewListResponse, ReviewStatsResponse, PipelineTriggerResponse

**Reference:** `backend/app/api/v1/admin.py`

### Task 3: OpenAPI — Admin Users (8 endpoints) [~25min]

**Add paths to** `starmap-contracts/openapi.yaml`:
- GET /admin/users → list[UserDetailResponse]
- POST /admin/users → UserDetailResponse (201)
- GET /admin/users/{user_id} → UserDetailResponse
- PATCH /admin/users/{user_id} → UserDetailResponse
- DELETE /admin/users/{user_id} → 204
- POST /admin/users/{user_id}/unlock → 200
- POST /admin/users/{user_id}/reset-password → 200
- GET /admin/audit-events → list[AuditEventResponse]

**Add schemas:** UserCreateRequest, UserUpdateRequest, UserDetailResponse, AuditEventResponse

**Reference:** `backend/app/api/v1/admin_users.py`

### Task 4: OpenAPI — Fix extras + datasource health + changelog rename [~15min]

**Changes to** `starmap-contracts/openapi.yaml`:
- Remove `/admin/sources` (does not exist in backend)
- Fix `/datasources/{source_id}/sync` → `/admin/datasources/{source_id}/sync` (admin_router prefix)
- Add PUT `/admin/datasources/{source_id}` (admin_router endpoint)
- Rename `/evolution/changelog/{position}` → `/evolution/changelog/{identifier}` (param name only)
- Add GET `/datasources/health` → DatasourcesHealthResponse

**Reference:** `backend/app/api/v1/datasource.py`, `backend/app/api/v1/evolution.py:211`

### Task 5: gen:api + 前端类型修复 [~30min]

**Steps:**
1. Run `cd frontend && npm run gen:api`
2. Check generated `schema.ts` for new types
3. Update stores/components that reference old types if needed
4. `vue-tsc --noEmit` passes

### Task 6: ChangeType 枚举统一 + ChangelogDrawer 修复 [~20min]

**Files:** `frontend/src/types/evolution.ts`, `frontend/src/components/EvolutionChangelogDrawer.vue`

**Steps:**
1. Add ChangeType union in evolution.ts:
   ```typescript
   export type ChangeType = 'added_required' | 'added_preferred' | 'removed' | 'promoted' | 'demoted' | 'retained'
   ```
2. Update ChangelogDrawer label map — keep existing Chinese labels where they match:
   - `added_required` → "新增必需" (current label, keep)
   - `added_preferred` → "新增优先" (current label, keep)
   - `removed` → "移除"
   - `promoted` → "提升"
   - `demoted` → "降级"
   - `retained` → "保留"
3. Remove legacy entries (proficiency_change, requirement_change, new_skill, removed_skill, trend_change, confidence_change)

### Task 7: EmergingAlerts 接口补齐 [~15min]

**Files:** `frontend/src/types/evolution.ts`, `frontend/src/stores/evolution.ts`

**Steps:**
1. Add missing fields to EmergingAlert interface:
   ```typescript
   source_count: number
   trend: 'rising' | 'stable' | 'declining'
   portability_score: number
   ```
2. Update `level` type: `string` → `'emerging' | 'rising' | 'stable' | 'declining'`
3. Verify EvolutionDashboard displays new fields (or add display)

## Dependencies

```
Task 1-4 (OpenAPI additions) → parallel, no inter-dependencies
Task 5 (gen:api) → depends on ALL of Task 1-4
Task 6 (ChangeType) → independent, can run in parallel with Task 1-4
Task 7 (EmergingAlerts) → must coordinate with Task 5 (gen:api may generate conflicting types)
```

## Execution Order

| Wave | Tasks | Rationale |
|------|-------|-----------|
| Wave 1 | Task 1-4, Task 6 (parallel) | OpenAPI additions + ChangeType fix — no dependencies |
| Wave 2 | Task 5 | gen:api + type fixes — needs all OpenAPI paths |
| Wave 3 | Task 7 | EmergingAlerts — after gen:api to avoid type conflicts |

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| gen:api overwrites manual type changes | Run gen:api first, then apply Task 6/7 on top |
| Admin router prefix mismatch | datasource admin_router uses /datasources prefix but is mounted under admin — verify actual URL |
| ChangeType label change confuses users | Labels stay same Chinese text, just mapped to correct enum values |
