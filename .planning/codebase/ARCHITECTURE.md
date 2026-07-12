# Architecture — StarMap

**Analysis Date:** 2026-07-12

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3 + Pinia)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ Home.vue │ │ExtractJD │ │MatchDiag │ │Evolution │ │Learning  │     │
│  │  +Graph  │ │  .vue    │ │  .vue    │ │Dashboard │ │Center    │     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘     │
│       │            │            │            │            │             │
│  ┌────┴────────────┴────────────┴────────────┴────────────┴──────┐     │
│  │              Pinia Stores (18 stores)                         │     │
│  │  graph | jd | match | evolution | learning | pipeline | ...  │     │
│  └──────────────────────┬───────────────────────────────────────┘     │
│                         │ axios (request.ts)                          │
│  ┌──────────────────────┴───────────────────────────────────────┐     │
│  │              SSE (useSSE.ts) — realtime events               │     │
│  └──────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ HTTP / SSE
┌────────────────────────────────┴─────────────────────────────────────┐
│                     FastAPI Backend (/api/v1)                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  API Layer (app/api/v1/) — 14 route modules                   │  │
│  │  extract | match | evolution | learning | pipeline | admin    │  │
│  │  graph | position | resume | quality | judge | datasource     │  │
│  │  dashboard | loop                                              │  │
│  └───────────────────────┬────────────────────────────────────────┘  │
│                          │                                           │
│  ┌───────────────────────┴────────────────────────────────────────┐  │
│  │  Service Layer (app/services/) — 16 service modules            │  │
│  │  match_service | graph_service | learning_service | neo4j_*    │  │
│  │  resume_service | judge_service | admin_* | dedup_service      │  │
│  └───────────────────────┬────────────────────────────────────────┘  │
│                          │                                           │
│  ┌───────────────────────┴────────────────────────────────────────┐  │
│  │  Core Layer (app/core/) — 8 domain modules                    │  │
│  │  extraction/ | matching/ | learning/ | evolution/ | pipeline/  │  │
│  │  dashboard/ | hallucination/ | trust/                          │  │
│  └───────────────────────┬────────────────────────────────────────┘  │
│                          │                                           │
│  ┌───────────────────────┴────────────────────────────────────────┐  │
│  │  Models (app/models/) — 4 ORM modules                         │  │
│  │  extraction_models | evolution_models | learning_models        │  │
│  │  pipeline_models                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴─────┐        ┌────┴─────┐        ┌────┴─────┐
    │PostgreSQL│        │  Neo4j   │        │  Redis   │
    │(asyncpg) │        │(py2neo)  │        │(pub/sub) │
    └──────────┘        └──────────┘        └──────────┘
