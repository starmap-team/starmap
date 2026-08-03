# ORM models knowledge base

## OVERVIEW

SQLAlchemy async PostgreSQL models. `__init__.py` exposes the declarative Base and model imports used by Alembic.

## MODULES

| File | Domain |
|---|---|
| `extraction_models.py` | raw/extracted JD, positions, skills and relations |
| `evolution_models.py` | snapshots, changelogs, paths and time series |
| `learning_models.py` | learning plans and progress |
| `pipeline_models.py` | pipeline runs, schedules, sources, loop and outbox |
| `user.py` | users and authentication lifecycle |
| `audit_models.py` | persistent audit events |
| `review_audit_log.py` | review workflow audit records |

## CONVENTIONS

- Schema changes require a new Alembic revision; do not edit an applied migration.
- Use timezone-aware timestamps and explicit constraints/indexes.
- Relationships and foreign keys must reflect ownership and deletion behavior.
- API request/response models do not belong here; use `app/schemas/`.
- Register new model modules through `app/models/__init__.py` so Alembic metadata sees them.

## VERIFICATION

Run `poetry run alembic heads`, `poetry run alembic upgrade head`, and focused model/migration tests from `backend/`.