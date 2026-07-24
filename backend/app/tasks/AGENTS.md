# Celery tasks knowledge base

## OVERVIEW

`celery_app.py` defines task entrypoints and schedules. `stage3_services.py` contains async extraction/graph service operations used by thin sync task wrappers.

## TASK GROUPS

- JD extraction and graph building
- Evolution pipeline execution
- ETL stage execution and DAG advance
- Scheduled pipeline runs and orphan-run sweeping

## CONVENTIONS

- Task entrypoints return JSON-serializable values.
- Use the established `run_async` bridge; do not create ad hoc event loops in task code.
- Put reusable async business logic in services/core, not in decorators.
- External calls have bounded retries, timeouts and idempotent state transitions.
- Pipeline cancellation checks both persistent state and the Redis stop flag.

## VERIFICATION

Test task wrappers with fake broker/service boundaries and test state transitions independently. Do not call real LLM or production databases from unit tests.