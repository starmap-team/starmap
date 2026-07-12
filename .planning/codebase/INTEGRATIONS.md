# Integrations & API Alignment — StarMap

**Analysis Date:** 2026-07-12

## API Contract Layer

- **Location:** `starmap-contracts/openapi.yaml` (4506 lines, OpenAPI 3.0.3)
- **Generated client:** `frontend/src/api/client.ts` (typed convenience methods)
- **Generated schema types:** `frontend/src/api/schema.ts` (via `openapi-typescript`)
- **Raw HTTP client:** `frontend/src/api/request.ts` (axios instance with interceptors)

**Coverage assessment:** The OpenAPI contract defines **~70 endpoints** across 12 tag groups. The generated `api/client.ts` only exposes **9 convenience methods** (health, extractJd, extractResume, listPositions, getPositionDetail, runMatch, getEvolutionTrends, getEvolutionPaths, getQualityDashboard, getPipelineStatus, getGraphOverview). All other endpoints are called via raw `request.get/post/put/delete` in Pinia stores, bypassing the typed client. This means most API calls lack compile-time type safety.

## Frontend→Backend API Mapping

### Graph Module (`frontend/src/stores/graph.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/graph/overview')` | `GET /graph/overview` | **ALIGNED** |
| `request.get('/graph/ka/{kaId}/positions')` | `GET /graph/ka/{ka_id}/positions` | **ALIGNED** |
| `request.get('/evolution/paths/all')` | `GET /evolution/paths/all` | **ALIGNED** (cross-module call) |
| `request.get('/evolution/paths/{position}')` | `GET /evolution/paths/{position}` | **ALIGNED** (cross-module call) |

### Match Module (`frontend/src/stores/match.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.post('/match/position')` | `POST /match/position` | **ALIGNED** |
| `request.get('/match/result/{matchId}')` | `GET /match/result/{match_id}` | **ALIGNED** |
| `request.get('/graph/position/{id}/skills')` | `GET /graph/position/{position_id}/skills` | **ALIGNED** (cross-module) |
| `request.get('/match/history')` | `GET /match/history` | **ALIGNED** |

### Evolution Module (`frontend/src/stores/evolution.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/evolution/trends')` | `GET /evolution/trends` | **ALIGNED** |
| `request.get('/evolution/snapshots')` | `GET /evolution/snapshots` | **ALIGNED** |
| `request.get('/evolution/changelog/{skill}')` | `GET /evolution/changelog/{position}` | **MISMATCH** — Frontend passes skill name, but OpenAPI param is `position` (岗位名称). The backend route handler at `backend/app/api/v1/evolution.py:211` accepts a `position` path param. The store calls it with `skillName`. This works only if the backend treats the param generically, but the contract says "岗位名称". |

### Quality Module (`frontend/src/stores/quality.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/quality/dashboard')` | `GET /quality/dashboard` | **ALIGNED** |
| `request.get('/quality/report')` | `GET /quality/report` | **ALIGNED** (fallback) |
| `request.get('/quality/trends')` | `GET /quality/trends` | **ALIGNED** |
| `request.get('/quality/alerts')` | `GET /quality/alerts` | **ALIGNED** |

### Pipeline Module (`frontend/src/stores/pipeline.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/pipeline/status')` | `GET /pipeline/status` | **ALIGNED** |
| `request.get('/pipeline/runs')` | `GET /pipeline/runs` | **ALIGNED** |
| `request.get('/pipeline/runs/{id}')` | `GET /pipeline/runs/{run_id}` | **ALIGNED** |
| `request.post('/pipeline/trigger')` | `POST /pipeline/trigger` | **ALIGNED** |
| `request.post('/pipeline/runs/{id}/retry')` | `POST /pipeline/runs/{run_id}/retry` | **ALIGNED** |
| `request.post('/pipeline/runs/{id}/resume')` | `POST /pipeline/runs/{run_id}/resume` | **ALIGNED** |
| `request.post('/pipeline/runs/{id}/cancel')` | `POST /pipeline/runs/{run_id}/cancel` | **ALIGNED** |
| `request.get('/pipeline/stages')` | `GET /pipeline/stages` | **ALIGNED** |
| `request.get('/pipeline/data-quality')` | `GET /pipeline/data-quality` | **ALIGNED** |
| `request.get('/pipeline/datasources')` | `GET /pipeline/datasources` | **ALIGNED** |
| `request.get('/pipeline/schedules')` | `GET /pipeline/schedules` | **ALIGNED** |
| `request.post('/pipeline/schedules')` | `POST /pipeline/schedules` | **ALIGNED** |
| `request.put('/pipeline/schedules/{id}')` | `PUT /pipeline/schedules/{schedule_id}` | **ALIGNED** |
| `request.delete('/pipeline/schedules/{id}')` | `DELETE /pipeline/schedules/{schedule_id}` | **ALIGNED** |
| `request.post('/pipeline/schedules/{id}/trigger')` | `POST /pipeline/schedules/{schedule_id}/trigger` | **ALIGNED** |
| `request.get('/pipeline/config')` | `GET /pipeline/config` | **ALIGNED** |
| `request.put('/pipeline/config')` | `PUT /pipeline/config` | **ALIGNED** |

