# Backend tests knowledge base

## OVERVIEW

Pytest unit and integration suites for the FastAPI backend. The active coverage threshold is configured in `backend/pyproject.toml`; do not duplicate a historical value here.

## STRUCTURE

| Path | Purpose |
|---|---|
| `conftest.py` | shared settings, resource and client fixtures |
| `fixtures/` | deterministic JSON/text input |
| `unit/` | isolated domain, service and route behavior |
| `integration/` | boundaries requiring multiple real components |

## CONVENTIONS

- Test behavior and public contracts, including error paths and authorization.
- Mock only external services that cannot be made deterministic; prefer real domain objects and focused fakes.
- Keep real LLM, production Neo4j and production credentials out of unit tests.
- Place browser/live-stack scenarios in repository `tests/e2e/`.
- Run `poetry run pytest` from `backend/` so configured coverage and pythonpath apply.