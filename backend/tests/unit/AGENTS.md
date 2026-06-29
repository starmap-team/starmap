# Unit tests knowledge base

## OVERVIEW
24 unit test files covering all backend domains. Each file mocks external dependencies (Neo4j, LLM, Celery, DB) and tests one module in isolation.

## STRUCTURE
```text
unit/
├── test_health.py                    # Health endpoint tests
├── test_models.py                    # Pydantic model validation
├── test_dependencies.py              # FastAPI dependency injection
├── test_extraction.py                # JD extraction pipeline
├── test_normalize.py                 # Skill normalization/alias logic
├── test_persist_extraction.py        # Extraction DB persistence
├── test_graph_service.py             # Graph query service
├── test_graph_ingest.py              # Graph data ingestion
├── test_graph_writer_stage3.py       # Stage 3 graph writes
├── test_match_golden.py              # Match accuracy against golden set
├── test_judge_service.py             # Judge/F1 scoring service
├── test_quality_evaluate.py          # Quality dashboard evaluation
├── test_evolution_orchestrator.py    # 8-step evolution pipeline
├── test_evolution_diff_engine.py     # Snapshot diff computation
├── test_evolution_trust_hallucination.py  # Trust + hallucination guard
├── test_evolution_emergence_path.py  # Emergence detection + path recommender
├── test_evolution_integration_pipeline.py # End-to-end evolution pipeline
├── test_evolution_api.py             # Evolution API endpoint tests
├── test_stage2_skeleton.py           # Stage 2 skeleton tests
├── test_stage3_analyze.py            # Stage 3 analysis tests
├── test_stage3_api.py                # Stage 3 API endpoint tests
├── test_stage3_helpers.py            # Stage 3 helper function tests
├── test_stage4_api.py                # Stage 4 API endpoint tests
└── test_celery_stage3_tasks.py       # Celery task tests (async bridge)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|---|
| Test extraction logic | `test_extraction.py`, `test_normalize.py` | Mock LLM calls; verify normalization rules |
| Test graph operations | `test_graph_service.py`, `test_graph_ingest.py`, `test_graph_writer_stage3.py` | Mock Neo4j driver |
| Test match accuracy | `test_match_golden.py` | Golden set validation; real scoring logic |
| Test evolution pipeline | `test_evolution_*.py` | 5 files covering orchestrator, diff, trust, emergence, paths |
| Test Celery tasks | `test_celery_stage3_tasks.py` | Tests async bridge pattern |

## CONVENTIONS
- One test file per source module; name mirrors source: `test_<module>.py`.
- All external services mocked: Neo4j, LLM client, Celery broker, async DB sessions.
- Use `conftest.py` fixtures from parent directory for shared setup.
- Test both happy path and error cases (LLM failures, empty results, validation errors).

## ANTI-PATTERNS
- Do **not** call real LLM APIs — mock `llm_client.call_llm_with_fallback()`.
- Do **not** connect to real Neo4j — mock the driver/service layer.
- Do **not** use mutable module-level state across tests.
- Do **not** test API routing here — test business logic only.
