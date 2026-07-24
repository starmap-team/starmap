# Scripts knowledge base

## OVERVIEW

Repository operations for contract/schema generation, database initialization, PG/Neo4j reconciliation, fixtures, evaluation, quality and deployment.

## CONVENTIONS

- Run scripts from the location documented by their imports and check `--help` first.
- Database/graph writers must be idempotent or explicitly guarded; add dry-run where practical.
- `offline/` produces fixtures only; `deprecated/` is historical and must not be used in production.
- Generated reports go to ignored output directories or `docs/archive/reports/<date>/` when evidence must be retained.
- Keep secrets and environment-specific hostnames out of source.

## WHERE TO LOOK

| Task | Entry |
|---|---|
| Export backend JSON Schema | `export_json_schemas.py` |
| Validate contract/type sync | `check-contract-sync.js`, `verify-contract.ts`, `check-type-sync.ts` |
| Initialize Neo4j/ESCO | `init_neo4j_schema.py`, `import_esco_skill.py` |
| Rebuild/reconcile graph | `rebuild_graph.py`, `reconcile_graph.py` |
| Data consistency | `ensure_data_consistency.py`, `validate_graph_data.py` |
| Operational integration | `daily-integration.sh`, `server-daily.sh` |
| Documentation gate | `check-docs.ps1`