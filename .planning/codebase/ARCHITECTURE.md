# Architecture

**Analysis Date:** 2026-07-05

## System Overview

StarMap is a talent competency knowledge graph system with a multi-layer architecture:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend Layer                                 │
│  Vue 3 + Pinia + Element Plus + ECharts + G6 + 3D-Force-Graph          │
│  `frontend/src/`                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                           API Gateway Layer                              │
│  FastAPI + Pydantic + CORS + Dependency Injection                      │
│  `backend/app/main.py`, `backend/app/api/v1/`                          │
├─────────────────────────────────────────────────────────────────────────┤
│                           Service Layer                                  │
│  Graph Service | Match Service | Resume Service | Learning Service       │
│  `backend/app/services/`                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                           Core Engine Layer                              │
│  Extraction | Evolution | Pipeline | Graph Engine | Matching | Trust    │
│  `backend/app/core/`                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                           Data Access Layer                              │
│  Neo4j (Graph) | PostgreSQL (Relational) | Redis (Cache/Queue)          │
│  ChromaDB (Vector) | Celery (Task Queue)                                │
│  `backend/app/models/`, `backend/app/repositories/`                     │
├─────────────────────────────────────────────────────────────────────────┤
│                           External Services                              │
│  MiMo API | DeepSeek API | Xunfei Spark | Ollama (Local Qwen)           │
│  `backend/app/core/extraction/llm_client.py`                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI App | HTTP server, lifecycle management, CORS | `backend/app/main.py` |
| API Router v1 | Route aggregation for 14 business modules | `backend/app/api/v1/router.py` |
| Graph Service | Neo4j queries, node/edge serialization | `backend/app/services/graph_service.py` |
| Match Service | Person-position matching, skill gap analysis | `backend/app/services/match_service.py` |
| Resume Service | PDF/Word parsing, skill extraction | `backend/app/services/resume_service.py` |
| Extraction Core | JD skill extraction, LLM client, normalization | `backend/app/core/extraction/` |
| Evolution Core | Skill trend analysis, diff engine, emergence | `backend/app/core/evolution/` |
| Pipeline Core | DAG orchestration, stage execution, cron | `backend/app/core/pipeline/` |
| Graph Engine | Neo4j graph operations, Cypher queries | `backend/app/core/graph_engine/` |
| Trust Integration | Trust scoring, hallucination guard | `backend/app/core/trust/` |
| Celery Tasks | Background job dispatch, retry logic | `backend/app/tasks/celery_app.py` |
| Graph Store (Pinia) | Three-layer graph view state (domain/position/detail) | `frontend/src/stores/graph.ts` |
| Match Store (Pinia) | Match results, history, skill gaps | `frontend/src/stores/match.ts` |
| Graph3D Component | WebGL 3D force-directed graph | `frontend/src/components/Graph3D.vue` |
| Graph2D Component | G6 2D graph with layout switching | `frontend/src/components/Graph2D.vue` |

## Pattern Overview

**Overall:** Layered Architecture with Domain-Driven Design (DDD) boundaries

**Key Characteristics:**
- **Contract-First:** OpenAPI 3.0 spec in `starmap-contracts/openapi.yaml` serves as single source of truth
- **Async-First:** All I/O operations use async/await (asyncpg, neo4j async driver, httpx)
- **Dependency Injection:** FastAPI `Depends()` for DB sessions, Neo4j drivers, Redis clients
- **Repository Pattern:** Data access abstracted behind repository interfaces
- **CQRS-Lite:** Separate read/write models for graph queries vs. pipeline state

## Layers

**Frontend Layer:**
- Purpose: SPA with 3D/2D graph visualization, admin dashboards, matching UI
- Location: `frontend/src/`
- Contains: Vue components, Pinia stores, composables, API client, mock handlers
- Depends on: Backend REST API (`/api/v1`), MSW (dev mode)
- Used by: End users via browser

