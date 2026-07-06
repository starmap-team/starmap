# Technology Stack

**Analysis Date:** 2026-07-05

## Languages

**Primary:**
- **Python 3.11** — Backend API, data pipelines, graph algorithms, ML/NLP processing
- **TypeScript** — Frontend application (Vue 3 + Vite)
- **Cypher** — Neo4j graph database queries

**Secondary:**
- **SQL** — PostgreSQL schema definitions, Alembic migrations
- **SCSS/CSS** — Frontend styling with CSS custom properties
- **YAML** — Docker Compose, OpenAPI contracts, configuration
- **Shell** — Deployment scripts (`scripts/`, `crawler/`)

## Runtime

**Environment:**
- Python 3.11 (slim Docker base image)
- Node.js 20 (Alpine base image for frontend build)

**Package Manager:**
- **Poetry 2.4.1** — Python dependency management with lockfile (`backend/poetry.lock`)
- **npm** — Node.js package management with lockfile (`frontend/package-lock.json`)
- Lockfiles committed to version control (enforced by project discipline)

## Frameworks

**Backend Core:**
- **FastAPI 0.110+** — Async web framework, OpenAPI auto-generation, dependency injection
- **Pydantic v2** — Data validation, settings management, request/response schemas
- **Uvicorn** — ASGI server with standard extras (websockets, httptools)

**Database & Storage:**
- **SQLAlchemy 2.0+** — Async ORM with PostgreSQL dialect
- **asyncpg 0.29+** — Native async PostgreSQL driver
- **Neo4j Python Driver 5.17+** — Graph database client (Bolt protocol)
- **Redis 5.0+** — Cache, message broker, pub/sub for SSE
- **ChromaDB 0.5+** — Vector database for semantic skill matching
- **Alembic 1.13+** — Database migration tool

**Task Queue:**
- **Celery 5.3+** — Distributed task queue with Redis broker/backend

**Frontend:**
- **Vue 3.4+** — Progressive JavaScript framework (Composition API)
- **Vue Router 4.3+** — SPA routing with history mode
- **Pinia 2.1+** — State management (composable API pattern)
- **Vite 5.2+** — Build tool and dev server with HMR
- **Element Plus 2.6+** — UI component library (Chinese locale)
- **ECharts 5.5+** — Data visualization (charts, radar, bar, pie)
- **vue-echarts 6.6+** — Vue wrapper for ECharts
- **@antv/g6 5.0+** — Graph visualization engine (2D force-directed layouts)
- **3d-force-graph 1.80+** — 3D force-directed graph visualization (WebGL/Three.js)
- **Three.js 0.185+** — 3D graphics library
- **Axios 1.6+** — HTTP client for API requests

**Testing:**
- **pytest 8.0+** — Python test framework with async support
- **pytest-cov** — Coverage reporting (60% threshold enforced)
- **pytest-asyncio** — Async test support
- **Vitest 1.4+** — Frontend unit testing
- **Playwright 1.61+** — E2E testing (browser automation)
- **MSW 2.2+** — Mock Service Worker for frontend development

**Dev Tools:**
- **Ruff 0.3+** — Python linting and formatting (line-length 120)
- **mypy 1.9+** — Static type checking (Python 3.11 target)
- **ESLint 8.57+** — TypeScript/Vue linting
- **vue-tsc 2.0+** — Vue SFC type checking
- **Sass 1.72+** — CSS preprocessor

## Key Dependencies

**Critical Backend:**
- `fastapi` (0.110-0.120) — Web framework
- `sqlalchemy[asyncio]` (2.0-2.1) — Async ORM
- `asyncpg` (0.29-0.30) — PostgreSQL async driver
- `neo4j` (5.17-6.0) — Graph database driver
- `redis` (5.0-6.0) — Cache and message broker
- `celery[redis]` (5.3-5.4) — Task queue
- `chromadb` (0.5-0.6) — Vector database
- `pydantic` (2.6-3.0) — Data validation
- `pydantic-settings` (2.2-3.0) — Environment configuration
- `loguru` (0.7+) — Structured logging
- `tenacity` (8.2-9.0) — Retry logic with exponential backoff

**LLM/NLP:**
- `httpx` (0.27-0.28) — Async HTTP client for LLM APIs
- `openai` (1.30-2.0) — OpenAI-compatible API client (for local Qwen/Ollama)
- `spacy` (3.7-3.8) — NLP processing
- `jieba` (0.42+) — Chinese text segmentation

**Document Parsing:**
- `pdfplumber` (0.10+) — PDF resume parsing
- `python-docx` (1.1+) — Word document parsing
- `python-multipart` (0.0.9+) — File upload handling

**ML/Analytics:**
- `scikit-learn` (1.4-1.5) — Clustering, metrics (F1, precision, recall)
- `hdbscan` (0.8.33+) — Emerging skill clustering

**Frontend:**
- `vue` (3.4+) — Framework
- `vue-router` (4.3+) — Routing
- `pinia` (2.1+) — State management
- `element-plus` (2.6+) — UI components
- `echarts` (5.5+) — Charts
- `@antv/g6` (5.0+) — 2D graph visualization
- `3d-force-graph` (1.80+) — 3D graph visualization
- `three` (0.185+) — 3D rendering
- `axios` (1.6+) — HTTP client
- `msw` (2.2+) — Mock service worker

## Configuration

**Environment:**
- `.env` — Local development environment variables
- `.env.example` — Template with all required variables
- `.env.docker` — Docker-specific overrides
- `backend/app/config.py` — Pydantic Settings with validation

**Key Environment Variables:**
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Graph database
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB` — Relational database
- `REDIS_URI` — Cache and message broker
- `XUNFEI_API_KEY`, `XUNFEI_API_SECRET` — Xunfei Spark API
- `DEEPSEEK_API_KEY` — DeepSeek API
- `MIMO_API_KEY`, `MIMO_API_BASE` — Xiaomi MiMo API
- `CHROMA_HOST`, `CHROMA_PORT` — Vector database

**Build:**
- `backend/pyproject.toml` — Poetry dependencies, Ruff config, pytest config, mypy config
- `frontend/package.json` — npm dependencies and scripts
- `frontend/vite.config.ts` — Vite build configuration with manual chunks
- `frontend/tsconfig.json` — TypeScript compiler options

## Platform Requirements

**Development:**
- Docker & Docker Compose (development and production environments)
- Python 3.11 (via Docker or local)
- Node.js 20+ (for frontend build)
- Git (trunk-based workflow)

**Production:**
- Docker Compose deployment
- Multi-service architecture: backend, frontend (Nginx), Neo4j, PostgreSQL, Redis, ChromaDB, Ollama
- Resource limits: Backend 2 CPU / 2GB RAM, Celery worker 1 CPU / 1GB RAM

**Services Architecture (Docker Compose):**
- `starmap-backend` — FastAPI application (port 8000)
- `starmap-frontend` — Nginx serving built Vue app (port 80)
- `starmap-neo4j` — Graph database (ports 7474, 7687)
- `starmap-postgres` — PostgreSQL (port 5433 on host)
- `starmap-redis` — Cache and message broker (port 6379)
- `starmap-chroma` — Vector database (port 8001)
- `starmap-celery-worker` — Background task worker
- `starmap-ollama` — Local LLM inference (port 11434)

---

*Stack analysis: 2026-07-05*
