# Concerns & Gaps — StarMap

**Analysis Date:** 2026-07-12

## Critical Concerns (阻断性问题)

### 1. No Authentication Login Endpoint

- **Issue:** The backend has NO `/auth/login` or `/auth/token` endpoint. There is no way for users to obtain a JWT token through the application.
- **Files:**
  - Frontend expects token: `frontend/src/stores/user.ts` (reads `starmap_token` from localStorage, decodes JWT)
  - Frontend sends token: `frontend/src/api/request.ts` (line 49: attaches `Authorization: Bearer` header)
  - Backend validates token: `backend/app/dependencies.py` (`get_current_user` requires valid JWT)
  - No login page exists: `frontend/src/router/index.ts` (line 73: `/login` route renders `Home.vue`, not a login form)
- **Impact:** In production (`app_env=production`), ALL API calls return 401. The system only functions in dev mode where `get_current_user` returns a default `{"sub": "dev", "role": "admin"}` user when no token is provided.
- **Fix approach:** Add `POST /auth/login` endpoint to backend that validates credentials and returns a JWT. Create a `Login.vue` page with a login form. Wire the login page to store the JWT in localStorage.

### 2. SSE Connections Bypass Authentication

- **Issue:** Three frontend code paths use `fetch()` or `EventSource` directly, bypassing the axios interceptor that attaches the Bearer token. In production, these requests will be rejected with 401.
- **Files:**
  - `frontend/src/stores/jobseeker.ts` (line 82: `fetch('/api/v1/pipeline/analyze', ...)` — no `Authorization` header)
  - `frontend/src/composables/useSSE.ts` (line 72: `new EventSource(url)` — EventSource API does not support custom headers)
  - `frontend/src/composables/useSSE.ts` (line 170: `fetch(pollUrl, ...)` — no `Authorization` header)
- **Impact:** The jobseeker analysis pipeline (SSE mode) and all dashboard real-time event streams fail in production.
- **Fix approach:** For `fetch()` calls, add `Authorization` header from localStorage. For `EventSource`, pass token as a query parameter and have the backend validate it from query params for SSE endpoints, or use the SSE polling fallback exclusively.

### 3. Learning Plan `createPlan` Request Shape Mismatch

- **Issue:** Frontend `createPlan()` sends a raw `Record<string, unknown>` to `POST /learning/plan`, but the backend requires a strict `CreatePlanRequest` schema with `position: str`, `match_score: float`, and `skills: list[SkillGapInput]` (each with `skill`, `importance`, `gap_level`, `learning_path`).
- **Files:**
  - Frontend store: `frontend/src/stores/learning.ts` (line 201: `createPlan(matchResult: Record<string, unknown>)`)
  - Frontend composable: `frontend/src/composables/useLearningActions.ts` (line 47-53: sends `{ position, skills: [{ skill, importance, gap_level }] }`)
  - Backend schema: `backend/app/api/v1/learning.py` (line 47-53: `CreatePlanRequest` requires `position`, `match_score`, `skills`)
- **Impact:** `useLearningActions` sends `{ skill: "..." }` but backend expects field name `skill` in `SkillGapInput` (correct field name), and `match_score` is missing from the composable payload. The backend returns 422 validation errors.
- **Fix approach:** Create a proper mapping function in the learning store that transforms the match result into the `CreatePlanRequest` shape, including `match_score`, and ensuring all required `SkillGapInput` fields are populated.

---

## Feature Loop Gaps (功能闭环缺失)

### JD Extraction Loop

**Expected flow:** User submits JD text -> backend extracts skills/positions -> results displayed -> data written to Neo4j -> appears in graph

**Actual gaps:**
- **Extraction-to-graph is functional** — `backend/app/api/v1/extract.py` (line 94-119) calls `_write_extraction_to_graph()` which writes to Neo4j. This was previously a gap but is now resolved.
- **Extraction-to-position-record gap** — After extraction, a `PositionRecord` is NOT automatically created in PostgreSQL. The extracted `position_name` exists in Neo4j but `/positions` queries PostgreSQL. Users cannot find their extracted positions in the position list page until a pipeline run imports them.
  - Files: `backend/app/api/v1/extract.py` (writes to Neo4j only), `backend/app/api/v1/position.py` (reads from PostgreSQL only)
