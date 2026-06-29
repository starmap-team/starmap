# Backend services knowledge base

## OVERVIEW
Business-logic layer consumed by API v1 routes; one module per domain, plus shared Neo4j/session resources. The `dependencies.py` module in the parent `app/` package provides FastAPI DI helpers.

## STRUCTURE
```
backend/app/services/
├── graph_service.py     # Neo4j-backed graph queries (read-only Cypher, keyword filter for writes)
├── match_service.py     # Position-match diagnosis engine (skill alignment, gap, proficiency scoring)
├── judge_service.py     # LLM-as-judge evaluation wrapper (multi-dimension scoring, A/B support)
├── resume_service.py    # Resume PDF/DOCX parsing → extraction pipeline
├── neo4j_service.py     # Async Neo4j driver context manager
└── resources.py         # AppResources dataclass: PG engine/sessionmaker, Neo4j driver, Redis client
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Graph queries | graph_service.py | Read-only Cypher; WRITE_CYPHER_KEYWORDS blocklist enforces read safety |
| Match scoring | match_service.py | Uses normalize_skill from extraction; proficiency weights: 了解=0.35, 熟悉=0.65, 精通=0.9 |
| Judge evaluation | judge_service.py | Wraps evaluation.judge_eval; supports pair-wise A/B and batch mode |
| Resume parsing | resume_service.py | pdfplumber + python-docx; delegates to extract_from_jd pipeline |
| DB/session setup | resources.py | Singleton AppResources; initialized in app lifespan, closed on shutdown |
| FastAPI DI hooks | ../dependencies.py | get_neo4j_driver, get_redis_client, get_db_session |

## CONVENTIONS
- Services are injected into routes via FastAPI `Depends()` or imported directly.
- Neo4j sessions use the async context manager from `neo4j_service.py`.
- `graph_service.py` enforces read-only Cypher by checking against WRITE_CYPHER_KEYWORDS.
- `resources.py` is a module-level singleton; `init_resources()` called once at app startup.
- Health checks use `healthcheck_resources()` which pings PG, Neo4j, and Redis independently.

## ANTI-PATTERNS
- Do **not** call Neo4j directly from route handlers; use graph_service or neo4j_service.
- Do **not** import LLM client internals into services; use the prompt/llm_client abstraction.
- Do **not** store mutable state in service modules; use resources.py singletons.
- Do **not** create new database engines in services; reuse the AppResources sessionmaker.
