# Contracts knowledge base

## OVERVIEW

Cross-team API and validation truth source: OpenAPI, generated JSON Schema, shared models and Cypher templates.

## WHERE TO LOOK

| Task | Location |
|---|---|
| Add/change API | `openapi.yaml` first |
| Exported runtime schemas | `schemas/` |
| Shared model compatibility | `models/__init__.py` |
| Graph query contract | `graph_cypher/query_templates.cypher` |
| Validate | `validate.py` |
| Integration process | `API_INTEGRATION_GUIDE.md` |
| Published change history | `CHANGELOG.md` |

## CONVENTIONS

- Contract-first means OpenAPI changes precede backend routes and frontend calls.
- Backend API models live in `backend/app/schemas/`; export JSON Schema after changes.
- Frontend regenerates `src/api/schema.ts` from this OpenAPI file.
- Keep `snake_case` fields consistent across all layers.
- Historical contract audits live in `docs/archive/audits/` and are not current findings.

## VERIFICATION

Run `python starmap-contracts/validate.py`, then backend Schema export and frontend `npm run gen:api`.