### JD Module (`frontend/src/stores/jd.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/positions')` | `GET /positions` | **ALIGNED** |
| `request.get('/graph/position/{name}/skills')` | `GET /graph/position/{position_id}/skills` | **ALIGNED** |
| `request.get('/positions/{name}')` | `GET /positions/{position_id}` | **ALIGNED** |
| `request.post('/extract/jd')` | `POST /extract/jd` | **ALIGNED** |

### Resume Module (`frontend/src/stores/resume.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.post('/resume/upload')` | `POST /resume/upload` | **ALIGNED** |

### Learning Module (`frontend/src/stores/learning.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.post('/learning/plan')` | `POST /learning/plan` | **ALIGNED** |
| `request.get('/learning/plan/{id}')` | `GET /learning/plan/{plan_id}` | **ALIGNED** |
| `request.put('/learning/plan/{id}/progress')` | `PUT /learning/plan/{plan_id}/progress` | **ALIGNED** |
| `request.get('/learning/recommendations')` | `GET /learning/recommendations` | **ALIGNED** |
| `request.get('/learning/plans')` | `GET /learning/plans` | **ALIGNED** |
| `request.post('/learning/plan/{id}/skills')` | `POST /learning/plan/{plan_id}/skills` | **ALIGNED** |
| `request.post('/match/batch')` | `POST /match/batch` | **ALIGNED** (cross-module) |
| `request.get('/match/competitiveness/{position}')` | `GET /match/competitiveness/{position}` | **ALIGNED** (cross-module) |
| `request.get('/evolution/career-path/{position}')` | `GET /evolution/career-path/{position}` | **ALIGNED** (cross-module) |
| `request.get('/evolution/industry-report')` | `GET /evolution/industry-report` | **ALIGNED** (cross-module) |

### Loop Module (`frontend/src/stores/loop.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.post('/loop/run')` | `POST /loop/run` | **ALIGNED** |
| `request.get('/loop/status/{id}')` | `GET /loop/status/{run_id}` | **ALIGNED** |
| `request.get('/loop/history')` | `GET /loop/history` | **ALIGNED** |

### Dashboard Module (`frontend/src/stores/dashboard.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/dashboard/overview')` | `GET /dashboard/overview` | **ALIGNED** |
| `request.get('/dashboard/trends')` | `GET /dashboard/trends` | **ALIGNED** |
| `request.get('/dashboard/distribution')` | `GET /dashboard/distribution` | **ALIGNED** |
| `request.get('/evolution/emerging-skills')` | `GET /evolution/emerging-skills` | **ALIGNED** (cross-module) |
| `request.get('/pipeline/stages')` | `GET /pipeline/stages` | **ALIGNED** (cross-module) |

### Datasource Module (`frontend/src/stores/datasource.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/datasources')` | `GET /datasources` | **ALIGNED** |
| `request.get('/datasources/{id}')` | `GET /datasources/{source_id}` | **ALIGNED** |
| `request.put('/datasources/{id}')` | `PUT /datasources/{source_id}` | **ALIGNED** |
| `request.get('/datasources/{id}/stats')` | `GET /datasources/{source_id}/stats` | **ALIGNED** |
| `request.post('/datasources/{id}/sync')` | `POST /datasources/{source_id}/sync` | **ALIGNED** |
| `request.get('/datasources/health')` | `GET /datasources/health` | **ALIGNED** (admin-only in backend) |

