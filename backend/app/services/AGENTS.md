# Backend services knowledge base

## OVERVIEW

Services coordinate domain logic and infrastructure. PostgreSQL business facts, Neo4j graph queries/projection, authentication, review, match, learning and dashboards meet here.

## AREAS

| Area | Files |
|---|---|
| Graph query/projection | `graph_service.py`, `graph_overview.py`, `graph_serializers.py`, `graph_sync.py`, `graph_projector.py`, `admin_graph_service.py` |
| Match/resume/learning | `match_service.py`, `resume_service.py`, `learning_service.py`, `recommendation_service.py` |
| Evolution | `evolution_service.py`, `timeseries_service.py` |
| Auth/admin/review | `auth_service.py`, `admin_*.py`, `review_service.py` |
| Shared resources | `resources.py` |

## CONVENTIONS

- API routes call services; services may call core algorithms and repositories/models.
- PostgreSQL is the business source of truth. `GraphProjector` uses PG UUIDs as `canonical_id` for Neo4j.
- Reuse `AppResources`/FastAPI dependencies; never create an engine per request.
- Graph query methods enforce read/write intent and parameterize values.
- Best-effort graph projection failure is observable and retryable; it does not rewrite PG facts.

## ANTI-PATTERNS

- Do not create a new `neo4j_service.py`; that historical file no longer exists.
- Do not merge PG and Neo4j records in one list endpoint to hide projection drift.
- Do not expose provider or ORM objects directly through API responses.