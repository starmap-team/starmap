# Codebase Structure — StarMap

**Analysis Date:** 2026-07-12

## Directory Layout

```
starmap/
├── backend/                    # FastAPI backend (Python)
│   ├── app/
│   │   ├── api/v1/             # API route handlers (14 modules)
│   │   │   ├── router.py       # Route aggregator
│   │   │   ├── extract.py      # JD/resume extraction
│   │   │   ├── match.py        # Match diagnosis
│   │   │   ├── evolution.py    # Evolution analysis (main + sub-routers)
│   │   │   ├── learning.py     # Learning center
│   │   │   ├── pipeline/       # Pipeline monitoring (routes/schemas/serializers)
│   │   │   ├── admin.py        # Admin (audit + sub-routers)
│   │   │   ├── graph.py        # Graph queries
│   │   │   ├── position.py     # Position CRUD
│   │   │   ├── resume.py       # Resume upload/parse
│   │   │   ├── quality.py      # Quality monitoring
│   │   │   ├── judge.py        # LLM-as-judge evaluation
│   │   │   ├── datasource.py   # Data source management
│   │   │   ├── dashboard.py    # Data dashboard (KPI/SSE)
│   │   │   └── loop.py         # Closed-loop demo
│   │   ├── core/               # Domain logic (8 modules)
│   │   │   ├── extraction/     # JD extract, LLM client, normalize, graph writer
│   │   │   ├── matching/       # Match scoring, path builder, cache
│   │   │   ├── learning/       # Path engine, progress tracker
│   │   │   ├── evolution/      # Emergence finder, diff engine, snapshots
│   │   │   ├── pipeline/       # Orchestrator, executor, quality monitor, cron
│   │   │   ├── dashboard/      # Dashboard service, SSE broadcaster
│   │   │   ├── hallucination/  # Hallucination detection
│   │   │   └── trust/          # Trust scoring
│   │   ├── services/           # Service layer (16 modules)
│   │   ├── models/             # SQLAlchemy ORM (4 modules)
│   │   ├── repositories/       # Repository pattern (position_repository)
│   │   ├── tasks/              # Celery async tasks
│   │   ├── pipeline/           # Pipeline engine (contracts, engine, steps)
│   │   ├── db/                 # Database session factory
│   │   ├── utils/              # Audit logging, async helpers
│   │   ├── dependencies.py     # Auth DI (JWT, require_admin)
│   │   ├── config.py           # Pydantic settings from env
│   │   └── main.py             # FastAPI app entry
│   ├── alembic/                # DB migrations
│   ├── tests/                  # Backend tests
│   └── pyproject.toml          # Poetry config
├── frontend/                   # Vue 3 frontend (TypeScript)
│   ├── src/
│   │   ├── pages/              # 15 page components
│   │   ├── components/         # 40+ shared components
│   │   ├── stores/             # 18 Pinia stores
│   │   ├── composables/        # 25+ composable hooks
│   │   ├── api/                # Axios client (request.ts)
│   │   ├── router/             # Vue Router (15 routes)
│   │   ├── types/              # TypeScript type definitions
│   │   ├── utils/              # Utility functions
│   │   ├── layouts/            # MainLayout
│   │   ├── styles/             # Global CSS
│   │   ├── App.vue             # Root component
│   │   └── main.ts             # App entry
│   └── e2e/                    # E2E tests
├── crawler/                    # Scrapy web crawlers
│   ├── spiders/                # Crawl spiders
│   ├── pipelines/              # Crawl pipelines
│   ├── persistence/            # Crawl data persistence
│   └── pipeline_bridge.py      # Bridge to backend pipeline
├── starmap-contracts/          # OpenAPI spec & contract validation
│   ├── openapi.yaml            # API contract
│   ├── models/                 # Contract models
│   └── validate.py             # Contract validator
├── tests/                      # Cross-stack E2E tests
│   └── e2e/
├── docs/                       # Documentation
├── scripts/                    # Utility scripts
├── audit/                      # Audit reports
└── evaluation/                 # Evaluation data
```

## Directory Purposes

**`backend/app/api/v1/`**:
- Purpose: HTTP route handlers (thin layer over services)
- Contains: FastAPI router definitions, Pydantic request/response schemas, dependency injection
- Key files: `router.py` (aggregator), `extract.py`, `match.py`, `evolution.py`, `learning.py`, `pipeline/routes.py`

**`backend/app/core/`**:
- Purpose: Domain business logic, independent of HTTP concerns
- Contains: Algorithm implementations, pipeline orchestration, LLM integration
- Key files: `extraction/jd_extract.py`, `matching/service.py`, `learning/path_engine.py`, `evolution/emergence_finder.py`, `pipeline/loop_orchestrator.py`

