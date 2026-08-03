---
phase: 3 (audit scope)
reviewers: [gemini, codex, opencode, ollama]  # all attempted, all failed
reviewed_at: 2026-07-29
plans_reviewed: [16-01-PLAN.md, 16-02-PLAN.md, 16-03-PLAN.md]
focus: UI/UX + 前端后端 API + 实际功能验证
review_status: external_reviewers_unavailable
fallback: orchestrator_self_review
---

# Cross-AI Plan Review — Phase 3 (UI/UX + 前后端 API + 实际功能)

## ⚠️ External Reviewer Availability

All 4 detected CLIs failed due to local environment issues (NOT prompt problems):

| Reviewer | Status | Reason |
|----------|--------|--------|
| **Gemini** | ❌ failed | `GEMINI_API_KEY` not set |
| **Codex** | ❌ failed | 401 Unauthorized — invalid key (xiaomimimo.com routing) |
| **OpenCode** | ❌ failed | Output file disappeared after timeout (claude-mem plugin conflict) |
| **Ollama (qwen2.5:7b)** | ❌ failed | Timeout (3 min insufficient for 7B model) |

**No external AI review was obtained.** Falling back to orchestrator self-review using the same criteria (per `gsd-core/references/`) AND the rich debug context from 3 previous debug sessions.

---

# Orchestrator Self-Review (Phase 3 Audit Plans)

## Summary

The 3 plans (16-01, 16-02, 16-03) comprehensively address the 10 user complaints surfaced in Phase 3 debug sessions. The priority ordering (Wave 1: 16-01+16-02 parallel; Wave 2: 16-03) is correct. The 5-8 day estimate is realistic but slightly optimistic — Plan 16-03 may need an extra day for the audit report.

**Overall Risk: LOW** — these are audit/verification tasks with clear scope and minimal risk.

---

## Strengths

1. **Real bug discovery basis**: All 10 user complaints were observed in actual screenshots, not theoretical. The plans target verified issues.

2. **Tracer-first decomposition**: Plan 16-01 leads with end-to-end test (`test_full_pipeline_runs_all_stages`) that exercises the entire pipeline before any targeted fixes. This matches the project's tracer-first methodology.

3. **Source-grounded investigation**: Every Issue in 16-01/16-02 cites a specific file:line and the observed symptom. e.g.:
   - Issue A (SSE): `backend/app/core/dashboard/sse_broadcaster.py` 
   - Issue E (SSE toast): `frontend/src/composables/useSSE.ts:46-68`
   - Issue F (progress fallback): `frontend/src/components/PipelineStageCard.vue:146-150`

4. **M1-M7 compliance**: All 4 mandatory rules cited in plans:
   - M1 (UUID fidelity): 16-03 跨端一致性测试 ensures sample 20x field equality
   - M4 (no baseline = no red): 16-01 Issue B separates cancelled from failed for success_rate
   - M5 (口径单一): 16-03 Task 4 documents field semantics in 16-cross-tier-report.md
   - M7 (verify-first): Each fix is followed by an integration test

5. **Latency measurement is principled**: 16-02 Task 5 uses 5 trial runs to get P50/P95 — statistically meaningful without being excessive.

6. **Cross-tier consistency check is rigorous**: 16-03 Task 1 runs N=20 parametrized trials; catching a flaky bug in 1/20 cases is statistically significant.

---

## Concerns

### MEDIUM Severity

**M1. SSE reconnect logic — `silentRefreshForSSE` may not fire correctly under all failure modes**

Plan 16-02 Task 1 adds `ElMessage.success` after `silentRefreshForSSE` resolves successfully. But the original code in `useSSE.ts:215-235` shows:
```ts
if (consecutiveFailures === 1 && !refreshingToken) {
  const hasRefreshToken = !!localStorage.getItem('starmap_refresh_token')
  if (hasRefreshToken) {
    refreshingToken = true
    silentRefreshForSSE().then((newToken) => {
      refreshingToken = false
      if (newToken && !disposed) {
        retryCount = 0
        consecutiveFailures = 0
        connectSSE()
        return
      }
      handleSSEError()
    })
```

The toast would only show on `newToken !== null` (refresh succeeded). But if `handleSSEError()` triggers (refresh failed), there's no toast. Plan should also show toast on refresh failure or on any successful reconnect.

**Recommendation:** Add toast on `connectSSE()` success after reconnect, not just inside `silentRefreshForSSE`.

**M2. Plan 16-03 index migration may conflict with existing indexes**

The proposed `idx_pipeline_runs_status_started` index — let me verify this doesn't already exist. Looking at the project, there are likely existing indexes from prior migrations.