### Audit Module (`frontend/src/stores/audit.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/admin/review-queue')` | `GET /admin/review-queue` | **ALIGNED** |
| `request.post('/admin/audit/{id}/approve')` | `POST /admin/audit/{item_id}/approve` | **ALIGNED** |
| `request.post('/admin/audit/{id}/reject')` | `POST /admin/audit/{item_id}/reject` | **ALIGNED** |
| `request.put('/admin/review-queue/{id}')` | `PUT /admin/review-queue/{item_id}` | **ALIGNED** |
| `request.post('/admin/audit/batch')` | `POST /admin/audit/batch` | **ALIGNED** (not in OpenAPI contract) |

### GraphNode Module (`frontend/src/stores/graphNode.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/admin/graph/nodes')` | `GET /admin/graph/nodes` | **ALIGNED** |
| `request.post('/admin/graph/nodes')` | `POST /admin/graph/nodes` | **ALIGNED** |
| `request.put('/admin/graph/nodes/{id}')` | `PUT /admin/graph/nodes/{node_id}` | **ALIGNED** |
| `request.delete('/admin/graph/nodes/{id}')` | `DELETE /admin/graph/nodes/{node_id}` | **ALIGNED** |
| `request.post('/admin/graph/nodes/{id}/approve')` | `POST /admin/graph/nodes/{node_id}/approve` | **ALIGNED** |
| `request.post('/admin/graph/nodes/{id}/reject')` | `POST /admin/graph/nodes/{node_id}/reject` | **ALIGNED** |

### Prompt Module (`frontend/src/stores/prompt.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `request.get('/admin/prompts')` | `GET /admin/prompts` | **ALIGNED** |
| `request.get('/admin/prompts/{name}/template')` | `GET /admin/prompts/{name}/template` | **ALIGNED** |
| `request.put('/admin/prompts/{name}/active')` | `PUT /admin/prompts/{name}/active` | **ALIGNED** |
| `request.post('/admin/prompts/{name}/versions')` | `POST /admin/prompts/{name}/versions` | **ALIGNED** |
| `request.post('/admin/prompts/{name}/ab-test')` | `POST /admin/prompts/{name}/ab-test` | **ALIGNED** |
| `request.delete('/admin/prompts/{name}/ab-test')` | `DELETE /admin/prompts/{name}/ab-test` | **ALIGNED** |
| `request.get('/admin/prompts/{name}/ab-results')` | `GET /admin/prompts/{name}/ab-results` | **ALIGNED** |

### Jobseeker Module (`frontend/src/stores/jobseeker.ts`)

| Frontend Call | Backend Endpoint | Status |
|---|---|---|
| `fetch('/api/v1/pipeline/analyze')` | `POST /pipeline/analyze` | **ALIGNED** (uses native fetch, not axios) |

---

## Incomplete Feature Loops (关键发现)

### Frontend UI without Backend Completion

1. **Evolution changelog called with skill name instead of position name**
   - Frontend: `frontend/src/stores/evolution.ts:85` calls `request.get('/evolution/changelog/${encodeURIComponent(skillName)}')`
   - OpenAPI contract: `GET /evolution/changelog/{position}` — param described as "岗位名称"
   - Backend: `backend/app/api/v1/evolution.py:211` — handler expects `position` path param
   - **Impact:** The EvolutionDashboard page's changelog feature may return empty or incorrect results when a skill name is passed where a position name is expected. The semantic mismatch means the feature works only if the backend treats the param as a generic identifier.

2. **No login/auth endpoint in backend**
   - Frontend: `frontend/src/router/index.ts` has a `/login` route and `frontend/src/stores/user.ts` decodes JWT tokens client-side
   - Backend: No `/auth/login` or `/auth/token` endpoint exists in the OpenAPI contract or router
   - **Impact:** There is no way for users to obtain a JWT token through the frontend. The system relies on pre-existing tokens in localStorage or the dev-mode `dev-token`. The login page (`/login`) currently renders the Home component, not an actual login form. This is a critical gap for production use.