```

## Backend Architecture

### Layered Architecture: API -> Service -> Core -> Models

**API Layer** (`backend/app/api/v1/`):
- Thin HTTP handlers: request parsing, dependency injection, domain-exception to HTTP-exception mapping, response serialization
- All routes aggregated in `router.py` under `/api/v1` prefix with `get_current_user` dependency
- Sub-routers split by domain in Phase 7 (e.g., `evolution_career_path.py`, `admin_graph_nodes.py`, `admin_prompts.py`)

**Service Layer** (`backend/app/services/`):
- Business logic orchestration: `match_service.py`, `graph_service.py`, `learning_service.py`, `neo4j_service.py`
- Admin services: `admin_audit_service.py`, `admin_graph_service.py`, `admin_ab_service.py`
- Infrastructure: `resources.py` (PostgreSQL/Neo4j/Redis connection lifecycle), `dedup_service.py`, `graph_sync.py`

**Core Layer** (`backend/app/core/`):
- Domain logic isolated from HTTP concerns:
  - `extraction/`: JD extraction pipeline, LLM client, normalization, graph writer, hallucination guard
  - `matching/`: match scoring, prerequisite path builder, caching
  - `learning/`: path engine, progress tracker
  - `evolution/`: emergence finder, diff engine, snapshot manager, timeseries loader, trust integration
  - `pipeline/`: orchestrator, executor, loop orchestrator, quality monitor, cron scheduler, bootstrap
  - `dashboard/`: dashboard service, SSE broadcaster

**Models Layer** (`backend/app/models/`):
- SQLAlchemy ORM models: `extraction_models.py` (PositionRecord, SkillRecord, JDExtractionRecord, ReviewQueue), `evolution_models.py` (EvolutionChangelog, EvolutionPath, EvolutionSnapshot, SkillTimeseries), `learning_models.py` (LearningPlan, LearningProgress), `pipeline_models.py` (PipelineRun, PipelineSchedule, DataSourceRecord)

### Key Modules and Responsibilities

| Module | Responsibility | File |
|--------|----------------|------|
| Router Aggregator | Mounts all API sub-routers under /api/v1 | `backend/app/api/v1/router.py` |
| Auth Dependencies | JWT validation, admin role check | `backend/app/dependencies.py` |
| App Entry | FastAPI app, lifespan, middleware (CORS, rate-limit, security headers) | `backend/app/main.py` |
| Resource Init | PostgreSQL/Neo4j/Redis connection lifecycle | `backend/app/services/resources.py` |
| Config | Centralized settings from env vars | `backend/app/config.py` |
| Pipeline Engine | DAG execution with step isolation | `backend/app/pipeline/engine.py` |
| Loop Orchestrator | 5-step closed-loop (extract->graph->match->learn) | `backend/app/core/pipeline/loop_orchestrator.py` |
| SSE Broadcaster | Redis pub/sub to SSE event stream | `backend/app/core/dashboard/sse_broadcaster.py` |
| Celery Tasks | Async evolution analysis | `backend/app/tasks/celery_app.py` |

## Frontend Architecture

### Vue 3 + Pinia + Vue Router

**Page Layer** (`frontend/src/pages/`):
- 15 page components, each consuming Pinia stores and composables
- Key pages: `Home.vue` (graph), `ExtractJD.vue`, `MatchDiagnosis.vue`, `EvolutionDashboard.vue`, `LearningCenter.vue`, `PipelineMonitor.vue`, `Admin.vue`, `PipelineAnalysis.vue`, `LoopDemo.vue`

**Component Layer** (`frontend/src/components/`):
- 40+ shared components: `SkillRadar.vue`, `GapAnalysisReport.vue`, `LearningPathPlan.vue`, `LearningPathFlow.vue`, `Graph2D.vue`, `Graph3D.vue`, `PipelineDag.vue`, `PromptManager.vue`, `ResumeUpload.vue`, etc.

**Composable Layer** (`frontend/src/composables/`):
- 25+ composables extracting reusable logic from pages
- SSE: `useSSE.ts` (exponential backoff + polling fallback)
- Graph: `useG6.ts`, `useG6Graph.ts`, `useGraphNodeEditor.ts`, `useGraphNodeList.ts`, `useGraphNodeLabels.ts`
- Dashboard: `useDashboardCharts.ts`, `useDashboardKpiCards.ts`, `useDashboardRealtimeSync.ts`
- Domain-specific: `useEvolutionCharts.ts`, `useEvolutionActions.ts`, `useLearningActions.ts`, `useLearningFilters.ts`, `useLearningMetrics.ts`, `usePipelineMonitor.ts`, `useQualityDashboard.ts`

**Store Layer** (`frontend/src/stores/`):
- 18 Pinia stores, each wrapping axios calls to specific backend API prefixes
- All stores use `request.ts` (axios instance with auth token injection, loading bar, error toasts)

**API Client Layer** (`frontend/src/api/`):
- `request.ts`: axios instance with baseURL `/api/v1`, 30s timeout, auth interceptor, 401->login redirect
- `request.improved.ts`: alternative client (not primary)
- `client.ts`, `schema.ts`: supplementary

**Router** (`frontend/src/router/index.ts`):
- 15 routes with lazy-loaded page components
- Auth guard: `requiresAuth` meta, `requiresAdmin` meta, 401 event listener redirects to `/login`

## Data Flow Architecture

### Primary Request Path: JD Extraction to Learning Plan

1. User pastes JD text in `ExtractJD.vue` (`frontend/src/pages/ExtractJD.vue`)
2. `useJdStore.extractJd()` calls `POST /extract/jd` (`frontend/src/stores/jd.ts:98`)
3. Backend `extract_jd()` invokes `extract_from_jd()` LLM pipeline (`backend/app/api/v1/extract.py:122`)
4. `_write_extraction_to_graph()` persists skills to Neo4j (`backend/app/api/v1/extract.py:94`)
5. Returns `ExtractionResult` with `normalized_skills`, `required_skills`, `confidence`
6. Frontend displays extracted skills in tags and normalized table

### Match Diagnosis Flow

1. User uploads resume in `MatchDiagnosis.vue` step 0 (`frontend/src/pages/MatchDiagnosis.vue:58`)
2. `useResumeStore.parseResume()` calls `POST /resume/upload` (`frontend/src/stores/resume.ts:26`)
3. User selects target position in step 1, `useMatchStore.fetchPositionSkills()` calls `GET /graph/position/{id}/skills`
4. User triggers diagnosis in step 2, `useMatchStore.runMatch()` calls `POST /match/position` (`frontend/src/stores/match.ts:51`)
5. Backend `run_match()` computes match score, gap analysis, persists to PostgreSQL (`backend/app/services/match_service.py`)
6. Frontend displays radar chart, gap analysis, and learning path plan in steps 3-4

### Pipeline Data Flow

1. `PipelineMonitor.vue` fetches status via `GET /pipeline/status` (`frontend/src/stores/pipeline.ts:153`)
2. SSE stream at `GET /pipeline/events` pushes real-time stage updates (`backend/app/api/v1/pipeline/routes.py:322`)
3. Admin triggers pipeline via `POST /pipeline/trigger` (requires admin role)
4. Pipeline engine executes DAG: crawl -> dedup -> clean -> import -> graph_sync (`backend/app/pipeline/engine.py`)
5. Each stage updates `PipelineRun` in PostgreSQL and publishes SSE events via Redis

### Closed-Loop Flow (LoopDemo)

1. `LoopDemo.vue` triggers `POST /loop/run` with JD text + target position (`frontend/src/stores/loop.ts:146`)
2. Backend `LoopOrchestrator.run_loop()` executes 5 steps: JD input -> skill extraction -> graph update -> match diagnosis -> learning path (`backend/app/core/pipeline/loop_orchestrator.py`)
3. Each step degrades independently on failure (partial results returned)
4. Frontend displays step-by-step timeline with status indicators

## Cross-Cutting Concerns

### Authentication Flow

- **Backend**: JWT HMAC-SHA256 validation in `get_current_user()` (`backend/app/dependencies.py:91`)
  - Dev mode: accepts `dev-token` or returns default dev user
  - Production: requires valid JWT with `sub`, `role`, `username` claims
  - `require_admin()` checks `role == "admin"`
- **Frontend**: Token stored in `localStorage` as `starmap_token` or `token` (`frontend/src/api/request.ts:49`)
  - Axios interceptor attaches `Authorization: Bearer {token}` to every request
  - 401 response clears token and dispatches `auth:unauthorized` event -> router redirects to `/login`
  - `useUserStore` decodes JWT client-side for role checks (`frontend/src/stores/user.ts:19`)
- **Gap**: No dedicated login page -- `/login` route renders `Home.vue`. No registration or token refresh endpoints.

### Error Handling Strategy

- **Backend**: Global exception handler returns generic 500 without internals (`backend/app/main.py:149`)
  - Domain exceptions mapped to HTTP status in API layer (e.g., `AuditItemNotFound` -> 404)
  - LLM failures: `ValueError` -> 422, `ConnectionError` -> 502
  - Audit logging for auth failures, rate limits (`backend/app/utils/audit.py`)
- **Frontend**: Axios response interceptor maps HTTP status to Chinese error messages (`frontend/src/api/request.ts:88`)
  - 401 -> clear token + redirect, 403 -> permission error toast, others -> generic error toast
  - Stores catch errors and set `error` ref for component-level display

### Real-Time Updates (SSE)

- **Backend**: `SSEBroadcaster` publishes events to Redis pub/sub (`backend/app/core/dashboard/sse_broadcaster.py`)
  - Event types: `pipeline_update`, `quality_alert`, `data_milestone`, `extraction_complete`
  - Two SSE endpoints: `/dashboard/realtime` and `/pipeline/events`
  - Polling fallbacks: `/dashboard/realtime-poll` and `/pipeline/events-poll`
- **Frontend**: `useSSE` composable with exponential backoff and automatic polling fallback (`frontend/src/composables/useSSE.ts`)
  - Named event listeners for `pipeline_update`, `quality_alert`, `data_milestone`, `extraction_complete`
  - `storeHandlers` map dispatches events to appropriate Pinia store actions

## Feature Loop Completeness (功能闭环分析)

### 1. JD 抽取闭环 (JD Extraction Loop)

**Frontend**: `ExtractJD.vue` -> `useJdStore.extractJd()` -> `POST /extract/jd`
**Backend**: `extract.py:extract_jd()` -> `extract_from_jd()` -> `_write_extraction_to_graph()` -> Neo4j
**Result**: Frontend displays `position_name`, `required_skills`, `preferred_skills`, `normalized_skills`, `confidence`

**Gap Analysis:**
- **CLOSED**: Extraction -> graph write is implemented. `_write_extraction_to_graph()` persists to Neo4j (non-blocking).
- **GAP 1 -- No navigation from extraction result to next step**: After extraction completes, there is no "Go to Match Diagnosis" or "Go to Graph View" button. The user must manually navigate. The extracted position is not auto-linked to the match flow.
- **GAP 2 -- Resume extraction has no dedicated page**: `POST /extract/resume` and `POST /resume/upload` exist but the only entry point is inside `MatchDiagnosis.vue` step 0. There is no standalone resume extraction page.
- **GAP 3 -- Extraction history not surfaced**: Backend stores `JDExtractionRecord` in PostgreSQL but there is no frontend list/history view for past extractions.

### 2. 匹配诊断闭环 (Match Diagnosis Loop)

**Frontend**: `MatchDiagnosis.vue` (5-step wizard) -> `useMatchStore.runMatch()` -> `POST /match/position`
**Backend**: `match.py:match_position()` -> `run_match()` -> PostgreSQL + Neo4j
**Result**: `MatchResponse` with `match_score`, `matched_skills`, `gap_skills`, `skill_gap_detail`, `recommendations`

**Gap Analysis:**
- **CLOSED**: Resume upload -> skill extraction -> position selection -> match diagnosis -> gap analysis -> learning path plan. The 5-step wizard in `MatchDiagnosis.vue` covers the full flow.
- **GAP 1 -- Learning plan creation is not auto-triggered**: Step 4 shows `LearningPathPlan.vue` but does not call `useLearningStore.createPlan()`. The user must navigate to `/learning` and manually create a plan. The `skill_gap_detail` from match is not automatically passed to the learning store.
- **GAP 2 -- Match history is shallow**: `GET /match/history` returns basic info (match_id, position, score) but the frontend `MatchDiagnosis.vue` only fetches history in step 3 and does not display it prominently. No "re-view past diagnosis" flow.
- **GAP 3 -- Reverse match (`/match/recommend`) has no frontend consumer**: Backend implements `POST /match/recommend` (skills -> position recommendations) but no frontend page or store action calls it.
- **GAP 4 -- Competitiveness analysis partially connected**: `GET /match/competitiveness/{position}` is called by `useLearningStore.fetchCompetitiveness()` but the result is only used in the learning store, not in the match diagnosis page itself.

### 3. 演化追踪闭环 (Evolution Tracking Loop)

**Frontend**: `EvolutionDashboard.vue` -> `useEvolutionStore.fetchTrends()` -> `GET /evolution/trends`
**Backend**: `evolution.py:get_trends()` -> `load_skill_timeseries_data()` -> `EmergenceFinder.scan()`
**Result**: `EvolutionTrendsResponse` with trend items (skill_name, trend, confidence, CII points, related_positions)

**Gap Analysis:**
- **CLOSED**: Trends display, emerging skills, changelog, snapshots, CII history all have backend endpoints and frontend consumers.
- **GAP 1 -- Evolution analysis trigger is fire-and-forget**: `POST /evolution/analyze` queues a Celery task but the frontend has no UI to trigger it or check task status. The `EvolutionDashboard.vue` only reads data, never triggers analysis.
- **GAP 2 -- Review queue not connected to admin**: `GET /evolution/review-queue` returns low-trust changes but the admin panel (`Admin.vue`) uses a separate audit queue from `admin_audit_service`. The evolution review queue and admin audit queue are disconnected.
- **GAP 3 -- Skill portability has no frontend**: `GET /evolution/portability/{skill}` is marked "L2 -- Internal API, no frontend consumer" in the backend audit note.
- **GAP 4 -- Career path and industry report consumed only by learning store**: `GET /evolution/career-path/{position}` and `GET /evolution/industry-report` are called by `useLearningStore` but not by `EvolutionDashboard.vue`. The evolution page does not show career paths or industry reports.
- **GAP 5 -- Emerging alerts sub-router exists but frontend integration unclear**: `evolution_emerging_alerts.py` is included in the evolution router but the frontend `EvolutionDashboard.vue` does not have a dedicated alerts section.

### 4. 数据管线闭环 (Pipeline Loop)

**Frontend**: `PipelineMonitor.vue` -> `usePipelineStore.fetchStatus()` -> `GET /pipeline/status`
**Backend**: `pipeline/routes.py:get_pipeline_status()` -> orchestrator + status aggregator + quality monitor
**Result**: `PipelineStatusResponse` with run status, stage progress, quality alerts, data source count

**Gap Analysis:**
- **CLOSED**: Pipeline monitoring, triggering, stage status, data quality, schedules, config, SSE events, cancel, retry, resume all have both backend endpoints and frontend store actions.
- **GAP 1 -- Pipeline analysis (jobseeker) uses raw fetch, not axios**: `useJobseekerStore.analyzeResume()` uses `fetch('/api/v1/pipeline/analyze')` directly instead of the `request.ts` axios instance (`frontend/src/stores/jobseeker.ts:82`). This bypasses auth token injection and error handling.
- **GAP 2 -- Pipeline export endpoint has no frontend consumer**: `POST /pipeline/export` returns JSON analysis result but no frontend page or store calls it.
- **GAP 3 -- Cron scheduler runs but schedule management is admin-only**: Schedule CRUD requires `require_admin` dependency. Regular users can view schedules but cannot create/modify them. The frontend `PipelineMonitor.vue` exposes schedule management but the auth guard may block non-admin users.

### 5. 学习路径闭环 (Learning Path Loop)

**Frontend**: `LearningCenter.vue` -> `useLearningStore.createPlan()` -> `POST /learning/plan`
**Backend**: `learning.py:create_learning_plan()` -> `generate_learning_path()` -> `create_plan()` -> PostgreSQL
**Result**: `PlanResponse` with plan_id, phases, skills, progress, total hours/weeks

**Gap Analysis:**
- **CLOSED**: Plan creation, listing, detail, progress update, skill addition, recommendations all have backend endpoints and frontend store actions.
- **GAP 1 -- No auto-creation from match diagnosis**: The match diagnosis page (step 4) shows a learning path plan component but does not call `useLearningStore.createPlan()`. The user must manually navigate to `/learning` and create a plan. The `skill_gap_detail` from the match result is not automatically forwarded.
- **GAP 2 -- Progress update lacks validation**: `PUT /learning/plan/{plan_id}/progress` accepts any status/progress_pct combination. The frontend optimistically updates local state without re-fetching, which can drift from backend state.
- **GAP 3 -- Recommendations do not use match context**: `GET /learning/recommendations` accepts optional `plan_id` or `position` but the learning center page does not pass the match result context. Recommendations default to trending skills rather than gap-based suggestions.
- **GAP 4 -- No learning completion/graduation flow**: There is no endpoint or UI to mark a plan as "completed" or to trigger a re-match after learning progress. The loop from "learn" back to "re-diagnose" is not closed.

### 6. 管理后台闭环 (Admin Loop)

**Frontend**: `Admin.vue` -> `useAuditStore`, `useGraphNodeStore`, `useDataSourceStore`, `usePromptStore`
**Backend**: `admin.py` + sub-routers -> `admin_audit_service`, `admin_graph_service`, `admin_ab_service`
**Result**: Audit queue CRUD, graph node CRUD, prompt version management, A/B testing, data source config

**Gap Analysis:**
- **CLOSED**: Audit queue (fetch, approve, reject, batch, update), graph node CRUD (list, create, update, delete, approve, reject), prompt management (list, template, version, activate, A/B test, results), data source management (list, detail, update, stats, sync, health).
- **GAP 1 -- Admin stats not displayed**: `GET /admin/stats` returns `AdminStatsResponse` but `Admin.vue` does not have a stats dashboard section. The admin page focuses on audit queue, graph nodes, data sources, and prompts.
- **GAP 2 -- Pipeline management in admin is redundant**: `GET /admin/pipeline/status` and `POST /admin/pipeline/trigger-full` duplicate functionality from `/pipeline/status` and `/pipeline/trigger`. The admin page does not use these endpoints.
- **GAP 3 -- Judge evaluation has no admin UI**: `POST /judge/evaluate`, `POST /judge/pairwise`, `POST /judge/batch` are internal APIs with no frontend consumer. Quality evaluation must be triggered via API directly.
- **GAP 4 -- Comprehensive quality report not surfaced**: `GET /quality/comprehensive-report` aggregates JD + resume + graph quality but has no frontend page. The `QualityDashboard.vue` only calls `/quality/dashboard` instead.

### 7. 闭环演示闭环 (Loop Demo)

**Frontend**: `LoopDemo.vue` -> `useLoopStore.runLoop()` -> `POST /loop/run`
**Backend**: `loop.py:run_loop()` -> `LoopOrchestrator.run_loop()` -> 5-step pipeline
**Result**: `LoopRunResponse` with step-by-step results, extracted skills, graph update, match result, learning path

**Gap Analysis:**
- **CLOSED**: The loop demo page triggers the full 5-step pipeline and displays step-by-step results with timeline visualization.
- **GAP 1 -- Loop results not persisted to learning center**: The learning path generated in step 5 of the loop is displayed in the loop demo but not forwarded to `useLearningStore`. The user cannot continue the learning journey from the loop demo.
- **GAP 2 -- Loop history is minimal**: `GET /loop/history` returns basic info but the loop demo page does not prominently display past runs or allow re-viewing them.

### 8. 数据大屏闭环 (Data Dashboard Loop)

**Frontend**: `DataDashboard.vue` -> `useDashboardStore.fetchAll()` -> multiple GET endpoints
**Backend**: `dashboard.py` -> `dashboard_service.py` + `sse_broadcaster.py`
**Result**: Overview KPIs, trends, distributions, emerging skills, pipeline timeline, realtime events

**Gap Analysis:**
- **CLOSED**: All dashboard data endpoints have frontend consumers. SSE realtime events are consumed via `useSSE`.
- **GAP 1 -- Dashboard data is read-only**: No write operations from the dashboard. Users cannot trigger actions (e.g., start pipeline, approve audit items) directly from the dashboard view.

## Architectural Constraints

- **Threading**: Single-threaded async event loop (FastAPI + asyncio). Celery workers for long-running tasks (evolution analysis).
- **Global state**: `resources` singleton in `backend/app/services/resources.py:38` holds PostgreSQL/Neo4j/Redis connections. `_rate_buckets` dict in `main.py:107` for in-memory rate limiting. `_ab_results` defaultdict in `admin_prompts.py:35` for A/B test tracking (process-local, not shared across workers).
- **Circular imports**: Sub-routers imported at module bottom with `# noqa: E402` (e.g., `evolution.py:590-598`, `admin.py:228-231`). These are deferred imports to avoid circular dependency at module load time.
- **Dual data stores**: PostgreSQL for structured data (positions, skills, match results, pipeline runs, learning plans) and Neo4j for graph data (Position/Skill nodes, REQUIRES/EVOLVES_TO edges). Some data is duplicated (e.g., evolution paths exist in both PG `evolution_paths` table and Neo4j EVOLVES_TO relationships). Neo4j is primary for graph queries; PG is fallback.