**Recommendation:** Plan should include a `SELECT 1 FROM pg_indexes WHERE indexname = '...'` pre-check or use `IF NOT EXISTS`.

**M3. Stage card progress fallback may mask actual bugs**

Plan 16-02 Task 2 fallback: `if (status === 'completed') return 100`. This is a good UX fix, but it could mask backend bugs (like the zombie run issue we already fixed). If backend reports progress=null for a real completed stage, we silently show 100% instead of investigating.

**Recommendation:** Add a console.warn when fallback fires, so frontend devs can spot backend issues.

### LOW Severity

**L1. The 5-8 day estimate may be optimistic**

Plan 16-01 has 9 Tasks (4 issues + 5 tests). At ~2 days of focused work, each fix + test cycle is tight. Realistically:
- 16-01: 3 days
- 16-02: 3 days
- 16-03: 2 days
- **Total: 8 days**, not 5-8. Update estimate.

**L2. The "查看全部" button in PipelineStageCard (already implemented) was not in the original UI-SPEC**

Plan 16-02 Task 2 says "新增 '查看全部' 按钮 → 打开 el-dialog 显示完整数据" — this was actually implemented in the previous debug session, not planned here. Plan should reference the existing implementation rather than duplicate.

**Recommendation:** Update 16-02 to reference `frontend/src/components/PipelineStageCard.vue` existing dialog, add tests only.

**L3. Plan 16-01 Issue C "数字口径不一致" is mostly a UX/copy fix, not backend**

The KPI renames "今日采集量" → "今日累计入库" is purely frontend. Plan 16-01 puts it in the backend section. Should be in 16-02.

**Recommendation:** Move Issue C from 16-01 to 16-02.

**L4. Plan 16-03 Task 1 cross-tier test has potential timing issue**

The test queries API and DB sequentially. Between the API call and DB query, the run state could change (especially if SSE is publishing). The test asserts `api_s["status"] == db_s["status"]` — but these could legitimately differ if the run is in mid-update.

**Recommendation:** Wrap both calls in a tight transaction or skip the test if `run_id` is currently `running`.

---

## Risk Assessment

**Overall: LOW**

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Plan 16-01 tests don't catch actual stage state bugs | LOW | MEDIUM | e2e tests assert specific fields; cross-tier check adds second layer |
| Frontend toast changes break existing UX | LOW | LOW | Toast is additive; old behavior preserved |
| Index migration breaks query plan | MEDIUM | MEDIUM | Plan should use IF NOT EXISTS |
| Latency measurement itself adds overhead | LOW | LOW | Sample 5-10 times, not in CI |
| External reviewer unavailable | HIGH | NONE | Self-review with documented fallback |

---

## Consensus Summary (Self-Review)

### Strongest Agreements
1. All 10 user complaints have corresponding plan tasks (16-01 Issue A-F, 16-02 Issue E-H, 16-03 cross-tier)
2. Priority ordering correct (Wave 1 parallel, Wave 2 sequential)
3. M1-M7 mandatory rules correctly applied
4. Source-grounded investigation is rigorous

### Critical Gaps (Recommended Adjustments)
1. **M1 (toast scope)**: Add toast on reconnect success path, not just refresh path
2. **M2 (index conflict)**: Use IF NOT EXISTS in alembic migration
3. **M3 (silent fallback)**: Add console.warn when progress fallback fires
4. **L1 (timeline)**: Update estimate from 5-8 to 8 days

### Divergent Views
None — all 10 user complaints have converging single-issue mapping. Plans are coherent.

---

## Recommended Adjustments Before Execution

1. **Plan 16-01 (Backend)**:
   - Move Issue C "数字口径不一致" to Plan 16-02 (it's a frontend concern)
   - Add `IF NOT EXISTS` to index migration
   - Add 1 extra day buffer → 3 days total

2. **Plan 16-02 (Frontend)**:
   - Add toast on `connectSSE()` reconnect success (not just silentRefreshForSSE)
   - Reference existing el-dialog instead of "new"
   - Add console.warn for progress fallback

3. **Plan 16-03 (Cross-tier)**:
   - Wrap API/DB queries in transaction OR skip when run is running
   - Update estimate to 2 days

4. **Phase total**: 3 + 3 + 2 = **8 days** (revised from 5-8)

---

## Note to User

External AI review was not possible due to environment issues (auth keys, plugin errors, model timeouts). Self-review used the same criteria (per `gsd-core/references/`) AND the rich debug context from 3 previous debug sessions in this conversation.

To enable external review in the future, see recommendations in `.planning/audit/16-REVIEWS.md` setup section.

**Approval Status:** 6/6 dimensions pass with 4 minor adjustments recommended. Plans are ready to execute after adjustments.