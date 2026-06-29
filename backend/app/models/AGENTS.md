# ORM models knowledge base

## OVERVIEW
SQLAlchemy 2.0 declarative models for PostgreSQL. Two model files cover the extraction pipeline and the evolution subsystem; `__init__.py` re-exports all tables via a single `Base`.

## STRUCTURE
```
backend/app/models/
├── __init__.py              # DeclarativeBase + re-exports all ORM classes
├── extraction_models.py     # JDExtractionRecord, RawJDRecord, SkillRecord, PositionRecord, PositionSkillRelation, SkillAliasRecord, ExtractionEvaluationRecord, SystemConfig
└── evolution_models.py      # EvolutionSnapshot, EvolutionChangelog, EvolutionPath, SkillTimeseries
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add extraction-related table | extraction_models.py | UUID PKs, UTC timestamps, JSON columns for flexible data |
| Add evolution-related table | evolution_models.py | Snapshot/changelog/path/timeseries patterns |
| Register new model | __init__.py | Import + add to `__all__`; Alembic auto-detects via Base |
| Generate migration | `alembic revision --autogenerate -m "desc"` | Run from `backend/` directory |

## CONVENTIONS
- All tables use `UUID(as_uuid=True)` primary keys with `uuid.uuid4` default.
- Timestamps are `DateTime(timezone=True)` with `datetime.now(UTC)` defaults.
- JSON columns store structured lists/dicts (skills, evidence, metadata).
- `Float` columns for scores/confidence; `Integer` for counts.
- Every new table requires an Alembic migration — never alter schema directly.

## ANTI-PATTERNS
- Do **not** add business logic to ORM models; they are pure schema definitions.
- Do **not** use `Integer` PKs; this project standardizes on UUID.
- Do **not** skip `__all__` updates when adding new model classes.
- Do **not** create foreign keys between extraction and evolution tables; they serve different subsystems.