**API Gateway Layer:**
- Purpose: HTTP request handling, validation, routing, CORS
- Location: `backend/app/api/v1/`
- Contains: FastAPI routers, Pydantic schemas, dependency injection
- Depends on: Service layer, Core engines
- Used by: Frontend, external integrations

**Service Layer:**
- Purpose: Business logic orchestration, cross-cutting concerns
- Location: `backend/app/services/`
- Contains: Graph service, match service, resume service, learning service, Neo4j service
- Depends on: Core engines, repositories, external APIs
- Used by: API layer

**Core Engine Layer:**
- Purpose: Domain-specific algorithms (NLP, graph analysis, evolution detection)
- Location: `backend/app/core/`
- Contains: Extraction, evolution, pipeline, graph engine, matching, trust, hallucination guard
- Depends on: Data access layer, LLM APIs
- Used by: Service layer

**Data Access Layer:**
- Purpose: Persistence and caching abstraction
- Location: `backend/app/models/`, `backend/app/repositories/`
- Contains: SQLAlchemy models, repository classes, connection management
- Depends on: PostgreSQL, Neo4j, Redis, ChromaDB
- Used by: Service layer, Core engines

## Data Flow

### Primary Request Path (Graph Query)

1. **Browser** sends GET `/api/v1/graph/position/{id}/skills`
2. **FastAPI Router** (`backend/app/api/v1/graph.py:73`) validates params, injects Neo4j driver
3. **Graph Service** (`backend/app/services/graph_service.py:fetch_position_graph`) builds Cypher query
4. **Neo4j Driver** executes query, returns nodes and relationships
5. **Graph Service** serializes to `PositionSkillDetailResponse` schema
6. **FastAPI** returns JSON to frontend
7. **Pinia Store** (`frontend/src/stores/graph.ts`) updates reactive state
8. **Vue Component** (`frontend/src/components/Graph3D.vue` or `Graph2D.vue`) renders graph

### Pipeline Execution Flow

1. **Trigger** — API POST `/api/v1/pipeline/trigger` creates `PipelineRun` record
2. **Orchestrator** (`backend/app/core/pipeline/orchestrator.py`) builds DAG stages
3. **Celery Task** (`backend/app/tasks/celery_app.py:execute_pipeline_stage`) dispatches ready stages
4. **Executor** (`backend/app/core/pipeline/executor.py`) runs stage logic (crawl → dedup → clean → import → graph_sync)
5. **Progress** — SSE events broadcast via Redis pub/sub (`backend/app/core/dashboard/sse_broadcaster.py`)
6. **Completion** — Stage status updated, next stages dispatched, run marked complete/failed

### Skill Extraction Flow

1. **Upload** — Resume/JD uploaded via `/api/v1/extract/resume` or `/api/v1/extract/jd`
2. **Parse** — `pdfplumber`/`python-docx` extracts raw text
3. **LLM Call** — `backend/app/core/extraction/llm_client.py` calls MiMo → DeepSeek → Xunfei → Ollama (fallback chain)
4. **Normalize** — `backend/app/core/extraction/normalize.py` canonicalizes skill names
5. **Hallucination Guard** — `backend/app/core/evolution/hallucination_guard.py` validates against ontology
6. **Persist** — Results stored in PostgreSQL (`JDExtractionRecord`, `SkillRecord`)
7. **Graph Sync** — MERGE operations write to Neo4j

## Key Abstractions

**GraphNode / GraphEdge:**
- Purpose: Unified data structure for frontend graph visualization
- Location: `frontend/src/stores/graph.ts`, `backend/app/api/v1/graph.py`
- Pattern: Shared contract between backend API and frontend stores

**PipelineRun / Stage:**
- Purpose: Track ETL pipeline execution state
- Location: `backend/app/models/pipeline_models.py`
- Pattern: State machine with DAG dependency resolution

