---
phase: 11-feature-loop-closure
plan: 11-02
wave: 1
requirements: [LOOP-03]
decision_refs: [D-07, D-08]
status: complete
---

# 11-02 Summary: 学习计划 createPlan 请求结构修复

## Accomplishments

1. **buildCreatePlanRequest() mapping function** — Added to `frontend/src/stores/learning.ts`: type-safe `CreatePlanRequestBody` interface and mapping function that converts raw `matchResult` into the correct request schema expected by backend `CreatePlanRequest` (position, match_score, skills[]).
2. **createPlan() uses mapping** — Modified `learning.ts` `createPlan()` to call `buildCreatePlanRequest(matchResult)` before POST, ensuring `match_score` is always included.
3. **useLearningActions wired** — Updated `useLearningActions.ts` to import and use `buildCreatePlanRequest` in `handleAddToPlan()`.

## User-facing Changes

- "创建学习计划" from MatchDiagnosis now sends correctly structured request body
- Previously missing `match_score` field is now included in POST /learning/plan
- Skills array includes `importance`, `gap_level`, `learning_path`, `target_proficiency`

## Files Modified

- `frontend/src/stores/learning.ts` — Added `CreatePlanRequestBody` interface, `buildCreatePlanRequest()` function; modified `createPlan()`
- `frontend/src/composables/useLearningActions.ts` — Import `buildCreatePlanRequest`, use in `handleAddToPlan()`

## UAT Verification

- ✅ POST /learning/plan with {position, match_score: 0.65, skills: [...]} → 200 + plan_id
- ✅ Response includes `match_score_at_creation: 0.65`