- **No "save extraction" confirmation** — The frontend shows extraction results but does not indicate whether the data was persisted to the graph or offer the user a way to verify it appeared in the graph.
  - Files: `frontend/src/stores/jd.ts` (no feedback about graph write status)

### Match Diagnosis Loop

**Expected flow:** User uploads resume -> system extracts skills -> user selects target position -> system matches -> gap analysis displayed -> learning path recommended

**Actual gaps:**
- **Step 4 to Learning Center bridge is broken** — `MatchDiagnosis.vue` (Step 4) shows a `LearningPathPlan.vue` component that only displays gap skills in a timeline. There is NO button or action that creates a learning plan from the match result and navigates to the Learning Center page. The user must separately go to `/learning` and manually trigger plan creation.
  - Files: `frontend/src/pages/MatchDiagnosis.vue`, `frontend/src/components/LearningPathPlan.vue` (no `createPlan` call)
- **Resume skills to match store gap** — After resume parsing, skills are stored in `userStore.parsedSkills` as plain strings. The `matchStore.runMatch()` then reconstructs `PersonSkill[]` objects with fake `skill_id` values (`skill_${name}`). This means proficiency information from the resume parse is partially lost.
  - Files: `frontend/src/stores/match.ts` (line 54: `skill_id: \`skill_${name}\``), `frontend/src/pages/MatchDiagnosis.vue` (line 159-165)
- **Match result not persisted to learning flow** — The `MatchResult` from `/match/position` contains `skill_gap_detail` with structured gap analysis, but when creating a learning plan, the frontend sends a simplified payload that loses this detail.
  - Files: `frontend/src/composables/useLearningActions.ts` (line 47-53: sends minimal data)

### Evolution Tracking Loop

**Expected flow:** Pipeline runs periodically -> detects emerging skills -> displays trends -> triggers alerts

**Actual gaps:**
- **Evolution analysis is NOT scheduled** — `POST /evolution/analyze` exists (line 202 in `backend/app/api/v1/evolution.py`) and queues a Celery task, but there is no periodic trigger. The user must manually call this endpoint.
  - Files: `backend/app/api/v1/evolution.py` (line 202-208)
- **Emerging alerts not consumed by frontend** — `GET /evolution/emerging-alerts` exists in the OpenAPI schema and has a backend implementation (`backend/app/api/v1/evolution_emerging_alerts.py`), but no frontend store or page fetches this endpoint. Alerts are generated but never displayed.
  - Files: Schema defines `/evolution/emerging-alerts`, but `frontend/src/stores/evolution.ts` does not call it.
- **Evolution review queue disconnected from admin** — `GET /evolution/review-queue` returns items needing human review, but the Admin page (`frontend/src/pages/Admin.vue`) uses the separate `/admin/review-queue` endpoint. Evolution review items and admin review items are different data sources with no integration.
  - Files: `backend/app/api/v1/evolution.py` (line 475-500: evolution review queue), `backend/app/api/v1/admin.py` (line 72-83: admin review queue)

### Learning Path Loop

**Expected flow:** Gap analysis -> learning plan generated -> progress tracked -> skills updated -> re-match shows improvement

**Actual gaps:**
- **No re-match after skill mastery** — When a user marks a skill as `mastered` in the Learning Center, there is no mechanism to re-run the match diagnosis to show improved match scores. The learning plan and match diagnosis are disconnected.
  - Files: `frontend/src/composables/useLearningActions.ts` (line 24-36: `handleUpdateStatus` only calls `updateProgress`, no re-match)
- **Skill progress not reflected in user profile** — The `userStore.parsedSkills` is a static list set once during resume upload. When the user masters skills in a learning plan, `parsedSkills` is never updated. Any future match diagnosis will use the original, stale skill list.
  - Files: `frontend/src/stores/user.ts` (line 62: `parsedSkills` only set via `setResume()`)
