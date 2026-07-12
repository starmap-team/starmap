# Tech Stack — StarMap

**Analysis Date:** 2026-07-12

## Backend

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Web Framework | FastAPI | >=0.110,<0.120 | Async REST API server |
| ASGI Server | Uvicorn | >=0.27,<0.30 | Production ASGI runner |
| Data Validation | Pydantic | >=2.6,<3.0 | Request/response schemas |
| Settings | pydantic-settings | >=2.2,<3.0 | Environment config management |
| ORM | SQLAlchemy (async) | >=2.0,<2.1 | PostgreSQL async ORM |
| DB Driver | asyncpg | >=0.29,<0.30 | PostgreSQL async driver |
| Migrations | Alembic | >=1.13,<1.14 | Schema migrations |
| Graph DB Driver | neo4j | >=5.17,<6.0 | Neo4j graph operations |
| Vector DB | chromadb | >=0.5,<0.6 | Skill vector similarity |
| Cache/Queue | Redis | >=5.0,<6.0 | Caching + Celery broker |
| Task Queue | Celery[redis] | >=5.3,<5.4 | Async pipeline execution |
| LLM Client | httpx | >=0.27,<0.28 | Xunfei Spark API calls |
| LLM Client | openai | >=1.30,<2.0 | OpenAI-compatible (Qwen/MiMo) |
| NLP | spaCy | >=3.7,<3.8 | Skill NER |
| NLP | jieba | >=0.42 | Chinese tokenization |
| PDF Parsing | pdfplumber | >=0.10 | Resume PDF extraction |
| DOCX Parsing | python-docx | >=1.1 | Resume Word extraction |
| ML | scikit-learn | >=1.4,<1.5 | F1/precision/recall metrics |
| Clustering | hdbscan | >=0.8.33 | Emerging skill clustering |
| Logging | loguru | >=0.7 | Structured logging |
| Retry | tenacity | >=8.2,<9.0 | LLM call retry logic |
| Config | pyyaml | >=6.0 | skill_taxonomy.yaml parsing |
| File Upload | python-multipart | >=0.0.9 | Resume file upload |
| Env | python-dotenv | >=1.0 | .env loading |

**Python Version:** >=3.11,<3.13

## Frontend

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Framework | Vue 3 | ^3.4.0 | SPA framework (Composition API) |
| Build Tool | Vite | ^5.2.0 | Dev server + bundler |
| Type System | TypeScript | ^5.4.0 | Static typing |
| State Management | Pinia | ^2.1.0 | Centralized stores |
| Router | vue-router | ^4.3.0 | Client-side routing |
| UI Library | Element Plus | ^2.6.0 | Component library |
| Icons | @element-plus/icons-vue | ^2.3.2 | UI icons |
| Charts | ECharts | ^5.5.0 | Data visualization |
| Vue-ECharts | vue-echarts | ^6.6.0 | ECharts Vue wrapper |
| 3D Graph | 3d-force-graph | ^1.80.0 | 3D skill graph visualization |
| 2D Graph | @antv/g6 | ^5.0.0 | 2D graph layout |
| 3D Engine | three.js | ^0.185.1 | WebGL rendering |
| HTTP Client | axios | ^1.6.0 | API requests |
| API Types | openapi-typescript | ^6.7.0 | OpenAPI -> TS type generation |
| Mock | MSW | ^2.2.0 | API mocking for tests |
| Unit Test | Vitest | ^1.4.0 | Unit testing |
| E2E Test | Playwright | ^1.61.1 | End-to-end testing |
| Lint | ESLint | ^8.57.0 | Code quality |
| CSS | Sass | ^1.72.0 | Styling preprocessor |

## Infrastructure

| Component | Technology | Purpose |
|---|---|---|
| Graph Database | Neo4j 5.x | Skill/Position knowledge graph |
| Relational DB | PostgreSQL | Position records, pipeline runs, learning plans |
| Cache/Broker | Redis | Caching, Celery broker, SSE event bus, pipeline stop flags |
| Vector Store | ChromaDB | Skill embedding similarity search |
| Task Queue | Celery | Async pipeline execution (crawl, dedup, clean, import, graph_sync) |
| Containerization | Docker | Multi-service deployment (docker-compose) |

## LLM Integration

| Provider | Config Key | Model | Purpose |
|---|---|---|---|
| Xiaomi MiMo | `MIMO_API_KEY`, `MIMO_API_BASE` | mimo-v2.5 | Primary LLM (OpenAI-compatible endpoint) |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | Alternative LLM |
| Xunfei Spark | `XUNFEI_API_KEY/SECRET/APP_ID` | generalv3.5 | JD/resume skill extraction |
| Local Ollama | (auto-fallback) | — | Degraded fallback when no cloud keys configured |

**LLM Usage Points:**
- JD skill extraction (`backend/app/api/v1/extract.py`)
- Resume skill extraction (`backend/app/api/v1/extract.py`, `backend/app/api/v1/resume.py`)
- Closed-loop pipeline step 2 (skill extraction via `backend/app/api/v1/loop.py`)
- Jobseeker analysis pipeline (`backend/app/api/v1/pipeline/routes.py` `/pipeline/analyze`)
- Judge evaluation with LLM judge (`backend/app/api/v1/judge.py`)

## Configuration

**Environment:**
- Backend config: `backend/app/config.py` (pydantic-settings, reads from `.env`)
- Frontend config: `VITE_API_BASE_URL` env var (defaults to `/api/v1`)
- `.env` files present at project root and `backend/` (contain secrets — never read)

**Key Config Files:**
- `backend/app/config.py` — All settings with defaults and validation
- `starmap-contracts/openapi.yaml` — API contract (source of truth)
- `frontend/vite.config.ts` — Vite build config
- `frontend/tsconfig.json` — TypeScript config

**Auth:**
- JWT Bearer tokens (HMAC-SHA256, `settings.secret_key`)
- Dev mode: accepts `dev-token` or returns default dev user
- Production: strict JWT validation with expiry check
- Admin role check via `require_admin` dependency

---

*Stack analysis: 2026-07-12*
