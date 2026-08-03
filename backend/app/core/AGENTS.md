# Core backend knowledge base

## OVERVIEW

`backend/app/core/` owns domain computation. HTTP concerns and graph/database adapters stay outside core unless a module is explicitly an orchestrator over typed domain services.

## DOMAINS

| Path | Responsibility |
|---|---|
| `dashboard/` | dashboard aggregation and SSE broadcast helpers |
| `evolution/` | snapshots, diffs, trust, emergence and evolution paths |
| `extraction/` | JD/resume extraction, prompts, normalization and graph-write preparation |
| `learning/` | path generation and progress tracking |
| `llm/` | provider-independent LLM cost tracking |
| `matching/` | scoring, caching and learning-gap construction |
| `pipeline/` | ETL DAG state, execution, scheduling and quality |
| `validation/` | unified error codes and FastAPI validation handling |

## CONVENTIONS

- Keep pure algorithms independent of FastAPI request/response objects.
- API-facing Pydantic models live in `app/schemas/`; ORM models live in `app/models/`.
- Neo4j queries and PG/Neo4j projection orchestration live in `app/services/`.
- Reuse extraction normalization and shared validation instead of copying rules.
- Preserve async boundaries and use the established Celery bridge for worker entrypoints.

## ANTI-PATTERNS

- No direct route imports into core.
- No provider-specific credentials or HTTP parsing in domain algorithms.
- No second implementation of a domain rule under another package.