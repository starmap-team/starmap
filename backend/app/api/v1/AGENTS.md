# API v1 knowledge base

## OVERVIEW
Route layer for `/api/v1`; one module per business domain plus a shared router aggregator.

## STRUCTURE
```text
starmap/backend/app/api/v1/
├── router.py        # mounts all v1 routers under /api/v1
├── admin.py         # admin/prompts/review/stats endpoints
├── graph.py         # graph query endpoints
├── match.py         # position match diagnostics
├── extract.py       # JD and resume extraction endpoints
├── evolution.py     # evolution trends/analyze/changelog/path endpoints
├── quality.py       # graph quality dashboard
├── position.py      # position management
├── resume.py        # resume endpoints
└── judge.py         # judge evaluation endpoints
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add a new domain route | `starmap/backend/app/api/v1/<domain>.py` | Keep one router per file |
| Wire new routes into v1 | `starmap/backend/app/api/v1/router.py` | Import the module router and add it to `api_router` |
| Implement business logic | `starmap/backend/app/services/` | Routes should delegate to services, not inline heavy logic |
| Keep frontend types aligned | `starmap/starmap-contracts/` | Contract changes should precede route changes |

## CONVENTIONS
- Each router uses its own `prefix` and `tags` to keep Swagger readable.
- Routes should return contract-shaped response models, not raw ORM entities.
- Graph endpoints go through Neo4j driver dependencies; DB-backed endpoints use the async session dependency.

## ANTI-PATTERNS
- Do **not** add routes without updating the contract where the API surface changes.
- Do **not** put Neo4j/SQL business orchestration directly in route handlers.
- Do **not** introduce sync-only blocking calls into async endpoints.
