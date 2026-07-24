# API v1 knowledge base

## OVERVIEW

Route layer for `/api/v1`. Public API shape is defined in `starmap-contracts/openapi.yaml`; request and response models belong in `backend/app/schemas/`.

## WHERE TO LOOK

| Task | Location |
|---|---|
| Register domain routers | `router.py` |
| Authentication endpoints | `auth.py` |
| Admin domains | `admin.py`, `admin_users.py`, `admin_graph_nodes.py`, `admin_prompts.py` |
| Extraction and resume | `extract.py`, `resume.py`, `upload_validation.py` |
| Graph and positions | `graph.py`, `position.py` |
| Match and learning | `match.py`, `learning.py` |
| Evolution | `evolution.py`, `evolution_*.py` |
| Pipeline | `pipeline/routes.py`; legacy local pipeline schemas remain compatibility-only |
| API Pydantic models | `../../schemas/` |

## CONVENTIONS

- Keep handlers thin: validate HTTP input, invoke services, return centralized Schema models.
- Use `Depends(get_db_session)` and resource dependencies instead of creating clients or engines.
- Mutating admin routes require `require_admin`; public/auth exceptions must be explicit.
- Use the unified error response and `ErrorCode` values from `app/core/validation/`.
- Update OpenAPI before adding or changing a public path or field.

## ANTI-PATTERNS

- Do not define new request/response `BaseModel` classes in route files.
- Do not embed raw SQL, graph orchestration, or LLM provider logic in handlers.
- Do not return ORM entities or unvalidated provider payloads directly.