**`backend/app/services/`**:
- Purpose: Service layer orchestrating core logic with data access
- Contains: Business workflows, cross-domain coordination, Neo4j/PG queries
- Key files: `match_service.py`, `graph_service.py`, `learning_service.py`, `resources.py`

**`backend/app/models/`**:
- Purpose: SQLAlchemy ORM model definitions
- Contains: Table schemas, relationships, column types
- Key files: `extraction_models.py`, `evolution_models.py`, `learning_models.py`, `pipeline_models.py`

**`frontend/src/pages/`**:
- Purpose: Top-level page components (one per route)
- Contains: Vue SFCs with script setup, template, scoped styles
- Key files: `Home.vue`, `ExtractJD.vue`, `MatchDiagnosis.vue`, `EvolutionDashboard.vue`, `LearningCenter.vue`

**`frontend/src/stores/`**:
- Purpose: Pinia state management (one per API domain)
- Contains: State refs, async actions wrapping API calls, computed getters
- Key files: `graph.ts`, `jd.ts`, `match.ts`, `evolution.ts`, `learning.ts`, `pipeline.ts`

**`frontend/src/composables/`**:
- Purpose: Reusable composition functions extracted from pages
- Contains: Logic for charts, SSE, graph editing, domain-specific actions
- Key files: `useSSE.ts`, `useG6.ts`, `useEvolutionCharts.ts`, `useLearningActions.ts`

**`frontend/src/components/`**:
- Purpose: Shared UI components consumed by pages
- Contains: Visualization components, form components, display components
- Key files: `SkillRadar.vue`, `GapAnalysisReport.vue`, `LearningPathPlan.vue`, `Graph3D.vue`, `PipelineDag.vue`

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI application entry (lifespan, middleware, routes)
- `frontend/src/main.ts`: Vue 3 application entry (Pinia, Router, Element Plus)
- `frontend/src/App.vue`: Root Vue component

**Configuration:**
- `backend/app/config.py`: Pydantic settings (env vars, validation, defaults)
- `frontend/src/api/request.ts`: Axios instance (baseURL, interceptors, error handling)
- `frontend/src/router/index.ts`: Vue Router (15 routes, auth guards)

**Core Logic:**
- `backend/app/core/extraction/jd_extract.py`: JD extraction pipeline (LLM call + normalization)
- `backend/app/core/matching/service.py`: Match scoring algorithm
- `backend/app/core/learning/path_engine.py`: Learning path generation with prerequisite awareness
- `backend/app/core/evolution/emergence_finder.py`: Emerging/declining skill detection (z-score)
- `backend/app/core/pipeline/loop_orchestrator.py`: 5-step closed-loop pipeline
- `backend/app/core/dashboard/sse_broadcaster.py`: Redis pub/sub to SSE stream

**Authentication:**
- `backend/app/dependencies.py`: JWT validation, `get_current_user()`, `require_admin()`
- `frontend/src/stores/user.ts`: User state, JWT decode, role checks
- `frontend/src/api/request.ts`: Auth token injection, 401 handling

**Testing:**
- `backend/tests/`: Backend unit/integration tests
- `frontend/src/stores/__tests__/`: Store tests
- `frontend/src/components/__tests__/`: Component tests
- `tests/e2e/`: Cross-stack E2E tests

## Naming Conventions

**Files:**
- Backend API routes: `{domain}.py` (e.g., `extract.py`, `match.py`, `evolution.py`)
- Backend core modules: `{domain}/` directory with `__init__.py` (e.g., `extraction/`, `matching/`)
- Backend services: `{domain}_service.py` (e.g., `match_service.py`, `graph_service.py`)
- Backend models: `{domain}_models.py` (e.g., `extraction_models.py`, `evolution_models.py`)
- Frontend pages: `PascalCase.vue` (e.g., `MatchDiagnosis.vue`, `EvolutionDashboard.vue`)
- Frontend stores: `camelCase.ts` (e.g., `match.ts`, `learning.ts`, `pipeline.ts`)
- Frontend composables: `usePascalCase.ts` (e.g., `useSSE.ts`, `useEvolutionCharts.ts`)
- Frontend components: `PascalCase.vue` (e.g., `SkillRadar.vue`, `PipelineDag.vue`)

**Directories:**
- Backend sub-routers split from parent: `{parent}_{child}.py` (e.g., `evolution_career_path.py`, `admin_graph_nodes.py`)
- Frontend types: `{domain}.ts` in `types/` (e.g., `quality.ts`, `datasource.ts`, `evolution.ts`)