3. **Jobseeker store uses native `fetch` instead of axios**
   - Frontend: `frontend/src/stores/jobseeker.ts:82` uses `fetch('/api/v1/pipeline/analyze')` directly
   - All other stores use the axios `request` instance
   - **Impact:** The jobseeker SSE pipeline bypasses the auth token injection interceptor in `request.ts`. The `Authorization` header is not attached, so the request will fail in production (401). Additionally, the hardcoded `/api/v1` prefix ignores the `VITE_API_BASE_URL` env var.

4. **`/pipeline/export` endpoint not consumed by frontend**
   - Backend: `POST /pipeline/export` returns JSON analysis results (non-SSE alternative to `/pipeline/analyze`)
   - Frontend: No store or page calls this endpoint
   - **Impact:** The JSON export path is unused. If the SSE approach fails in certain browsers/networks, there is no fallback consumed by the UI.

5. **Evolution review queue not consumed by frontend**
   - Backend: `GET /evolution/review-queue` returns low-trust evolution changes needing review
   - Frontend: No store or page calls this endpoint
   - **Impact:** The evolution review workflow is incomplete — changes flagged for human review have no UI for reviewers to action them.

6. **Evolution snapshots page has no dedicated route**
   - Backend: `GET /evolution/snapshots` returns position skill snapshots
   - Frontend: `evolution.ts` store fetches snapshots, but there is no dedicated page/route for viewing them
   - **Impact:** Snapshot data is fetched but not surfaced in a standalone view.

7. **CII history endpoint not consumed by frontend**
   - Backend: `GET /evolution/cii-history/{position}` returns capability inflation index history
   - Frontend: No store or page calls this endpoint
   - **Impact:** CII (Capability Inflation Index) tracking is a key differentiator feature but has no UI.

8. **Skill portability endpoint not consumed by frontend**
   - Backend: `GET /evolution/portability/{skill}` returns cross-domain skill transferability analysis
   - Frontend: No store or page calls this endpoint
   - **Impact:** Skill portability analysis is defined in the contract but has no frontend integration.

9. **Emerging alerts endpoint not consumed by frontend**
   - Backend: `GET /evolution/emerging-alerts` returns Z-score based emerging/rising/declining skill alerts
   - Frontend: No store or page calls this endpoint (the dashboard store calls `/evolution/emerging-skills` instead, which is a different endpoint)
   - **Impact:** The richer alert system with domain filtering and Z-score thresholds is not used.

10. **Quality evaluate endpoint not triggered from UI**
    - Backend: `POST /quality/evaluate` triggers quality assessment pipeline
    - Backend: `POST /quality/evaluate/resume` triggers resume extraction evaluation
    - Frontend: No store or page calls these endpoints
    - **Impact:** Quality evaluation must be triggered manually via API; there is no "Run Evaluation" button in the Quality Dashboard.

11. **Quality comprehensive report not consumed**
    - Backend: `GET /quality/comprehensive-report` returns combined JD + resume + graph quality report
    - Frontend: No store or page calls this endpoint
    - **Impact:** The comprehensive report feature is backend-only.

12. **Position discover endpoint not triggered from UI**
    - Backend: `POST /positions/discover` triggers automated position discovery pipeline
    - Frontend: No store or page calls this endpoint
    - **Impact:** Position discovery must be triggered via API; no UI button exists.

13. **Dashboard SSE/realtime not fully wired**
    - Backend: `GET /dashboard/realtime` (SSE) and `GET /dashboard/realtime-poll` (fallback) exist
    - Frontend: `dashboard.ts` store has `addRealtimeEvent()` method and `sseConnected` ref, but no SSE connection setup code
    - **Impact:** The real-time dashboard updates are not functional. The SSE connection is never established from the frontend.

14. **Pipeline SSE events not consumed**
    - Backend: `GET /pipeline/events` (SSE) and `GET /pipeline/events-poll` (fallback) exist
    - Frontend: `pipeline.ts` store has `handlePipelineEvent()` and related handlers, but no SSE subscription code
    - **Impact:** Pipeline progress updates require manual page refresh; the live progress feature is incomplete.

### Backend Endpoints without Frontend Integration