- **Learning plan creation from match result is manual only** — The `LearningPathPlan.vue` component (Step 4 of MatchDiagnosis) shows learning paths but has no "Create Learning Plan" button. The user must navigate to `/learning` separately and use the `useLearningActions.handleAddToPlan()` which creates a new plan with a single skill rather than the full gap analysis.

### Pipeline Management Loop

**Expected flow:** Trigger pipeline -> monitor progress -> view results -> retry failures

**Actual gaps:**
- **Pipeline trigger requires admin role** — `POST /pipeline/trigger` has `dependencies=[Depends(require_admin)]` (line 178 in `backend/app/api/v1/pipeline/routes.py`). Regular users cannot trigger pipelines from the Pipeline Monitor page. The frontend `usePipelineStore.triggerPipeline()` will get 403 for non-admin users with no clear error message explaining why.
  - Files: `backend/app/api/v1/pipeline/routes.py` (line 178), `frontend/src/stores/pipeline.ts` (line 193-207)
- **Schedule CRUD also requires admin** — All schedule create/update/delete endpoints require admin. The Pipeline Monitor page shows schedule management UI to all authenticated users, but only admins can actually use it.
  - Files: `backend/app/api/v1/pipeline/routes.py` (lines 366, 391, 413, 428)
- **Pipeline config updates are in-memory only** — `PUT /pipeline/config` modifies `settings` object attributes at runtime (line 486-501 in `routes.py`). Changes are lost on server restart. There is no persistence to `.env` file despite the docstring claiming "writes to .env".
  - Files: `backend/app/api/v1/pipeline/routes.py` (line 486-501)

### Admin Review Loop

**Expected flow:** Audit queue -> review items -> approve/reject -> status updated in Neo4j

**Actual gaps:**
- **Admin approve/reject does NOT update Neo4j** — `approveAuditItem` and `rejectAuditItem` in the admin service update the PostgreSQL `review_queue` table status, but do NOT modify the corresponding node's `trust_score` or `status` property in Neo4j. Approved items still appear as low-trust in the graph.
  - Files: `backend/app/api/v1/admin.py` (line 86-107), `backend/app/services/admin_audit_service.py`
- **Graph node approve/reject updates Neo4j but NOT the admin review queue** — The graph node approval endpoints (`/admin/graph/nodes/{id}/approve`, `/admin/graph/nodes/{id}/reject`) update Neo4j but don't remove the item from the admin review queue. Two parallel approval systems exist with no synchronization.
  - Files: `frontend/src/stores/graphNode.ts` (line 65-73), `frontend/src/stores/audit.ts` (line 41-49)
- **Batch audit endpoint exists in backend but frontend uses wrong response shape** — `POST /admin/audit/batch` returns `list[AuditItem]` (line 126-135 in `admin.py`), but `useAuditStore.batchAudit()` casts the response as `AuditItem[]` with a different shape. The frontend `AuditItem` has `id: number`, `type: 'position' | 'skill'`, `name: string`, `trust: number`, `status: string` while the backend `AuditItem` has `id`, `type`, `name`, `trust_score`, `status`.
  - Files: `frontend/src/stores/audit.ts` (line 60-66), `backend/app/services/admin_audit_service.py`

---

## Frontend-Backend API Mismatches

### 1. `/datasources/health` — Missing from OpenAPI Schema

- Frontend calls: `frontend/src/stores/datasource.ts` (line 137: `request.get('/datasources/health')`)
- Backend endpoint exists: `backend/app/api/v1/datasource.py` (line 154: `GET /datasources/health`)
- **Issue:** The endpoint is not in `frontend/src/api/schema.ts`, meaning the typed API client (`frontend/src/api/client.ts`) does not include it. The call uses raw `request.get()` with no type safety.
- **Impact:** If the endpoint path changes, no compile-time error will occur.

### 2. `/match/batch` — Response Shape Mismatch

