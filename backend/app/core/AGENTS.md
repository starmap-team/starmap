# Core backend subsystems knowledge base

## OVERVIEW
Core business logic under ``backend/app/core/`` is split by domain: extraction from job/resume text, evolution analysis over time, and any future domain modules added alongside them.

## STRUCTURE
```text
backend/app/core/
├── extraction/   # LLM-backed extraction, normalization, prompts, graph writes
└── evolution/    # snapshots, diffs, trust, hallucination defense, emergence, paths
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Implement text extraction flow | ``backend/app/core/extraction/`` | jd_extract.py orchestrates the pipeline |
| Change normalization behavior | ``backend/app/core/extraction/normalize.py`` | alias/synonym normalization rules |
| Maintain prompts/A-B routing | ``backend/app/core/extraction/prompt.py`` | prompt registry plus active version routing |
| Adjust LLM provider behavior | ``backend/app/core/extraction/llm_client.py`` | multi-provider fallback lives here |
| Persist extraction results to graph | ``backend/app/core/extraction/graph_writer.py`` | Neo4j write logic stays isolated |
| Tune evolution pipeline | ``backend/app/core/evolution/orchestrator.py`` | 8-step workflow coordinates downstream modules |
| Tune trust/emergence/path logic | ``backend/app/core/evolution/*.py`` | keep each concern in its own module |

## CONVENTIONS
- Keep extraction and evolution separated; do not mix normalization rules with graph-evolution logic.
- Route handlers stay thin; business orchestration belongs in ``core/`` and ``services/``.
- Shared domain models live in ``backend/app/models/``; schema changes require Alembic migrations.
- Async SQLAlchemy and Neo4j usage should stay behind service/resource abstractions instead of ad hoc drivers.

## ANTI-PATTERNS
- Do **not** put prompt orchestration or graph write orchestration directly in API routes.
- Do **not** embed Neo4j/LLM provider details inside normalization or diff logic.
- Do **not** duplicate extraction validation rules across multiple modules.