1. **`GET /health`** — System health check. Only in `api/client.ts` convenience methods, not called by any page.
2. **`POST /extract/resume`** — Resume skill extraction (multipart). Frontend uses `/resume/upload` instead, which is a separate endpoint. The `/extract/resume` endpoint is never called.
3. **`GET /admin/stats`** — System statistics. Not consumed by any frontend store or page.
4. **`GET /admin/sources`** — Data source configuration list. Not consumed by any frontend store or page.
5. **`GET /admin/prompts/{name}`** — Prompt template metadata. The prompt store only calls `/admin/prompts/{name}/template`, not the metadata endpoint.
6. **`GET /admin/prompts/{name}/ab-test`** — Get A/B test config. The prompt store calls POST/DELETE for ab-test but never GET to read the config.
7. **`POST /admin/prompts/{name}/ab-results`** — Record A/B test result. This is a server-side recording endpoint, not expected to be called from frontend.
8. **`POST /match/diagnose`** — Alias for `/match/position`. Frontend always uses `/match/position` directly.
9. **`POST /match/recommend`** — Reverse match (given skills, recommend positions). Not consumed by any frontend store or page.
10. **`POST /evolution/analyze`** — Trigger evolution analysis pipeline. Not consumed by any frontend store or page.
11. **`POST /judge/evaluate`** — Single sample judge evaluation. Not consumed by any frontend store or page.
12. **`POST /judge/pairwise`** — Pairwise comparison. Not consumed by any frontend store or page.
13. **`POST /judge/batch`** — Batch judge evaluation. Not consumed by any frontend store or page.

### Data Flow Gaps (数据流断点)

1. **Match → Learning path creation is manual**
   - The match result includes `skill_gap_detail` with `learning_path` arrays per skill
   - The learning store's `createPlan()` accepts a `matchResult` object but the mapping is ad-hoc
   - There is no automatic "Create Learning Plan from Match Result" flow that properly maps `MatchResult.skill_gap_detail` → `CreatePlanRequest.skills`
   - **Files:** `frontend/src/stores/match.ts` (MatchResult type), `frontend/src/stores/learning.ts` (createPlan), `starmap-contracts/openapi.yaml` (CreatePlanRequest schema)

2. **Resume extraction → Match diagnosis is disconnected**
   - `frontend/src/stores/resume.ts` parses a resume and stores `ResumeParseResult`
   - `frontend/src/stores/match.ts` requires `person_skills: PersonSkill[]` for matching
   - The `user.ts` store has `parsedSkills` and `setResume()` but no code bridges resume parsing output to match input
   - The user must manually re-enter skills in the match form
   - **Files:** `frontend/src/stores/resume.ts`, `frontend/src/stores/match.ts`, `frontend/src/stores/user.ts`

3. **Loop demo → Learning plan creation is not wired**
   - The loop store's step 5 produces `learning_path` data
   - There is no button or flow to create a `LearningPlan` from the loop result
   - The loop demo is a standalone showcase, not integrated into the learning workflow
   - **Files:** `frontend/src/stores/loop.ts`, `frontend/src/stores/learning.ts`

4. **Jobseeker pipeline → No downstream consumption**
   - The jobseeker store's `PipelineResult` contains `top_matches`, `recommended_positions`, `skill_gaps`, `learning_path_summary`
   - None of these results feed into the match store, learning store, or evolution store
   - The analysis result is displayed once and lost
   - **Files:** `frontend/src/stores/jobseeker.ts`

5. **Evolution trends → Graph overlay is one-directional**
   - The graph store fetches evolution edges (`/evolution/paths/all`) and displays them on the 3D graph
   - But clicking an evolution edge does not navigate to the evolution dashboard or show trend details
   - The evolution store's trend data is not linked back to the graph view
   - **Files:** `frontend/src/stores/graph.ts`, `frontend/src/stores/evolution.ts`

6. **Quality alerts → No action workflow**
   - The quality store fetches alerts from `/quality/alerts`
   - Alerts are displayed but there is no "acknowledge", "resolve", or "investigate" action
   - The `QualityAlert` type has a `handled` boolean but no UI updates it
   - **Files:** `frontend/src/stores/quality.ts`, `frontend/src/types/quality.ts`

