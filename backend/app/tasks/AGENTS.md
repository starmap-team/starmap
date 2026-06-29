# Celery tasks knowledge base

## OVERVIEW
Async task layer for long-running extraction, graph-building, and evolution-trend operations. Celery workers run sync wrappers that delegate to async business logic in `stage3_services.py`.

## STRUCTURE
```
backend/app/tasks/
├── celery_app.py        # Celery app config, task definitions with retry
└── stage3_services.py   # Async business logic: persist, graph-write, trend analysis
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add a new Celery task | celery_app.py | Define task with `@celery_app.task(bind=True, max_retries=3)` |
| Implement task business logic | stage3_services.py | All async SQLAlchemy/Neo4j work lives here |
| Bridge async→sync for Celery | stage3_services.run_async() | Required because Celery workers are sync |
| Adjust Redis broker/backend | celery_app.py | Reads `settings.redis_uri` |

## CONVENTIONS
- Task functions in `celery_app.py` are thin wrappers: log → `run_async(coroutine)` → retry on failure.
- All real logic lives in `stage3_services.py` as `async` functions.
- `run_async()` handles the sync/async bridge; never call `asyncio.run()` directly in tasks.
- Tasks return JSON-serializable dicts (Celery serialization requirement).
- Bounded limits in service functions (e.g., `max(1, min(limit, 1000))`) prevent runaway queries.

## ANTI-PATTERNS
- Do **not** put async business logic directly in Celery task functions.
- Do **not** share database connections between Celery workers and the FastAPI app; each creates its own engine.
- Do **not** skip retry decorators on tasks that call external services (LLM, Neo4j, PostgreSQL).
- Do **not** call Celery tasks synchronously from API endpoints; use `.delay()` or `.apply_async()`.