## Where to Add New Code

**New Feature (full-stack):**
- Backend API route: `backend/app/api/v1/{feature}.py` + register in `router.py`
- Backend service: `backend/app/services/{feature}_service.py`
- Backend core logic: `backend/app/core/{feature}/`
- Backend models: add to `backend/app/models/{domain}_models.py` + Alembic migration
- Frontend store: `frontend/src/stores/{feature}.ts`
- Frontend page: `frontend/src/pages/{FeatureName}.vue` + add route in `router/index.ts`
- Frontend components: `frontend/src/components/{ComponentName}.vue`
- Frontend composables: `frontend/src/composables/use{FeatureName}.ts`

**New API Endpoint (backend only):**
- Add route handler in `backend/app/api/v1/{domain}.py`
- If domain gets large, split to sub-router: `backend/app/api/v1/{domain}_{sub}.py`
- Register sub-router in parent: `router.include_router(sub_router, prefix="")`

**New Frontend Page:**
- Create `frontend/src/pages/{PageName}.vue`
- Add route in `frontend/src/router/index.ts` with `component: () => import('@/pages/{PageName}.vue')`
- Add `meta: { requiresAuth: true }` for authenticated pages
- Add `meta: { requiresAdmin: true }` for admin-only pages

**New Pinia Store:**
- Create `frontend/src/stores/{domain}.ts`
- Use `defineStore('{domain}', () => { ... })` with composition API style
- Import `request` from `@/api/request` for all API calls
- Follow pattern: `const loading = ref(false)`, `const error = ref<string | null>(null)`

**Utilities:**
- Backend shared helpers: `backend/app/utils/`
- Frontend shared helpers: `frontend/src/utils/`
- Frontend type definitions: `frontend/src/types/`

## Module Inventory

### Backend Modules

| Module | Files | Purpose | Frontend Consumer |
|--------|-------|---------|-------------------|
| extract | `api/v1/extract.py`, `core/extraction/` | JD/resume extraction, LLM, normalization | `useJdStore`, `useResumeStore` |
| match | `api/v1/match.py`, `core/matching/`, `services/match_service.py` | Match diagnosis, scoring, gap analysis | `useMatchStore`, `useLearningStore` |
| evolution | `api/v1/evolution*.py`, `core/evolution/` | Trends, emergence, changelog, career paths | `useEvolutionStore`, `useLearningStore`, `useGraphStore` |
| learning | `api/v1/learning.py`, `core/learning/`, `services/learning_service.py` | Learning plans, progress, recommendations | `useLearningStore` |
| pipeline | `api/v1/pipeline/`, `core/pipeline/`, `pipeline/` | DAG execution, monitoring, scheduling | `usePipelineStore`, `useJobseekerStore` |
| admin | `api/v1/admin*.py`, `services/admin_*_service.py` | Audit queue, graph CRUD, prompts, A/B | `useAuditStore`, `useGraphNodeStore`, `usePromptStore` |
| graph | `api/v1/graph.py`, `services/graph_service.py` | Graph queries, overview, KA positions | `useGraphStore`, `useMatchStore` |
| position | `api/v1/position.py` | Position CRUD | `useJdStore` |
| resume | `api/v1/resume.py`, `services/resume_service.py` | Resume upload and parsing | `useResumeStore` |
| quality | `api/v1/quality*.py` | Quality dashboard, evaluation, alerts | `useQualityStore` |
| judge | `api/v1/judge.py`, `services/judge_service.py` | LLM-as-judge evaluation | None (internal API) |
| datasource | `api/v1/datasource.py` | Data source CRUD, health, sync | `useDataSourceStore` |
| dashboard | `api/v1/dashboard.py`, `core/dashboard/` | KPI aggregation, SSE events | `useDashboardStore` |
| loop | `api/v1/loop.py`, `core/pipeline/loop_orchestrator.py` | Closed-loop 5-step demo | `useLoopStore` |

### Frontend Modules

