# Backend services knowledge base

## OVERVIEW
Business-logic layer consumed by API v1 routes; one module per domain, plus shared Neo4j/session resources.

## STRUCTURE
```text
starmap/backend/app/services/
├── graph_service.py     # Neo4j-backed graph queries (read-only Cypher, keyword filter for writes)
├── match_service.py     # position-match diagnosis engine (skill alignment, gap, proficiency scoring)
├── judge_service.py     # LLM-as-judge evaluation wrapper (multi-dimension scoring, A/B support)
├── resume_service.py    # resume PDF/DOCX parsing → extraction pipeline
├── neo4j_service.py     # async Neo4j driver context manager
├── resources.py         # AppResources dataclass: DB engine, session factory, Redis, Neo4j driver
└── .gitkeep
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Graph queries | graph_service.py | Read-only Cypher; WRITE_CYPHER_KEYWORDS blocklist enforces read safety |
| Match scoring | match_service.py | Uses 
ormalize_skill from extraction; proficiency weights: 了解=0.35, 熟悉=0.65, 精通=0.9 |
| Judge evaluation | judge_service.py | Wraps evaluation.judge_eval; supports pair-wise A/B and batch mode |
| Resume parsing | esume_service.py | pdfplumber + python-docx; delegates to extract_from_jd pipeline |
| DB/session setup | esources.py | Singleton AppResources; imported at app startup |

## CONVENTIONS
- Services are injected into routes via FastAPI Depends() or imported directly.
- Neo4j sessions use the async context manager from 
eo4j_service.py.
- graph_service.py enforces read-only Cypher by checking against WRITE_CYPHER_KEYWORDS.

## ANTI-PATTERNS
- Do **not** call Neo4j directly from route handlers; use graph_service or 
eo4j_service.
- Do **not** import LLM client internals into services; use the prompt/llm_client abstraction.
- Do **not** store mutable state in service modules; use esources.py singletons.