- Frontend expects: `{ results: BatchMatchItem[] }` or `{ items: BatchMatchItem[] }` (`frontend/src/stores/learning.ts` line 346)
- Backend returns: `{ results: [...], total: N }` (`backend/app/api/v1/match.py` line 206)
- **Issue:** Frontend tries `data.results ?? data.items`. The `data.results` will work, but the `BatchMatchItem` shape differs. Frontend expects `{ resume_name, position_name, match_score, matched_skills, gap_skills }` but backend returns `{ position_name, result: MatchResponse }` or `{ position_name, error: str }`.

### 3. `/learning/plan` — Request Shape Mismatch (Critical)

- Frontend sends: Raw `Record<string, unknown>` from match result (`frontend/src/stores/learning.ts` line 205)
- Backend expects: `CreatePlanRequest` with `{ position: str, match_score: float, skills: [SkillGapInput], available_hours_per_week: float }` (`backend/app/api/v1/learning.py` line 47-53)
- **Issue:** The `useLearningActions` composable sends `{ position, skills: [{ skill, importance, gap_level }] }` but `match_score` is missing. The backend requires `match_score` (has default 0.0 so may pass, but the data is inaccurate). The `skills` array may also be missing required sub-fields like `learning_path`.
- **Impact:** 422 validation errors or silent data loss.

### 4. `/loop/run` — `target_position` is Required but Frontend Sends Optional

- Frontend sends: `{ jd_text, target_position: targetPosition || undefined }` (`frontend/src/stores/loop.ts` line 165)
- Backend requires: `LoopRunRequest` with `target_position: str = Field(..., min_length=1)` (`backend/app/api/v1/loop.py` line 34)
- **Issue:** If `targetPosition` is empty/undefined, the backend returns 422. The LoopDemo page allows running without specifying a target position.
  - Files: `frontend/src/pages/LoopDemo.vue` (line 126: `targetPosition.value || undefined`)

### 5. Dashboard Overview — Field Name Mapping

- Frontend expects: `DashboardOverview` with `today_crawl_volume`, `today_matches`, `quality_score` (`frontend/src/stores/dashboard.ts` line 14-31)
- Backend returns: `OverviewResponse` with `data_volume`, no `today_matches`, `trust_score` not `quality_score` (`backend/app/api/v1/dashboard.py` line 33-51)
- **Issue:** The frontend manually maps field names (line 102-120 in `dashboard.ts`), which works but is fragile. `today_matches` is always 0 because the backend does not provide it.

### 6. Quality Dashboard — Nested Report Structure

- Frontend `fetchQuality()` tries `request.get('/quality/dashboard')` first, then falls back to `/quality/report` (`frontend/src/stores/quality.ts` line 81-86)
- Backend `/quality/dashboard` returns `{ report: QualityReport, ...other_fields }` (nested structure)
- Frontend merges both `data.report` and top-level `data` fields into a flat `QualityMetrics` object (line 87-100)
- **Issue:** The field mapping is implicit and depends on field name overlap. If backend adds a new field with the same name at the top level and inside `report`, the merge behavior is undefined.

---

## Technical Debt Hotspots

### 1. Pervasive `as any` / `as unknown as` Type Casting

- Multiple stores use unsafe type assertions to bridge untyped API responses to typed interfaces.
- Files: `frontend/src/stores/match.ts` (line 63: `data as unknown as MatchResult`), `frontend/src/stores/learning.ts` (line 206: `asRecord(data) as unknown as PlanResponseRaw`)
- **Impact:** Runtime type mismatches silently pass. No compile-time protection.

### 2. Dual Data Source (PostgreSQL + Neo4j) Without Consistency Guarantees

- Positions exist in both PostgreSQL (`PositionRecord`) and Neo4j (`Position` nodes), with no synchronization mechanism.
- Skills exist in both PostgreSQL (`SkillRecord`) and Neo4j (`Skill` nodes).
- Files: `backend/app/api/v1/position.py` (reads PG), `backend/app/api/v1/graph.py` (reads Neo4j)
- **Impact:** Data can be stale in one source. `/positions` may show different results from `/graph/overview` for the same position.

