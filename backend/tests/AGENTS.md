# Backend tests knowledge base

## OVERVIEW
Unit tests, integration tests, fixtures, and conftest for the StarMap backend. pytest runs with coverage gate ≥60%.

## STRUCTURE
```text
backend/tests/
├── conftest.py              # Shared fixtures: async DB sessions, mock Neo4j, test clients
├── __init__.py
├── fixtures/                # Test data fixtures (JSON, JSONL)
├── integration/             # Integration tests (API-level, needs DB/services)
│   └── test_extraction_api.py
└── unit/                    # Unit tests (24 files, mocked dependencies)
    ├── test_health.py
    ├── test_models.py
    ├── test_extraction.py
    ├── test_normalize.py
    ├── test_graph_service.py
    ├── test_graph_writer_stage3.py
    ├── test_graph_ingest.py
    ├── test_match_golden.py
    ├── test_judge_service.py
    ├── test_quality_evaluate.py
    ├── test_evolution_orchestrator.py
    ├── test_evolution_diff_engine.py
    ├── test_evolution_trust_hallucination.py
    ├── test_evolution_emergence_path.py
    ├── test_evolution_integration_pipeline.py
    ├── test_evolution_api.py
    ├── test_stage2_skeleton.py
    ├── test_stage3_analyze.py
    ├── test_stage3_api.py
    ├── test_stage3_helpers.py
    ├── test_stage4_api.py
    ├── test_celery_stage3_tasks.py
    ├── test_dependencies.py
    └── test_persist_extraction.py
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|---|
| Add unit test | `unit/test_<module>.py` | One test file per backend module; mock external deps |
| Add integration test | `integration/` | API-level tests; may need DB fixtures |
| Add test fixtures | `fixtures/` | JSON/JSONL data files |
| Configure test DB | `conftest.py` | async session fixtures, mock resources |
| Run tests | `pytest` from backend/ | `--cov=app --cov-fail-under=60` |

## CONVENTIONS
- Unit tests mock all external services (Neo4j, LLM, Celery).
- Integration tests use real DB sessions but mock LLM/graph where needed.
- Test file naming: `test_<module>.py` matching the source module name.
- Fixtures in `conftest.py` provide async sessions, test clients, and mock resources.
- Coverage gate: 60% minimum (configured in pyproject.toml).

## ANTI-PATTERNS
- Do **not** make real LLM calls in unit tests — use mocks.
- Do **not** put browser/E2E tests here — they belong in `tests/e2e/`.
- Do **not** share mutable state between test files.
- Do **not** skip conftest fixtures in favor of inline setup — prefer reusable fixtures.
