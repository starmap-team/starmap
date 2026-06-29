# Frontend pages knowledge base

## OVERVIEW
User-facing page surfaces: panorama home, position browsing/detail, match diagnosis, evolution/quality dashboards, and admin views.

## STRUCTURE
```text
starmap/frontend/src/pages/
├── Home.vue
├── PositionList.vue
├── PositionDetail.vue
├── MatchDiagnosis.vue
├── EvolutionDashboard.vue
├── QualityDashboard.vue
└── Admin.vue
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Change main flows | `starmap/frontend/src/pages/*.vue` | Each page owns its UI flow |
| Implement shared layout | `starmap/frontend/src/layouts/` | Shared chrome around pages |
| Connect data/state | `starmap/frontend/src/stores/` | Pages should delegate data/state to stores |
| Use generated API types | `starmap/frontend/src/api/schema.ts` | Generated from contracts; gitignored |

## CONVENTIONS
- Keep pages focused on UI orchestration and validation, not API fetching details.
- Match diagnosis is intentionally step-driven; preserve the existing stage transitions.
- Use contract-backed types where possible instead of ad hoc local typing.

## ANTI-PATTERNS
- Do **not** hardcode API shapes that diverge from contract-backed types.
- Do **not** duplicate store logic directly inside page components.
- Do **not** mock around contract boundaries when the real concern is backend behavior.
