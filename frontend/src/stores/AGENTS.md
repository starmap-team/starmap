# Frontend stores knowledge base

## OVERVIEW
Pinia stores that hold client-side domain state for graph, match, resume, quality, admin, user, and JD workflows.

## STRUCTURE
```text
starmap/frontend/src/stores/
├── admin.ts
├── graph.ts
├── jd.ts
├── match.ts
├── quality.ts
├── resume.ts
└── user.ts
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Change domain state | `starmap/frontend/src/stores/<domain>.ts` | One store per domain |
| Update API calls | same files | Keep fetch logic centralized in stores |
| Align types with API | `starmap/frontend/src/api/schema.ts` | Prefer generated contract types |

## CONVENTIONS
- Stores should encapsulate fetch logic and expose simple reactive state to pages.
- Keep each store focused on one user-facing domain.
- Treat MSW mocks as contract stand-ins, not permanent API truth.

## ANTI-PATTERNS
- Do **not** scatter API fetch logic across pages instead of using stores.
- Do **not** create store-level workarounds when the contract/backend shape needs fixing.
- Do **not** rely on mock-only shapes without a path to real backend alignment.
