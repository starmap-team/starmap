# Conventions — StarMap

**Analysis Date:** 2026-07-12

## Backend Conventions

### Python Style
- **Naming:** snake_case for files, variables, and functions; PascalCase for classes
- **Line width:** 120 characters (Ruff config `line-length = 120`)
- **Formatter/Linter:** Ruff (`ruff check .` + `ruff format .`)
- **Target version:** Python 3.11 (`target-version = "py311"`)
- **Ruff rule set:** E, F, W, I, N, UP, B, C4; E501 and B008 ignored
- **Type hints:** `from __future__ import annotations` at top of every module; mypy for type checking
- **mypy strictness:** `strict = false`, `ignore_missing_imports = true`, `disallow_incomplete_defs = true`
- **Docstrings:** Chinese business description comments (`业务说明：`) and technical comments (`技术说明：`) on model fields and test classes; module-level docstrings in Chinese

### API Patterns
- **Framework:** FastAPI with APIRouter per domain module
- **Router registration:** Each module exports `router = APIRouter(...)` with prefix and tags; all routers aggregated in `backend/app/api/v1/router.py`
- **Pydantic models:** Request/response schemas defined inline in route files using `BaseModel` + `Field(..., description=...)`; no separate schemas directory for most modules (exception: `backend/app/api/v1/pipeline/schemas.py`)
- **Dependency injection:** FastAPI `Depends()` for DB sessions, Neo4j driver, Redis client, and auth (`backend/app/dependencies.py`)
- **Auth:** `get_current_user` dependency on all v1 routes; `require_admin` for admin-only endpoints
- **API field naming:** snake_case throughout (e.g., `match_score`, `skill_name`, `source_count`); no camelCase conversion

### Error Handling
- **API layer:** `HTTPException` with status code and `detail` string
- **Service layer:** Domain-specific exceptions; let them propagate to API layer
- **Global handler:** `@app.exception_handler(Exception)` in `backend/app/main.py` catches unhandled exceptions, logs them, returns generic 500
- **LLM failures:** Return 502 with `"LLM service unavailable"` detail
- **Validation errors:** FastAPI auto-returns 422 for Pydantic validation failures

### Logging
- **Framework:** loguru (`from loguru import logger`)
- **Production:** JSON-structured output (`serialize=True`) for ELK/Loki ingestion
- **Development:** Colored human-readable format
- **Audit logging:** Structured `AuditEntry` dataclass via `backend/app/utils/audit.py` with event types from `AuditEvent` StrEnum
- **Pattern:** `logger.info("StarMap 启动中... env={}", settings.app_env)` — brace-style formatting, not f-strings

### Configuration
- **Settings class:** `pydantic-settings` `BaseSettings` in `backend/app/config.py`; reads from `.env`
- **Singleton:** `@lru_cache` on `get_settings()`; module-level `settings = get_settings()`
- **Validation:** `@model_validator(mode="after")` checks for unconfigured passwords, production constraints

### Module Organization
- **API routes:** `backend/app/api/v1/` — one file per domain (e.g., `graph.py`, `match.py`, `evolution.py`)
- **Core business logic:** `backend/app/core/` — subpackages by domain (`extraction/`, `evolution/`, `matching/`, `learning/`, `dashboard/`, `pipeline/`)
- **Services:** `backend/app/services/` — data access and external integration (Neo4j, graph queries, matching)
- **Models:** `backend/app/models/` — SQLAlchemy ORM models, one file per domain
- **Repositories:** `backend/app/repositories/` — data access layer (currently only `position_repository.py`)
- **Tasks:** `backend/app/tasks/` — Celery async tasks
- **Utilities:** `backend/app/utils/` — shared helpers (`audit.py`, `async_helpers.py`)

### Import Conventions
- `from __future__ import annotations` always first
- stdlib imports
- third-party imports (fastapi, sqlalchemy, pydantic, loguru)
- local app imports
- Re-exports use `# noqa: F401` comments for backward compatibility (see `backend/app/services/graph_service.py`)

---

## Frontend Conventions

### Vue Component Style
- **Framework:** Vue 3 Composition API with `<script setup lang="ts">`
- **Component naming:** PascalCase files and components (e.g., `SkillRadar.vue`, `DataSourceCard.vue`)
- **Variable naming:** camelCase for variables and functions (e.g., `radarOption`, `fetchOverview`)
- **Props:** Typed with `defineProps<{ ... }>()` using TypeScript interface
- **Emits:** Typed with `defineEmits<{ ... }>()`
- **Exports:** `export interface` for prop types co-located in the same `<script setup>` block

### Pinia Stores
- **Pattern:** `defineStore('name', () => { ... })` — setup function syntax, not options API
- **File naming:** One store per file in `frontend/src/stores/`, named by domain (e.g., `graph.ts`, `match.ts`, `evolution.ts`)
- **State:** `ref<T>()` for reactive state; `computed()` for derived state
- **Actions:** Regular async functions within the setup function
- **Return:** Explicit return object listing all exposed state, computed, and actions
- **API calls:** Use `request.get/post/put/delete` from `frontend/src/api/request.ts`

### API Client
- **Base client:** Axios instance in `frontend/src/api/request.ts` with interceptors for auth token, loading bar, error messages
- **Typed client:** `frontend/src/api/client.ts` wraps `request` with OpenAPI-generated types from `frontend/src/api/schema.ts`
- **Schema generation:** `npm run gen:api` runs `openapi-typescript ../starmap-contracts/openapi.yaml -o src/api/schema.ts`
- **Migration path:** New code should use `api.*` from `client.ts`; existing `request.get/post` + `as any` casts can be migrated incrementally