## Anti-Patterns

### Store-Page Coupling Without Cross-Store Communication

**What happens**: `MatchDiagnosis.vue` produces match results in `useMatchStore` but `LearningCenter.vue` consumes `useLearningStore`. There is no programmatic bridge between the two stores. The user must manually navigate and re-enter data.
**Why it is wrong**: The core business flow (match -> learn) is broken at the store boundary. Users lose context when navigating between pages.
**Do this instead**: After match diagnosis completes, auto-populate `useLearningStore.createPlan()` with the match result's `skill_gap_detail`. Add a "Create Learning Plan" button in `MatchDiagnosis.vue` step 4 that calls `learningStore.createPlan()` with the match result.

### Raw Fetch Bypassing Axios Interceptors

**What happens**: `useJobseekerStore.analyzeResume()` uses `fetch('/api/v1/pipeline/analyze')` directly instead of the `request.ts` axios instance (`frontend/src/stores/jobseeker.ts:82`).
**Why it is wrong**: This bypasses auth token injection, loading bar, error toast, and 401 redirect handling. If the token expires, the request will fail silently with a 401 instead of redirecting to login.
**Do this instead**: Use the `request.ts` axios instance for all API calls. For SSE/streaming responses, use the axios instance with `responseType: 'stream'` or keep raw fetch but manually inject the auth header from localStorage.

