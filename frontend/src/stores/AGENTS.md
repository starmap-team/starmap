# Frontend stores knowledge base

## OVERVIEW

Pinia domain state and API actions. Stores cover auth, graph, extraction/resume, match, learning, evolution, pipeline, quality, review, prompts, data sources and dashboards.

## CONVENTIONS

- One domain owner per store; compatibility barrel stores only re-export existing behavior.
- API calls use `src/api/request.ts` or the generated-type wrapper in `src/api/client.ts`.
- Validate relevant responses with `useResponseValidation()` in development without changing the returned business value.
- Keep server fields in `snake_case` and define explicit TypeScript types.
- Pages consume reactive state/actions and do not recreate fetch/cache logic.

## CURRENT SPLITS

- Learning: `learningPlan.ts`, `learningRecommendation.ts`, `learningAnalytics.ts` with compatibility exports in `learning.ts`.
- Pipeline: `pipelineRun.ts`, `pipelineConfig.ts` with compatibility exports in `pipeline.ts`.

## ANTI-PATTERNS

- No `admin.ts` compatibility store: it no longer exists.
- No MSW-only response shapes.
- Do not hide contract drift behind broad casts; fix schema/client/store boundaries.