### Styling
- **UI library:** Element Plus with Chinese locale (`zhCn`)
- **Charts:** ECharts via `vue-echarts` (registered globally as `<VChart>`)
- **Graph visualization:** @antv/G6 for 2D, 3d-force-graph + Three.js for 3D
- **CSS:** Scoped styles with CSS custom properties (e.g., `var(--font-size-lg)`, `var(--foreground)`, `var(--space-3)`)
- **Theme:** Chart theme utilities in `frontend/src/utils/chartTheme.ts`

### TypeScript
- **Strict mode:** `strict: true` in `tsconfig.json`
- **Known debt:** `@typescript-eslint/no-explicit-any` is `off` in ESLint; some stores use `as any` casts
- **Path alias:** `@/` maps to `src/`
- **Type check:** `vue-tsc --noEmit` via `npm run typecheck`
- **Build gate:** `npm run build` runs `vue-tsc --noEmit && vite build`

### Routing
- **Router:** Vue Router 4 with `createWebHistory`
- **Route meta:** `{ title, icon, breadcrumb, transition, requiresAuth, requiresAdmin }`
- **Lazy loading:** All page components use `() => import('@/pages/...')`
- **Auth guard:** `router.beforeEach` checks `requiresAuth` and `requiresAdmin` meta fields
- **401 handling:** `window` custom event `auth:unauthorized` dispatched by axios interceptor, caught by router

### Composables
- **Location:** `frontend/src/composables/` — domain-grouped in `home/` subdirectory for home-page composables
- **Naming:** `use` prefix (e.g., `useSSE`, `useG6`, `useDashboardCharts`)
- **Pattern:** Standard Vue composable pattern with `ref`, `computed`, `onUnmounted` lifecycle

---

## API Contract Conventions

- **Spec:** OpenAPI 3.0.3 in `starmap-contracts/openapi.yaml`
- **Truth source:** `starmap-contracts/` is the cross-team source of truth
- **Field naming:** snake_case throughout (e.g., `match_score`, `skill_name`, `source_count`)
- **Frontend sync:** `cd frontend && npm run gen:api` generates `src/api/schema.ts`
- **Contract-first development:** API changes must update `openapi.yaml` before implementation
- **Backward compatibility:** `tests/contract/diff_openapi.py` checks for breaking changes against baseline

---

## Git Conventions

- **Branches:** `fix/*`, `feat/*`, `chore/*`, `docs/*`
- **Commit format:** `type(scope): description (#PR)`
- **PR merge:** Squash merge
- **Linting gate:** Backend: `ruff check . && mypy app`; Frontend: `npm run lint && npm run typecheck`

---

## Known Deviations

### Backend
1. **mypy per-module overrides:** 12+ modules have `ignore_errors = true` in `pyproject.toml` `[tool.mypy.overrides]`, including `app.core.dashboard.*`, `app.core.pipeline.*`, `app.api.v1.dashboard`, `app.api.v1.learning`, `app.api.v1.loop`, `app.api.v1.pipeline`, `app.api.v1.evolution`, `app.tasks.celery_app`, `app.services.graph_service`, `app.services.match_service`. These modules bypass type checking entirely.
2. **mypy.ini disable_error_code:** 14+ specific modules have individual error codes disabled (e.g., `app.api.v1.graph` disables `arg-type`, `app.services.graph_overview` disables `index`). This indicates accumulated type-safety debt.
3. **Re-exports with noqa:** `backend/app/services/graph_service.py` re-exports symbols from `graph_serializers.py` and `graph_overview.py` with `# noqa: F401` for backward compatibility rather than updating import sites.
4. **Inline Cypher in route handlers:** `backend/app/api/v1/graph.py` contains raw Cypher queries directly in route handler functions (lines 139-209) instead of delegating to the service layer.
5. **Global mutable state:** `_rate_buckets` dict in `backend/app/main.py` is module-level mutable state for rate limiting; `_rate_buckets.clear()` in conftest.py is required to prevent test pollution.
6. **ESLint `no-explicit-any: off`:** Frontend ESLint disables `@typescript-eslint/no-explicit-any`, allowing untyped code. The typed API client in `client.ts` still uses `any` for `runMatch` body.
7. **Test files outside pytest scope:** `tests/unit/` at repo root contains Playwright-based UI tests (e.g., `test_config_management.py`) that are not discovered by `pytest` (which uses `backend/tests/`).
8. **Dual E2E frameworks:** Both Playwright (`frontend/e2e/*.spec.ts`) and Cypress (`frontend/e2e/*.cy.ts`) exist; Cypress tests appear to be legacy and may not be actively maintained.
9. **Missing store tests:** 9 of 16 Pinia stores lack test files: `dashboard`, `datasource`, `evolution`, `jd`, `jobseeker`, `learning`, `loop`, `pipeline`, `user`.
10. **Missing composable tests:** None of the 31 composables have dedicated test files.
11. **Missing component tests:** 33 of 39 Vue components lack test files; only 6 have specs.
12. **`as unknown as` type casts:** Stores like `match.ts` use `data as unknown as MatchResult` instead of proper type narrowing through the typed API client.

---

*Convention analysis: 2026-07-12*