### 3. Two Parallel Review/Audit Systems

- The admin review queue (`/admin/review-queue`) and the evolution review queue (`/evolution/review-queue`) serve similar purposes but use different database tables and different frontend stores.
- Files: `frontend/src/stores/audit.ts`, `backend/app/api/v1/evolution.py` (line 475-500)
- **Impact:** Reviewers must check two separate queues. Items approved in one queue do not affect the other.

### 4. Hardcoded Domain Color Maps in Backend Route Handlers

- The graph overview endpoint contains hardcoded color maps for domain categories directly in the route handler.
- Files: `backend/app/api/v1/graph.py` (line 131-136: `_domain_colors` dict)
- **Impact:** Cannot be updated without code changes and deployment. Should be in configuration or database.

### 5. `update_trust()` Never Called

- The trust integration module implements exponential moving average trust score accumulation, but the method is never invoked by any pipeline or endpoint.
- Files: `backend/app/core/evolution/trust_integration.py` (line 165-189)
- **Impact:** Trust scores remain static. Multiple analyses of the same skill/position do not improve confidence.

### 6. Graph `depth` Parameter Ignored

- `fetch_position_graph()` accepts a `depth` parameter but the Cypher query always does a single-hop traversal.
- Files: `backend/app/services/graph_service.py` (line 208-238)
- **Impact:** Multi-hop skill prerequisite traversal is non-functional.

---

## Security Concerns Remaining

### 1. No Login/Registration System

- There is no way to create user accounts or authenticate users in production. The system relies entirely on dev-mode bypass.
- Files: No `Login.vue` page, no `/auth/` backend routes
- **Current mitigation:** Dev mode returns default admin user
- **Recommendations:** Implement full authentication system with login, registration, and session management

### 2. Pipeline Trigger and Config Endpoints Shown to All Users in Frontend

- The Pipeline Monitor page shows trigger/config/schedule UI to all authenticated users, but the backend restricts these to admin only.
- Files: `frontend/src/pages/PipelineMonitor.vue`, `backend/app/api/v1/pipeline/routes.py` (admin-only decorators)
- **Current mitigation:** Backend returns 403 for non-admin users
- **Recommendations:** Frontend should check `userStore.isAdmin` and hide/disable admin-only controls for non-admin users

### 3. In-Memory Config Changes Without Audit

- `PUT /pipeline/config` modifies runtime settings without writing to persistent storage or creating audit log entries.
- Files: `backend/app/api/v1/pipeline/routes.py` (line 480-502)
- **Recommendations:** Persist config changes to database and create audit trail

### 4. Credentials Hardcoded in Docker Compose