7. **Audit queue → Evolution review queue is separate**
   - The admin audit queue (`/admin/review-queue`) manages position/skill trust reviews
   - The evolution review queue (`/evolution/review-queue`) manages low-trust evolution changes
   - These are two separate queues with no cross-referencing or unified review UI
   - **Files:** `frontend/src/stores/audit.ts`, `backend/app/api/v1/evolution.py`

---

## External Service Integrations

### Neo4j (Graph Database)
- **Purpose:** Knowledge graph storage — Position, Skill, Tool, KnowledgeArea nodes and REQUIRES, EVOLVES_TO, BELONGS_TO edges
- **Connection:** `bolt://localhost:7687` (configurable via `NEO4J_URI`)
- **Auth:** `NEO4J_USER` / `NEO4J_PASSWORD` env vars
- **Client:** `neo4j` Python driver >=5.17
- **Dependency injection:** `backend/app/dependencies.py:get_neo4j_driver()` — retrieves driver from `app.state.resources`
- **Key consumers:** `graph.py`, `evolution.py`, `match.py`, `extract.py`, `loop.py`

### PostgreSQL (Relational Database)
- **Purpose:** Position records, pipeline runs, learning plans, audit items, data source configs, schedules
- **Connection:** `postgresql+asyncpg://user:pass@host:5432/starmap` (composed from env vars)
- **Auth:** `POSTGRES_USER` / `POSTGRES_PASSWORD` env vars
- **Client:** SQLAlchemy 2.0 async with asyncpg driver
- **Dependency injection:** `backend/app/dependencies.py:get_db_session()` — async session context
- **Migrations:** Alembic (`backend/alembic/`)

### Redis (Cache + Message Broker)
- **Purpose:** Celery broker, SSE event bus, pipeline stop flags, A/B test result storage, caching
- **Connection:** `redis://localhost:6379/0` (configurable via `REDIS_URI`)
- **Auth:** Password in URI (required in production)
- **Client:** `redis.asyncio` (async Redis client)
- **Dependency injection:** `backend/app/dependencies.py:get_redis_client()`

### ChromaDB (Vector Store)
- **Purpose:** Skill embedding similarity search for extraction dedup and normalization
- **Connection:** `localhost:8001` (configurable via `CHROMA_HOST`/`CHROMA_PORT`)
- **Client:** `chromadb` >=0.5

### LLM APIs
- **Xunfei Spark:** JD/resume skill extraction — `XUNFEI_API_KEY`, `XUNFEI_API_SECRET`, `XUNFEI_APP_ID`
- **DeepSeek:** Alternative LLM — `DEEPSEEK_API_KEY`, model `deepseek-chat`
- **Xiaomi MiMo:** Primary reasoning model — `MIMO_API_KEY`, `MIMO_API_BASE` (OpenAI-compatible)
- **Local Ollama:** Auto-fallback when no cloud keys configured
- **Client:** `httpx` (Xunfei), `openai` (DeepSeek/MiMo via OpenAI-compatible API)

### Celery (Task Queue)
- **Purpose:** Async pipeline execution (crawl, dedup, clean, import, graph_sync stages)
- **Broker:** Redis
- **Key tasks:** Pipeline DAG execution, source sync, evolution analysis

---

## Environment Configuration

**Required env vars (backend):**
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Graph database
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` — Relational database
- `REDIS_URI` — Cache/broker
- `SECRET_KEY` — JWT signing (must be >=32 chars in production)
- `MIMO_API_KEY` / `DEEPSEEK_API_KEY` / `XUNFEI_API_KEY` — At least one LLM provider (or use local Ollama)

**Required env vars (frontend):**
- `VITE_API_BASE_URL` — API base URL (defaults to `/api/v1`)

**Secrets location:** `.env` files at project root and `backend/` directory (gitignored)

---

## Webhooks & Callbacks

**Incoming:** None detected

**Outgoing:** None detected

---

## SSE (Server-Sent Events) Endpoints

| Endpoint | Purpose | Frontend Consumer | Status |
|---|---|---|---|
| `GET /dashboard/realtime` | Dashboard real-time events | None (not wired) | **GAP** |
| `GET /pipeline/events` | Pipeline progress events | None (not wired) | **GAP** |
| `POST /pipeline/analyze` | Jobseeker analysis SSE | `jobseeker.ts` (native fetch) | **PARTIAL** — works but bypasses auth |

---

*Integration audit: 2026-07-12*