### Backend-Only APIs Without Frontend Consumers

**What happens**: Several backend endpoints are marked "Internal API, no frontend consumer" in audit notes: `/evolution/portability/{skill}`, `/quality/evaluate/resume`, `/quality/comprehensive-report`, `/judge/*`, `/match/recommend`, `/pipeline/export`.
**Why it is wrong**: These represent implemented backend capabilities that users cannot access. They increase maintenance burden without delivering user value.
**Do this instead**: Either build frontend UI for these features or remove the endpoints if they are truly internal-only. At minimum, document them in an internal API reference separate from the user-facing API.

## Error Handling

**Strategy**: Layered error handling with domain-specific exceptions at the core, HTTP mapping at the API layer, and user-friendly messages at the frontend.

**Patterns:**
- Backend: Domain exceptions (e.g., `AuditItemNotFound`, `RunNotFoundError`) raised in services, caught and mapped to HTTP status in API handlers
- Backend: Global exception handler catches unhandled exceptions, logs with stack trace, returns generic 500
- Frontend: Axios interceptor maps HTTP status codes to Chinese error messages, shows ElMessage/ElNotification
- Frontend: Stores catch errors, set `error` ref, and re-throw for component-level handling
- Frontend: SSE composable handles connection errors with exponential backoff and polling fallback

## Cross-Cutting Concerns

**Logging**: Loguru with JSON-structured output in production, colored output in development (`backend/app/main.py:28-41`)
**Validation**: Pydantic models for all request/response schemas at the API layer. SQLAlchemy models for database constraints.
**Authentication**: JWT HMAC-SHA256 with role-based access control. All API routes require authentication by default. Admin routes require `role == "admin"`.

---

*Architecture analysis: 2026-07-12*
