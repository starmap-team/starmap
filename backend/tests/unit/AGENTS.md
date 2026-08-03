# Backend unit-test knowledge base

## OVERVIEW

Unit tests mirror backend modules and cover API validation, auth, extraction, evolution, graph projection, matching, learning, pipeline, quality, review and services.

## WHERE TO LOOK

- Use `rg --files backend/tests/unit` to locate the test matching a source module.
- Shared fixtures live in `backend/tests/conftest.py`; domain-specific builders stay next to their tests.
- Evolution tests use current `diff_engine`, `trust_scorer`, `path_recommender`, `snapshot_manager` and orchestrator names.
- Pipeline tests cover the current staged DAG and compatibility behavior separately.

## CONVENTIONS

- Name tests after observable behavior and one condition.
- Avoid asserting line counts, internal helper order or historical response dumps.
- Use deterministic clocks/IDs where time or UUIDs affect results.
- Assert unified error fields for API failures.
- Keep each test independent of execution order and external network state.