**EvolutionResult:**
- Purpose: Container for 8-step evolution analysis output
- Location: `backend/app/core/evolution/orchestrator.py`
- Pattern: Dataclass aggregator for multi-step pipeline results

**AppResources:**
- Purpose: Singleton holding database connections (PostgreSQL, Neo4j, Redis)
- Location: `backend/app/services/resources.py`
- Pattern: Application-level resource lifecycle management

## Entry Points

**Backend API:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Responsibilities: Initialize AppResources, mount API routers, health checks

**Celery Worker:**
- Location: `backend/app/tasks/celery_app.py`
- Triggers: `celery -A app.tasks.celery_app.celery_app worker --loglevel=info`
- Responsibilities: Execute background tasks (extraction, graph build, evolution analysis)

**Frontend Dev:**
- Location: `frontend/src/main.ts`
- Triggers: `npm run dev` (Vite dev server)
- Responsibilities: Bootstrap Vue app, register Pinia, Element Plus, ECharts, router

**Crawler CLI:**
- Location: `crawler/run.py`
- Triggers: `python run.py <command>`
- Responsibilities: Spider execution, data ingestion, stats

## Architectural Constraints

**Threading:**
- Single-threaded async event loop (FastAPI + Uvicorn)
- Celery workers run in separate processes (multi-processing for CPU-bound tasks)
- ThreadPoolExecutor used sparingly for sync-to-async bridges in Celery tasks

**Global State:**
- `AppResources` singleton (`backend/app/services/resources.py`) holds database connections
- `PREREQUISITE_MAP` module-level cache in `match_service.py` (5-minute TTL)
- `_PROFILE_CACHE` module-level cache in `match_service.py` (5-minute TTL)

**Circular Imports:**
- Mitigated by lazy imports within functions in pipeline executor and Celery tasks
- `__init__.py` model imports use noqa comments to manage dependency order

## Anti-Patterns

### Module-Level Mutable Caches

**What happens:** Global dictionaries (`PREREQUISITE_MAP`, `_PROFILE_CACHE`) in `match_service.py` store cached data without proper invalidation mechanisms.
**Why it's wrong:** Cache invalidation is ad-hoc (5-minute TTL based on monotonic time), leading to stale data under concurrent access.
**Do this instead:** Use Redis for distributed caching with explicit TTLs, or implement a proper cache abstraction layer.

### Sync-to-Async Bridge in Celery

**What happens:** Celery tasks use `_run_async()` helper with `ThreadPoolExecutor` to run async coroutines.
**Why it's wrong:** Creates unnecessary thread overhead and potential event loop conflicts.
**Do this instead:** Use `asyncio.run()` directly in Celery task bodies where no running loop exists; consider `celery[async]` or `asgiref` for cleaner integration.

## Error Handling

**Strategy:** Structured exception hierarchy with FastAPI HTTPException mapping

**Patterns:**
- Custom exceptions: `LLMConnectionError`, `LLMResponseError`, `LLMTimeoutError` in `llm_client.py`
- Retry logic: `tenacity.retry` with exponential backoff on LLM calls
- Graceful degradation: Return 0/fallback when Neo4j queries fail
- HTTP status mapping: 400 validation, 404 not found, 502 LLM unavailable, 500 internal

## Cross-Cutting Concerns

**Logging:**
- `loguru` for structured logging across all backend modules
- Log level controlled via `app_log_level` setting
- Celery tasks include run_id and stage_name in log context

**Validation:**
- Pydantic v2 models for request/response validation
- Environment variable validation via `pydantic-settings` (`backend/app/config.py`)
- Hallucination guard validates extracted skills against ontology

**Authentication:**
- Not fully implemented (placeholder in config)
- CORS configured for localhost development

**Real-time Updates:**
- Redis pub/sub for SSE event broadcasting
- `dashboard:events` channel for pipeline progress, quality alerts
- Frontend consumes via `EventSource` API

---

*Architecture analysis: 2026-07-05*
