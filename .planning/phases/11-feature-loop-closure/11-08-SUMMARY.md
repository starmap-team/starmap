---
phase: 11-feature-loop-closure
plan: 11-08
wave: 3
requirements: [LOOP-07, LOOP-08, LOOP-09]
decision_refs: [D-14, D-15, D-16]
status: complete
---

# 11-08 Summary: 审核Neo4j同步 + Pipeline权限UX + LoopDemo修复

## Accomplishments

1. **Admin audit → Neo4j sync** — Added `_sync_neo4j_on_audit()` helper in `admin_audit_service.py` that updates Neo4j node `trust_score` and `status` on approve/reject. Both `approve_audit()` and `reject_audit()` now accept `neo4j_driver` param and call the sync helper. Neo4j sync failure is non-blocking.
2. **Pipeline admin controls** — Added `isAdmin` from `usePipelineMonitor` to PipelineMonitor.vue. Header management buttons ("触发流水线", "断点续跑", "取消运行", "定时调度", "配置") wrapped in `<template v-if="isAdmin">`. Schedule panel "新增" button also guarded with `v-if="isAdmin"`.
3. **LoopRunRequest.target_position Optional** — Changed `target_position` from `str` to `str | None = Field(default=None)` in `loop.py`. Added `StepStatus.SKIPPED` to `loop_orchestrator.py`. Steps 4 (Match Diagnosis) and 5 (Learning Path) are skipped when `target_position` is None.

## User-facing Changes

- Admin approve/reject now syncs to Neo4j (trust_score=1.0, status='approved')
- Non-admin users don't see pipeline management buttons
- Loop run can be started without specifying a target position (steps 4/5 skipped)

## Files Modified

- `backend/app/services/admin_audit_service.py` — Added `_sync_neo4j_on_audit()`, modified approve/reject
- `backend/app/api/v1/admin.py` — Pass `neo4j_driver` to audit service
- `frontend/src/composables/usePipelineMonitor.ts` — Exposed `isAdmin`
- `frontend/src/pages/PipelineMonitor.vue` — `v-if="isAdmin"` on admin controls
- `backend/app/api/v1/loop.py` — `target_position: str | None = Field(default=None)`
- `backend/app/core/pipeline/loop_orchestrator.py` — Added `StepStatus.SKIPPED`, skip logic

## UAT Verification

- ✅ `_sync_neo4j_on_audit` has 3 references in admin_audit_service.py
- ✅ Admin user sees management buttons; non-admin (demo) user doesn't
- ✅ POST /loop/run without target_position → 200 (accepted, not 422)
- ✅ StepStatus.SKIPPED exists in loop_orchestrator.py