| Module | Files | Purpose | Backend Dependency |
|--------|-------|---------|-------------------|
| graph | `stores/graph.ts`, `composables/useG6*.ts` | 3-layer graph navigation | `/graph/overview`, `/graph/ka/*/positions`, `/evolution/paths/*` |
| jd | `stores/jd.ts` | JD extraction + position list | `/extract/jd`, `/positions`, `/graph/position/*/skills` |
| match | `stores/match.ts` | Match diagnosis + history | `/match/position`, `/match/result/*`, `/match/history`, `/match/competitiveness/*` |
| evolution | `stores/evolution.ts` | Trends, snapshots, changelog | `/evolution/trends`, `/evolution/snapshots`, `/evolution/changelog/*` |
| learning | `stores/learning.ts` | Plans, progress, recommendations, batch match, career path | `/learning/*`, `/match/batch`, `/match/competitiveness/*`, `/evolution/career-path/*`, `/evolution/industry-report` |
| pipeline | `stores/pipeline.ts` | Pipeline monitoring, schedules, config | `/pipeline/*` |
| jobseeker | `stores/jobseeker.ts` | Jobseeker analysis (SSE) | `/pipeline/analyze` |
| loop | `stores/loop.ts` | Closed-loop demo | `/loop/run`, `/loop/status/*`, `/loop/history` |
| audit | `stores/audit.ts` | Admin audit queue | `/admin/review-queue`, `/admin/audit/*/approve|reject`, `/admin/audit/batch` |
| graphNode | `stores/graphNode.ts` | Admin graph node CRUD | `/admin/graph/nodes/*` |
| prompt | `stores/prompt.ts` | Prompt version management | `/admin/prompts/*` |
| datasource | `stores/datasource.ts` | Data source management | `/datasources/*` |
| quality | `stores/quality.ts` | Quality dashboard + trends | `/quality/dashboard`, `/quality/trends`, `/quality/alerts` |
| dashboard | `stores/dashboard.ts` | Data dashboard KPIs | `/dashboard/overview`, `/dashboard/trends`, `/dashboard/distribution`, `/evolution/emerging-skills`, `/pipeline/stages` |
| resume | `stores/resume.ts` | Resume parsing | `/resume/upload` |
| user | `stores/user.ts` | Auth state, JWT decode | None (client-side only) |

### Orphan Modules (no cross-referencing)

| Backend Endpoint | Status | Issue |
|------------------|--------|-------|
| `POST /match/recommend` | No frontend consumer | Reverse match (skills -> positions) implemented but unused |
| `POST /pipeline/export` | No frontend consumer | JSON export of pipeline analysis results |
| `GET /evolution/portability/{skill}` | No frontend consumer | Skill portability analysis (marked L2 internal) |
| `POST /quality/evaluate/resume` | No frontend consumer | Resume extraction F1 evaluation (marked L3 internal) |
| `GET /quality/comprehensive-report` | No frontend consumer | Comprehensive JD + resume + graph quality report (marked L4 internal) |
| `POST /judge/evaluate` | No frontend consumer | Single-sample LLM-as-judge evaluation |
| `POST /judge/pairwise` | No frontend consumer | Pairwise comparison evaluation |
| `POST /judge/batch` | No frontend consumer | Batch evaluation with quality gate |
| `GET /admin/stats` | No frontend consumer | Admin overview statistics |
| `GET /admin/pipeline/status` | Redundant | Duplicates `/pipeline/status` |
| `POST /admin/pipeline/trigger-full` | Redundant | Duplicates `/pipeline/trigger` |
| `GET /evolution/review-queue` | Disconnected | Separate from admin audit queue; no admin UI |

| Frontend Store/Composable | Status | Issue |
|---------------------------|--------|-------|
| `useJobseekerStore` raw fetch | Bypasses axios | Uses `fetch()` instead of `request.ts`, missing auth/error handling |
| `LearningPathPlan.vue` in MatchDiagnosis | No store bridge | Shows learning plan but does not call `useLearningStore.createPlan()` |

## Special Directories

**`backend/alembic/`**:
- Purpose: Database migration scripts
- Generated: Yes (by `alembic revision --autogenerate`)
- Committed: Yes

**`starmap-contracts/`**:
- Purpose: OpenAPI specification and contract validation
- Generated: Partially (openapi.yaml can be auto-generated from FastAPI)
- Committed: Yes

**`crawler/`**:
- Purpose: Scrapy web crawlers for job data collection
- Generated: No
- Committed: Yes

**`frontend/src/composables/home/`**:
- Purpose: Home page-specific composables (dashboard charts, KPI cards, realtime sync)
- Generated: No
- Committed: Yes

**`backend/app/core/graph_engine/`**:
- Purpose: Graph engine module (directory exists but appears empty)
- Generated: No
- Committed: Yes (empty)

**`backend/app/core/trust/`**:
- Purpose: Trust scoring module (directory exists but appears empty)
- Generated: No
- Committed: Yes (empty)

**`backend/app/core/hallucination/`**:
- Purpose: Hallucination detection module (directory exists but appears empty)
- Generated: No
- Committed: Yes (empty)

---

*Structure analysis: 2026-07-12*
