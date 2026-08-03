# Deprecated Scripts

These scripts were used to seed data directly into PostgreSQL and Neo4j,
bypassing the proper ETL pipeline and review workflow. They are superseded by:

## Replacement

- **Fixture loader**: `backend/app/data/fixtures/seed.py`
  - Reads structured JSON from `app/data/fixtures/`
  - Writes to PG via review_service (proper approval workflow)
  - Syncs to Neo4j via graph_writer (complete ontology)
  - Idempotent (safe to re-run)

The old scripts remain in this directory for historical reference only and
must not be referenced from new code, CI, Compose or operational playbooks.