- `docker-compose.dev.yml` and `docker-compose.prod.yml` contain hardcoded passwords like `NEO4J_AUTH=neo4j/starmap123456` and `POSTGRES_PASSWORD=starmap123456`.
- Files: `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Current mitigation:** None
- **Recommendations:** Use Docker Secrets or environment variable files, never commit plaintext passwords

---

## Performance Concerns

### 1. N+1 Query in Position List

- The `/positions` endpoint issues a separate SQL query for each position's skills inside a loop.
- Files: `backend/app/api/v1/position.py` (line 83-98: `skill_stmt` inside `for r in rows` loop)
- **Impact:** With 100 positions, this generates 101 SQL queries. Response time degrades linearly with position count.
- **Improvement path:** Use a single JOIN query or batch-load skills after the position query.

### 2. Reverse Match Scans All Positions

- `POST /match/recommend` loads ALL position names from the database (up to 200) and runs match computation for each one sequentially.
- Files: `backend/app/api/v1/match.py` (line 252-316)
- **Impact:** With 200 positions and Neo4j queries for each, this endpoint can take 30+ seconds.
- **Improvement path:** Pre-compute skill vectors for positions and use vector similarity search instead of brute-force matching.

### 3. Quality Dashboard Builds on Every Request

- `_build_quality_dashboard()` runs 10+ aggregate SQL queries on every `GET /quality/dashboard` call with no caching.
- Files: `backend/app/api/v1/quality.py` (line 79-301)
- **Impact:** Slow response times (1-2 seconds) for a frequently-polled dashboard endpoint.
- **Improvement path:** Cache the dashboard data with a 30-60 second TTL in Redis.

### 4. Unbounded Frontend State Growth in SSE Event Arrays

- The pipeline store and dashboard store accumulate SSE events in reactive arrays, capped at 50-100 items. These are never cleared except on page navigation.
- Files: `frontend/src/stores/pipeline.ts` (line 377: `liveEvents` capped at 50), `frontend/src/stores/dashboard.ts` (line 229: `realtimeEvents` capped at 100)
- **Impact:** Memory usage grows with active SSE connections, especially on the data dashboard which is designed to run continuously.
- **Improvement path:** Use a ring buffer with automatic eviction or periodic cleanup.

### 5. Missing Composite Unique Constraints

- `SkillPrerequisite`, `PositionSkillRelation`, and other junction tables lack `UniqueConstraint`, allowing duplicate rows.
- Files: `backend/app/models/extraction_models.py`
- **Impact:** Data bloat over time. Duplicate rows slow down queries and produce incorrect aggregate counts.
- **Improvement path:** Add `UniqueConstraint` to junction tables and deduplicate existing data.

---

## Recommended Priorities

### P0 — Blocking Production Deployment

1. **Implement authentication login endpoint and login page** — Without this, the system cannot operate in production. Add `POST /auth/login` to backend and create `Login.vue` page.
2. **Fix SSE authentication gaps** — Add `Authorization` headers to all `fetch()` calls in jobseeker store and SSE polling. Implement query-param auth for `EventSource` connections.
3. **Fix `createPlan` request shape mismatch** — Map frontend match result data to backend `CreatePlanRequest` schema properly, including `match_score` and correct `SkillGapInput` fields.

### P1 — Core Feature Loop Completion

4. **Bridge Match Diagnosis Step 4 to Learning Center** — Add "Create Learning Plan" button in `LearningPathPlan.vue` that calls `learningStore.createPlan()` with properly shaped data from the match result.
5. **Auto-create PositionRecord after JD extraction** — When `POST /extract/jd` succeeds, also create/update the `PositionRecord` in PostgreSQL so it appears in `/positions`.
6. **Schedule periodic evolution analysis** — Create a Celery beat schedule or cron trigger for `POST /evolution/analyze` so trends are kept up-to-date without manual intervention.
7. **Consume emerging alerts in frontend** — Add alerts fetching to `evolution.ts` store and display alerts in the Evolution Dashboard page.

### P2 — Data Consistency and UX

8. **Synchronize admin review queue and evolution review queue** — Merge the two review systems or create a unified view. When an item is approved in one, update the other.
9. **Update Neo4j on admin approve/reject** — When a review queue item is approved or rejected, update the corresponding node's trust_score/status in Neo4j.
10. **Hide admin-only pipeline controls for non-admin users** — Check `userStore.isAdmin` in the Pipeline Monitor page and conditionally render trigger/config/schedule UI.
11. **Fix LoopDemo `target_position` optional vs required** — Either make `target_position` optional in the backend `LoopRunRequest` or add frontend validation that requires it before submission.
12. **Update user skills after learning plan progress** — When skills are mastered in a learning plan, update `userStore.parsedSkills` so future match diagnoses reflect progress.

### P3 — Performance and Maintainability

13. **Optimize N+1 queries in position list** — Replace the per-position skill query with a single JOIN or batch query.
14. **Add Redis caching for quality dashboard** — Cache `_build_quality_dashboard()` results with a 30-60 second TTL.
15. **Migrate raw `request.get/post` calls to typed `api.*` client** — Replace `as any` casts with proper typed API calls using the generated client in `frontend/src/api/client.ts`.
16. **Persist pipeline config changes** — Write config updates to database or `.env` file instead of only modifying in-memory settings.
17. **Add composite unique constraints to junction tables** — Prevent duplicate rows in `PositionSkillRelation`, `SkillPrerequisite`, etc.
