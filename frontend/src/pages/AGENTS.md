# Frontend pages knowledge base

## OVERVIEW

Route-level Vue components. The authoritative route list and auth/admin metadata live in `frontend/src/router/index.ts`.

## CONVENTIONS

- Pages orchestrate layout, stores, composables and child components; they do not duplicate API clients.
- All protected routes rely on the router bootstrap/auth guard.
- Reusable views move to `src/components/`; lifecycle and complex interactions move to `src/composables/`.
- Use generated API types and project `snake_case` fields.
- Loading, empty, error and permission states are part of page behavior.

## WHERE TO LOOK

- Panorama and graph: `Home.vue`
- Position and match: `PositionList.vue`, `PositionDetail.vue`, `MatchDiagnosis.vue`
- Evolution/quality/data: `EvolutionDashboard.vue`, `QualityDashboard.vue`, `DataDashboard.vue`
- Pipeline: `PipelineMonitor.vue`, `PipelineAnalysis.vue`
- Admin/auth: `Admin.vue`, `UserManagement.vue`, `AuditLog.vue`, `Login.vue`, `ChangePassword.vue`

Use `rg --files frontend/src/pages -g "*.vue"` instead of maintaining a hand-written count.