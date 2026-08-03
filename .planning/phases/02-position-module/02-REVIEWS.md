---
phase: 2
reviewers: [codex]
cycles:
  - cycle: 1
    reviewed_at: 2026-07-28
    plans_reviewed: [.planning/phases/02-position-module/02-01-PLAN.md]
    reviewer_status:
      codex:
        outcome: failed_substituted
        failure_mode: "codex CLI 0.145.0 returned exit 1: `unexpected status 401 Unauthorized: Invalid API Key, url: https://token-plan-cn.xiaomimimo.com/v1/responses` (provider: `mimo-v2.5-pro`, custom endpoint). The configured provider rejected the request; no review text was produced."
        substituted_by: "orchestrator source-grounded pass (Claude Sonnet 4.6, full repo access). Reviewer attribution kept as 'Codex Review (CLI auth failure — substituted by orchestrator)' so the failure mode is auditable and the substituted review is clearly flagged as not produced by an independent AI."
        source_grounding: "Substituted review still followed the source-grounding contract: every concern cites `path/to/file:line` evidence read live from the repository on 2026-07-28."
  - cycle: 3
    reviewed_at: 2026-07-28T23:55
    plans_reviewed: [.planning/phases/02-position-module/02-01-PLAN.md]
    plan_revision_note: "PLAN.md revised in place 2026-07-28 23:17 (51038 bytes, 487 lines). Cycle-3 plan-stage incorporated all 6 Cycle-2 findings (C2-M1, C2-M2, C2-M3, C2-L1, C2-L2, C2-L3) with explicit `关键（C2-X）` callouts and concrete code patterns. Added 'New Symbols / Endpoints' subsection to the 'Artifacts this phase produces' section declaring `mockRouteRef` and `searchDebounceTimer` as new symbols (must be excluded from drift verification)."
    reviewer_status:
      codex:
        outcome: failed_substituted
        failure_mode: "codex CLI 0.145.0 retry on 2026-07-28: identical `401 Unauthorized: Invalid API Key` from `https://token-plan-cn.xiaomimimo.com/v1/responses`. No credential rotation occurred between cycles 1/2/3; the configured Xiaomi Mimico endpoint is still rejecting the request. Per Cycle-1 documented fallback, no Codex-generated content was produced; orchestrator (Claude Sonnet 4.6, full repo access) performed a substituted source-grounded pass against the Cycle-3-revised plan."
        codex_attempt_evidence: "Bash `echo 'ping' | codex exec --ephemeral --skip-git-repo-check -o /tmp/codex-test-cycle3.md - 2>/tmp/codex-test-cycle3.err` (timeout 60s) produced stderr: `OpenAI Codex v0.145.0` header (workdir, model: mimo-v2.5-pro, provider: custom, reasoning effort: xhigh) followed by `ERROR: Reconnecting... 1/5` through `5/5` and `ERROR: unexpected status 401 Unauthorized: Invalid API Key, url: https://token-plan-cn.xiaomimimo.com/v1/responses` (twice). Retry attempt confirmed identical to Cycle-1 and Cycle-2 failure modes."
        substituted_by: "orchestrator source-grounded pass (Cycle-3 review) following same source-grounding contract as Cycles 1 and 2. Plan claims verified against live `path/to/file:line` evidence read on 2026-07-28 (post-23:17 revision). Cycle-2 finding status (FULLY_RESOLVED / PARTIALLY_RESOLVED / NEW) was independently verified, not taken from the planner's claims."
        source_grounding: "Substituted review still followed the source-grounding contract: every Cycle-3 concern cites `path/to/file:line` evidence read live from the repository on 2026-07-28. New artifacts (`mockRouteRef`, `searchDebounceTimer`, `mockFetchPositions`, `mockFetchPositionDetail`, `setRouteParams`, `list_industries`, `IndustriesResponse`, `onIndustryChange`, `loadDetail`) were grep-verified absent from the live source — no drift to exclude."
    convergence_verdict: "CONVERGED — current_high=0, current_actionable=0. All 6 Cycle-2 findings are FULLY RESOLVED in the plan. No new HIGH or actionable MEDIUM concerns emerged in Cycle 3. Plan is ready to execute."
  - cycle: 2
    reviewed_at: 2026-07-28T23:30
    plans_reviewed: [.planning/phases/02-position-module/02-01-PLAN.md]
    plan_revision_note: "PLAN.md revised in place 2026-07-28 22:58 (47006 bytes, 474 lines). Replaces Task 3 'Requirements A–E' design output with direct implementation; re-anchors source analysis to current (post-Phase 13 + post-Phase 23) code state; adds new 'Artifacts this phase produces' section declaring new symbols/endpoints that must be excluded from drift verification."
    reviewer_status:
      codex:
        outcome: failed_substituted
        failure_mode: "codex CLI 0.145.0 retry on 2026-07-28: same `401 Unauthorized: Invalid API Key` from `https://token-plan-cn.xiaomimimo.com/v1/responses`. No credential rotation occurred between cycles; the configured provider endpoint is still rejecting the request. Per Cycle-1 documented fallback, no Codex-generated content was produced; orchestrator (Claude Sonnet 4.6, full repo access) performed a substituted source-grounded pass against the revised plan."
        codex_attempt_evidence: "Bash `echo 'ping' | codex exec --ephemeral --skip-git-repo-check -o /tmp/codex-test.md - 2>/tmp/codex-test.err` produced stderr: `ERROR: Reconnecting... 5/5` + `ERROR: unexpected status 401 Unauthorized: Invalid API Key, url: https://token-plan-cn.xiaomimimo.com/v1/responses`. Retry attempt confirmed identical to Cycle-1 failure mode."
        substituted_by: "orchestrator source-grounded pass (Cycle-2 review) following same source-grounding contract as Cycle-1. Plan claims verified against live `path/to/file:line` evidence read on 2026-07-28."
        source_grounding: "Substituted review still followed the source-grounding contract: every Cycle-2 concern cites `path/to/file:line` evidence read live from the repository on 2026-07-28. Cycle-1 finding status (FULLY_RESOLVED / PARTIALLY_RESOLVED / NEW) was independently verified, not taken from the planner's 'all 13 marked COVERED' claim."
---

# Cross-AI Plan Review — Phase 2 (PositionList + PositionDetail)

> **Reviewer status note.** The configured `--codex` reviewer (codex CLI 0.145.0 with provider `mimo-v2.5-pro`) failed at authentication with `401 Unauthorized: Invalid API Key, url: https://token-plan-cn.xiaomimimo.com/v1/responses`. No Codex-generated review content exists. To preserve the source-grounding contract, the orchestrator (Claude Sonnet 4.6, full repo access) performed a substituted source-grounded pass and is recorded below under "Codex Review (substituted)". Treat its verdict as the **only** plan-level review in this cycle, and weight it conservatively (no independent-AI cross-check).

---

## Codex Review (CLI auth failure — substituted by orchestrator)

### 1. Summary

`02-01-PLAN.md` is largely **out of date**: it characterizes as bugs several behaviors that have already been fixed in the live code (Phase 13 conformance pass + a follow-up Phase 23 admin/include_all pass recorded in `02-VALIDATION.md` and `backend/tests/integration/test_position_conformance.py`). Executing this plan as written would be mostly a no-op for those items and risks regression in two places the plan does *not* address: (a) the search input and industry-chip controls do not trigger `fetchPositions`, so the page silently depends on the *client-side* `filteredPositions` filter the plan describes as redundant; and (b) Neo4j-fallback `PositionNode` construction does not write `review_status`, which admin status badges rely on. The plan's design output (Task 2: Requirements A–E) inherits the same drift — A and B describe already-fixed behavior. Net assessment: **plan should be revised, not executed as written**.

### 2. Strengths

- **Already-implemented invariants are correctly identified as invariants.** `_escape_like` (`backend/app/api/v1/position.py:20-22`), the `search` param `OR`-ing `name` + `industry` in both PG (`position.py:84-90`) and Neo4j (`position.py:332-338`), and the public/admin visibility split (`position.py:91-96`) are flagged as required behavior. The conformance test `backend/tests/integration/test_position_conformance.py:48-83` locks these, which is the right pattern.
- **Threat model is grounded.** T-02-01 / T-02-05 correctly identify LIKE-wildcard escaping and Cypher parameterization as the relevant risks; both mitigations are already in place.
- **Spec of "fixed" Python mapping rule with Chinese labels** (Task 3, Step 2) — the *intent* (PG and Neo4j must produce the same proficiency labels) is right; only the mapping table is wrong.
- **Empty-state and loading-skeleton coverage in test plan** (Task 4, Steps 3–4) targets real gaps and is the highest-value section of the plan.
- **2-of-3 requirements (POS-02, POS-03) are testable in jsdom.** The plan's "shallowMount + complete mock" approach matches the existing 2 spec files' pattern and stays in line with `vitest.config.ts:13`.

### 3. Concerns

#### HIGH

- **H1. Plan describes already-fixed code as bugs — execution will produce mostly no-op commits and risks reverting recent fixes.**
  - *Plan claims:* `fetchPositions()` "params 类型定义和实际传参均未包含 [search/industry]" (Plan L98).
  - *Code reality:* `frontend/src/pages/PositionList.vue:109-137` — `fetchPositions` already builds `params` with `search` and `industry` from `searchQuery.value` and `selectedIndustry.value`; the inline comment at `:55` documents the prior fix.
  - *Plan claims:* PostgreSQL path skills list "缺少 `proficiency` 字段" (Plan L105, L119).
  - *Code reality:* `backend/app/api/v1/position.py:201` — `"proficiency": "精通" if rel.requirement_type == "required" else "了解" if rel.requirement_type == "preferred" else "熟悉"` is present.
  - *Plan claims:* `_escape_like` "必须不被回退" (Setup context 5). The plan's Task 3 does NOT touch `_escape_like` — but the plan's narrative framing as "fix" suggests it might.
  - *Impact:* The plan as written produces no source change for these items. If the executor interprets the plan as "still need to add", they may overwrite correct code. **Plan must be re-grounded against the live source before execution.**

- **H2. Search input and industry-chip clicks do not trigger `fetchPositions`, so removing `filteredPositions` client filter would silently break in-page filtering.**
  - *Evidence:* `frontend/src/pages/PositionList.vue:194-201` — `<el-input v-model="searchQuery" ...>` has no `@input` / `@change` / `@keyup.enter` handler. `PositionList.vue:235-248` — industry `<el-tag>` click sets `selectedIndustry` but does not call `fetchPositions`. The only re-fetch triggers are `onMounted(:181)`, `onPageChange(:158)`, `onStatusFilterChange(:163)`.
  - *Plan claim:* Step 3 (Plan L237) says "若 params 包含 search/industry 则跳过客户端过滤" — implying `filteredPositions` can degenerate to `positions.value`.
  - *Impact:* If the executor implements Step 3 literally, typing in the search box or clicking an industry chip will filter only the currently-loaded page (24 rows). Search results from other pages will be invisible. The user-visible `total` will be the *unfiltered* total, and `filteredPositions.length` will mismatch the pagination widget — exactly the UX bug the plan set out to fix.

- **H3. `industries` computed list is still page-bounded; plan silently retains the limitation.**
  - *Evidence:* `frontend/src/pages/PositionList.vue:49-52` — `industries` derives from `positions.value.map(p => p.industry)`, which is the *current page only*. `pageSize = ref(24)` (`:42`).
  - *Plan claim:* Step 3 (Plan L238) says "保留从 positions.value 提取行业的逻辑... 如果后端未来支持 `/positions/industries` 端点，可后续优化".
  - *Impact:* User on page 3 sees only industries present on page 3; clicking a chip that exists on page 1 will look like a "missing filter". The fix is mechanical (add `/positions/industries` or include all industries in the list response), and the plan explicitly defers it. This is the most user-visible gap.

- **H4. PG `proficiency` mapping in plan (Task 3 Step 2) is inverted from the live code, and would mislabel Neo4j-vs-PG parity if applied.**
  - *Plan claim (L230-232):* `required → 熟悉, preferred → 了解, optional → 了解`.
  - *Code reality:* `position.py:201` — `required → 精通, preferred → 了解, ELSE → 熟悉`. Neo4j path uses `normalize_proficiency(level)` (`graph_serializers.py:198`, `normalize.py:750-760`) which maps `_EXPERT_TERMS → 精通`, `_BEGINNER_TERMS → 了解`, default → 熟悉 — and the Neo4j path never reflects `required` directly; it reflects the `level` value on the relationship.
  - *Impact:* Plan Task 3 Step 2 instructs the executor to "add" `proficiency` with a wrong mapping table. The field already exists with the *correct* mapping (一致 across PG and Neo4j). Re-adding it with the wrong map is a regression.

#### MEDIUM

- **M1. Neo4j-fallback `PositionNode` does not write `review_status`, breaking admin status badge.**
  - *Evidence:* `backend/app/api/v1/position.py:393-401` — `PositionNode(...)` constructed without `review_status=...`. `frontend/src/pages/PositionList.vue:294-302` — admin card shows `<el-tag :type="statusBadgeType(pos.review_status)">` which falls through to `default → 'info'`.
  - *VALIDATION.md already flagged this:* `[OPEN · LOW]` (item 4). The current plan does not mention it.
  - *Impact:* When admin views pages whose PG filtered count = 0 and the Neo4j fallback fires, every card's status badge shows "info"/"已发布" regardless of actual `review_status`. Mitigate by adding `review_status=props.get("review_status")` in the Neo4j `PositionNode(...)` call.

- **M2. `fetchPositionSkills` in `jd.ts:95-97` is dead code (now superseded by `fetchPositionDetail`).**
  - *Evidence:* `frontend/src/stores/jd.ts:95-97` exposes `fetchPositionSkills` which hits `/graph/position/{name}/skills`. `frontend/src/pages/PositionDetail.vue:90` now calls `jdStore.fetchPositionDetail(id, { silent: true })` (a comment at `:80-82` explicitly says "改用列表传入的 id（UUID，路径安全）"). No other call site is reachable via grep; the store still exports it (`:167`).
  - *Impact:* Dead surface area. The route `/graph/position/{name}/skills` may now be unused — verify with a backend grep before deleting, but at minimum the store export should be deprecated to avoid future drift.

- **M3. `fetchToken` race-handling covers only `onMounted`, not route changes.**
  - *Evidence:* `frontend/src/pages/PositionDetail.vue:83-121` — `fetchToken` is incremented inside `onMounted`, which Vue Router does *not* re-run when navigating between `/position/A` and `/position/B` if the route component is reused (it is — both resolve to `name: 'position-detail'` at `frontend/src/router/index.ts:19-20`).
  - *Plan note (L108):* "需要注意当 fetchToken 溢出 ... 实际场景极不可能" — plan acknowledges but doesn't propose a watcher.
  - *Impact:* Navigating from `/position/A` to `/position/B` without unmount shows stale data from `A`. The fix is `@watch(() => route.params.name, fetch)` in PositionDetail.

- **M4. `PositionList.spec.ts` and `PositionDetail.spec.ts` enhancements assume jdStore is mocked, but plan doesn't show how.**
  - *Evidence:* Existing tests `PositionList.spec.ts:9-15` mock only `vue-router` and `@/composables/useAuthBootstrap` (the latter is not even imported by `PositionList.vue` — dead mock). On mount, `PositionList.vue:181` calls `fetchPositions()` which calls `jdStore.fetchPositions` which calls `request.get('/positions', ...)`. jsdom env + axios = real fetch attempt (or network error).
  - *Plan claim (Task 4 Steps 3-4):* "采用 shallowMount + 完整 mock 的策略（与现有测试一致）" — but the existing strategy does NOT mock jdStore.
  - *Impact:* New tests likely fail with axios "Network Error" or unhandled promise rejection. Add explicit `vi.mock('@/stores/jd', () => ({ useJdStore: () => ({ fetchPositions: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 24 }), ... }) }))`.

- **M5. PositionList.vue renders `review_status ?? 'approved'` (`:143`) which masks admin's view of Neo4j-fallback positions.**
  - *Evidence:* `frontend/src/pages/PositionList.vue:138-146` — when backend omits `review_status` (Neo4j fallback, M1 above), frontend defaults it to `'approved'`.
  - *Impact:* Admin sees Neo4j-fallback positions always as "已发布" even when their actual Neo4j status is `'pending_review'`. Couples to M1 — fixing M1 (Neo4j fallback writes `review_status`) also fixes this.

#### LOW

- **L1. Plan's `description of "double encoding" goDetail fix` is reverse-engineered.**
  - *Code reality:* `PositionList.vue:166-170` already uses `router.push('/position/' + id)` with raw UUID. The plan's Step 3 narrative (Plan L240) describes removing `encodeURIComponent` that was never there in this commit. Task is a no-op.
  - *Impact:* None if ignored; wasted executor time if implemented as described.

- **L2. `PROFICIENCY_MAP[s.proficiency] ?? 0.5` fallback (PositionDetail.vue:48) is effectively dead.**
  - *Code reality:* Both PG (`position.py:201`) and Neo4j (`graph_serializers.py:198` → `normalize_proficiency`) always return one of `精通/熟悉/了解` (see `normalize.py:750-760`). `PROFICIENCY_MAP` (`frontend/src/utils/proficiency.ts:2-6`) covers all three.
  - *Impact:* Cosmetic — no functional bug, but dead default may confuse future maintainers.

- **L3. `CATEGORY_LABELS` whitelist (`PositionDetail.vue:53-63`) has 9 entries; backend `SkillRecord.category` allows free-form string.**
  - *Evidence:* `backend/app/models/extraction_models.py:298` — `Mapped[str] = ... default="general"`. Neo4j fallback (`graph_serializers.py:191-193`) handles `category == "Skill"` but doesn't constrain.
  - *Impact:* Unknown categories render as their raw English string via the `?? row.category` fallback (`PositionDetail.vue:252`). Document or constrain.

- **L4. Plan Task 2 design output (Requirements A–E) is bloated for value delivered.**
  - *Observation:* Requirements A (`search/industry 参数传递`) and B (`proficiency 补全`) describe already-fixed behavior. C/D (`empty state`) are cosmetic. E (`错误处理增强`) is the only requirement with clear position-module gap.
  - *Impact:* 5 of 5 requirements produce low ROI as written. Suggest collapsing to: (i) wire search/industry controls to refetch, (ii) `/positions/industries` endpoint, (iii) Neo4j fallback `review_status` writeback (M1).

- **L5. Plan assumes `vi.spyOn(jdStore, 'fetchPositions')` style mocking but doesn't import `useJdStore` directly in tests.**
  - *Pinia nuance:* Tests that use `createPinia() + setActivePinia(pinia)` then `shallowMount` the page need to set the pinia store BEFORE mount; the current tests do this correctly (`:19-22`), so the foundation is fine — just needs an explicit `setActivePinia` + `useJdStore` mock pattern.

- **L6. Plan's `tests pass verification` (Step 5) lacks an ordering between vitest and pytest.**
  - *Why it matters:* Frontend and backend tests are independent, but `conftest.py`/pytest fixtures sometimes expect the DB. `02-VALIDATION.md` shows `test_position_conformance.py:43` overrides `get_neo4j_driver` — that test should not need a live DB. Plan should keep verification commands clean.

### 4. Suggestions

- **S1. Re-anchor the plan to the live source.** Each "fix" in Task 3 Step 2-5 should be re-checked against `position.py` / `PositionList.vue` / `PositionDetail.vue` *before* being marked as an action item. Add a pre-execute diff step: `git diff HEAD -- backend/app/api/v1/position.py frontend/src/pages/PositionList.vue frontend/src/pages/PositionDetail.vue` and reconcile each item.
- **S2. Wire search and industry controls to refetch.** Either add `@input` debounced to `el-input` (search) or trigger `fetchPositions()` in `onSearchQueryChange` / `onIndustryChange`. Remove `filteredPositions` client filter only AFTER the refetch wiring is verified end-to-end (live test). Keep client filter as a safety net until then.
- **S3. Add `GET /positions/industries` endpoint** returning the distinct `industry` set (admin/non-admin variant). Replace the page-bounded `industries` computed in `PositionList.vue:49-52`.
- **S4. Backfill `review_status` in Neo4j fallback `PositionNode(...)`** (M1) — single line fix at `position.py:393-401`.
- **S5. Drop the dead `fetchPositionSkills` store export** after a backend grep confirms `/graph/position/{name}/skills` has no other callers.
- **S6. Add a route watcher to `PositionDetail.vue`** (`@watch(() => route.params.name, refetch)`) so the `fetchToken` mechanism actually serves in-component navigation.
- **S7. Plan's `Task 4` test enhancements need explicit jdStore mocking**. Show the mock pattern once and reuse. Without it, new tests will fail at `onMounted → fetchPositions → axios`.
- **S8. Reconcile PG and Neo4j `proficiency` mapping tables.** Live code already does it correctly (PG: `精通/了解/熟悉` by `requirement_type`; Neo4j: `normalize_proficiency(level)`). Plan should *describe* the existing mapping rather than prescribe a new one — preventing the H4 regression.
- **S9. Reduce `docs/archive/position-optimization-design.md` requirements to the 3 with real ROI** (search/industry refetch trigger, `/positions/industries` endpoint, Neo4j `review_status` writeback).

### 5. Risk Assessment — **HIGH**

Justification:
- The plan's Task 3 is **net-negative** if executed as written: most items are already-fixed (no-op commits), one item (H4 proficiency mapping table) is inverted and would regress the live code, and the items it *should* address (H2 search refetch trigger, H3 industries endpoint, M1 Neo4j review_status) are absent or only acknowledged.
- The plan's Task 4 (tests) is the highest-value section, but it inherits test-infrastructure gaps (M4, L5) that will cause flaky test runs if not addressed before the new tests are added.
- Threat model and conformance invariants are sound — the regression risk is concentrated in the "fix" tasks, not in security.

If the plan is revised to address H1, H2, H3, H4 before execution, the risk drops to MEDIUM (and Task 4 can ship independently as test-only work).

---

## Verification Coverage

| Plan claim | Verified against | Result |
|---|---|---|
| Plan L98: `fetchPositions` lacks search/industry params | `frontend/src/pages/PositionList.vue:109-137` | **CONTRADICTED** — already wired (H1) |
| Plan L105/L119: PG path lacks `proficiency` | `backend/app/api/v1/position.py:201` | **CONTRADICTED** — present (H1) |
| Plan L100: `industries` from current page only | `frontend/src/pages/PositionList.vue:49-52` | **CONFIRMED** — still bounded (H3) |
| Plan L107: `SkillRadar` v-if="data.length >= 3" | `frontend/src/components/SkillRadar.vue:94` | **CONFIRMED** — present |
| Plan L112: `_escape_like` escapes `%` and `_` | `backend/app/api/v1/position.py:20-22` | **CONFIRMED** — present and tested at `test_position_conformance.py:48-50` |
| Plan L230-232: proficiency mapping `required→熟悉` | `position.py:201` (actual: `required→精通`) | **CONTRADICTED** (H4) |
| Plan L240: `goDetail` double-encode | `frontend/src/pages/PositionList.vue:166-170` | **CONTRADICTED** — no encode present (L1) |
| Plan L256: post-fix lint passes | ruff + eslint | NOT VERIFIED (no edit proposed that survives H1-H4 fixes) |
| Plan L88: skeleton `:rows="0"` | `frontend/src/pages/PositionDetail.vue:130-145` | **CONFIRMED** |
| Plan L82-90 (P-F2): `search` OR `name`+`industry` | `position.py:84-90` and `position.py:110-117` | **CONFIRMED** — both count and page stmt |
| Plan L91-96 (P-F1): public defaults to `approved` | `position.py:91-96` | **CONFIRMED** |
| Plan L98 (status filter admin-only): include_all only when admin | `frontend/src/pages/PositionList.vue:128-136` | **CONFIRMED** — `if (isAdmin.value)` |
| VALIDATION.md [OPEN·LOW] Neo4j fallback `review_status` omitted | `position.py:393-401` | **CONFIRMED** — still open (M1) |
| VALIDATION.md [OPEN·MEDIUM] PositionList/PositionDetail test gaps | `PositionList.spec.ts`, `PositionDetail.spec.ts` | **CONFIRMED** — only 3 thin tests total |

Total plan claims checked: **15**. Contradicted: **3** (H1×2, H4, L1 counted once). Confirmed: **11**. Plan lines cited without source verification: lines describing archive-doc-generation (`docs/archive/position-source-analysis.md`, `docs/archive/position-optimization-design.md`) which are documentation artifacts and not verifiable against code.

---

## Consensus Summary

Single reviewer (substituted). No independent cross-check performed due to codex CLI auth failure.

### Agreed Strengths

(Single reviewer — "agreed" trivially.)

- Threat model is grounded and `_escape_like` / P-F1 / P-F2 invariants are correctly identified as load-bearing.
- Plan correctly notes that `_escape_like` must not regress.
- Plan's Task 4 (test enhancements) targets real thin-coverage gaps (VALIDATION.md [OPEN·MEDIUM]).

### Agreed Concerns (Single-reviewer)

All HIGH and MEDIUM concerns above, ranked:

1. **H1 — plan describes already-fixed code as bugs (HIGH)**
2. **H2 — search/industry inputs do not trigger refetch; removing client filter would silently break UX (HIGH)**
3. **H3 — industries list is page-bounded and the plan defers the fix (HIGH)**
4. **H4 — proficiency mapping table in Task 3 Step 2 is inverted vs live code (HIGH)**
5. **M1 — Neo4j fallback `PositionNode` omits `review_status` (MEDIUM, pre-existing)**
6. **M4 — new tests need explicit jdStore mocking or they'll fail at axios (MEDIUM)**

### Divergent Views

None (single reviewer).

---

> **Auditor's note for next /gsd-plan-phase cycle**: Treat the HIGH findings above as blocking. A revised `02-01-PLAN.md` should re-anchor Task 3 to the *current* `position.py` / `PositionList.vue` / `PositionDetail.vue` (post-Phase 13 / Phase 23 fixes), delete the misleading "fix" steps that are now no-ops, and add the missing wiring (search/industry → refetch; `/positions/industries` endpoint; Neo4j `review_status` writeback). The conformance regression test `backend/tests/integration/test_position_conformance.py` should remain green throughout — it already locks P-F1/P-F2 and the wildcards escape.

---

# Cross-AI Plan Review — Phase 2 (PositionList + PositionDetail) — Cycle 2

> **Cycle-2 review.** The planner was instructed to either incorporate each Cycle-1 finding into PLAN.md or explicitly defer/reject with rationale. This cycle independently verifies whether the plan now actually delivers the changes — not just claims them. Codex CLI auth still failing (verified, see frontmatter); substituted source-grounded Claude pass performed against the live code on 2026-07-28.

---

## Codex Review (CLI auth failure — substituted by orchestrator)

### 1. Summary

The revised `02-01-PLAN.md` (revised 2026-07-28 22:58) has **substantially addressed all 13 Cycle-1 findings** (4 HIGH + 5 MEDIUM + 4 LOW). Each Cycle-1 HIGH has a corresponding Task-2 or Task-3 fix with `// fix:` / `# fix:` comment anchors, an explicit file:line target, and acceptance_criteria that an executor can verify against. Phase 13 / Phase 23 already-fixed items are correctly reclassified as `invariant` rather than bugs (H1/H4 retired). New artifacts (`GET /api/v1/positions/industries`, `IndustriesResponse`, `list_industries`, `onIndustryChange`, `loadDetail`, `setRouteParams`, `mockFetchPositions`, `mockFetchPositionDetail`) are declared in the "Artifacts this phase produces" section and correctly excluded from drift verification. Three MEDIUM and three LOW concerns remain — all are **execution-level ambiguities** in how `vi.mock` factories, module-scope timer refs, reactive route mocks, and SQL-string assertions should be wired, rather than missing acceptance_criteria. Net assessment: **plan is ready to execute; no blocking findings remain**.

### 2. Cycle-1 finding disposition (independently verified against live source)

| Cycle-1 ID | Cycle-1 severity | Cycle-2 status | Evidence |
|---|---|---|---|
| **H1** — plan describes already-fixed code as bugs | HIGH | **FULLY RESOLVED** | Plan Task 1 acceptance_criteria explicitly requires "Phase 13/23 already-fixed items ... are listed as `invariant` with a back-reference to `test_position_conformance.py`, NOT as bugs." Task 1 read_first list points to current `position.py:84-90`/`PositionList.vue:111-125`. The plan §"第 2 层 — Review cycle 新发现的真实缺陷" enumerates the *open* bugs only. |
| **H2** — search/industry inputs do not trigger refetch | HIGH | **FULLY RESOLVED** | Task 2 H2 specifies (a) `watch(searchQuery, () => { ... setTimeout(() => { page.value=1; fetchPositions() }, 300) })` (line 211-215 of plan), (b) `onIndustryChange()` helper reset page=1 + refetch, (c) wire to both industry `el-tag` clicks (line 217-218). Acceptance criteria §H2 line 271-272 are explicit. Live verification: `PositionList.vue:194-201` indeed lacks `@input` handler; industry tag at `:235-247` indeed lacks refetch — bug confirmed still present, plan fix targets both sites. |
| **H3** — `industries` page-bounded; plan silently retains limitation | HIGH | **FULLY RESOLVED** | Task 2 H3 specifies new `GET /api/v1/positions/industries` endpoint with P-F1/P-F2/`_escape_like` invariant reuse, registered *before* `/{position_id}` to avoid path collision. New `IndustriesResponse` Pydantic model + `list_industries` async function declared in artifacts section (excluded from drift). Live verification: `grep -n "list_industries\|/industries\|IndustriesResponse" backend/app/api/v1/position.py` returned no matches — endpoint does NOT yet exist, plan correctly adds it. |
| **H4** — proficiency mapping table in plan is inverted | HIGH | **FULLY RESOLVED** (retired) | Cycle-1 H4 was about Cycle-1 plan's Task 3 prescribing a *wrong* mapping. Cycle-2 plan's Task 1 §"PG `proficiency` 映射" (line 122) explicitly marks the live mapping as `invariant`, and Task 2 §"不做的" (line 256-263) explicitly excludes "不修改 PG `proficiency` 已正确的 required→精通 映射（position.py:201）". No regression risk. |
| **M1** — Neo4j fallback `PositionNode` omits `review_status` | MEDIUM | **FULLY RESOLVED** | Task 2 M1 (line 205-208) specifies `PositionNode(... review_status=props.get("review_status"))` aligned with PG `getattr(r, "review_status", None)`. Acceptance criterion line 270-271 verifies via grep. Live verification: `position.py:393-401` `PositionNode(...)` does NOT include `review_status=...` — bug confirmed still present. |
| **M2** — `fetchPositionSkills` dead code | MEDIUM | **FULLY RESOLVED** | Task 2 M2 (line 238-241) specifies JSDoc `@deprecated since 2026-07-28` on `jd.ts:93-96`; explicitly preserves backend route for E2E/contract tests. Live verification: grep across `frontend/src/` confirms `jdStore.fetchPositionSkills` has zero callers (only `matchStore.fetchPositionSkills` is used at `MatchDiagnosis.vue:137`). |
| **M3** — `PositionDetail.vue` `fetchToken` only covers `onMounted` | MEDIUM | **FULLY RESOLVED** | Task 2 M3 (line 229-236) specifies `watch(() => route.params.name, (newName) => { if (newName) loadDetail(String(newName)) })` and extracts `loadDetail(id: string)` from `onMounted`, preserving the existing `myToken !== fetchToken` guard. Live verification: `PositionDetail.vue:6` `import { ref, computed, onMounted } from 'vue'` — `watch` not yet imported. Router `name: 'position-detail'` (`router/index.ts:20`) confirms component reuse across `/position/A` → `/position/B`. |
| **M4** — `PositionList.spec.ts`/`PositionDetail.spec.ts` lack jdStore mock | MEDIUM | **FULLY RESOLVED** | Task 3 M4 (line 317-322) specifies `vi.mock('@/stores/jd', () => ({ useJdStore: () => ({ fetchPositions: mockFetchPositions, ... }) }))` with explicit mock factory; references `learningPlan.test.ts:7-20` and `AuditLog.spec.ts:9-17` patterns. Removal of dead `useAuthBootstrap` mock also specified (line 318, 332). Live verification: `PositionList.vue` and `PositionDetail.vue` do NOT import `useAuthBootstrap` — dead mock confirmed. |
| **M5** — `PositionList.vue:143` masks Neo4j null with `?? 'approved'` | MEDIUM | **FULLY RESOLVED** | Task 2 M5 (line 224-227) specifies replacement `?? 'approved'` → `?? null` + admin `statusLabel` default-branch returning `'未分类'`. Live verification: `PositionList.vue:143` `review_status: p.review_status ?? 'approved'` still present. |
| **L1** — `goDetail` double-encode | LOW | **FULLY RESOLVED** (no-op confirmed) | Plan Task 1 §"第 5 层 — 已归档项" (line 147-148) explicitly cites L1 as `no-op with file:line evidence`. Live verification: `PositionList.vue:169` is `router.push('/position/' + id)` — no encode/decode. |
| **L2** — `PROFICIENCY_MAP[s.proficiency] ?? 0.5` dead branch | LOW | **FULLY RESOLVED** | Task 2 L2 (line 243-245) specifies removal. Live verification: `PositionDetail.vue:48` still has `?? 0.5`; `PROFICIENCY_MAP` (`frontend/src/utils/proficiency.ts:1-6`) covers all 3 PG/Neo4j return values `{精通, 熟悉, 了解}`. |
| **L3** — Unknown category falls back to raw English | LOW | **FULLY RESOLVED** | Task 2 L3 (line 247-250) specifies `{{ CATEGORY_LABELS[row.category] ?? '其他' }}`. Live verification: `PositionDetail.vue:252` still falls back to raw `row.category`. |
| **L4** — Task 2 design output (Requirements A–E) bloated | LOW | **FULLY RESOLVED** | Plan's `objective` (line 56-67) explicitly states "直接补齐当前真实代码仍存在的差距" — design output collapsed into Task 2/3 implementation. |
| **L5** — vi.spyOn + setActivePinia pattern | LOW | **FULLY RESOLVED** | Task 3 M4 explicitly uses `setActivePinia(createPinia())` + `vi.mock('@/stores/jd', ...)` (matches `learningPlan.test.ts:7-20` reference). |
| **L6** — verification ordering between vitest and pytest | LOW | **FULLY RESOLVED** | `<verification>` section line 412-422 enumerates 8 ordered checks (ruff → pytest conformance → pytest industries → vitest → Playwright) without coupling. |

**Cycle-1 finding count summary:** 13/13 fully resolved or retired (no-op). 0 partially resolved. 0 new HIGHs raised in Cycle-2.

### 3. Cycle-2 NEW findings (against revised plan)

#### MEDIUM

- **C2-M1. Task 2 H2 `let searchDebounceTimer` placement is ambiguous between module-scope and per-instance closure.**
  - *Plan text (line 213-214):* "在 `onMounted` 之前定义 `let searchDebounceTimer: ReturnType<typeof setTimeout> | undefined`"
  - *Issue:* With `<script setup>`, top-level `let` becomes module-scoped across *all* PositionList instances (e.g., when both `/positions` and any preview route mount PositionList). For a SPA where only one PositionList exists at a time, the leak is benign, but the plan should specify `ref<NodeJS.Timeout | undefined>(undefined)` for clarity, or scope the timer inside the `watch` callback. Currently the plan's wording suggests module-scope `let`, which is correct-but-ambiguous.
  - *Mitigation:* Change `let searchDebounceTimer` → `const searchDebounceTimer = ref<ReturnType<typeof setTimeout>>()` and reference `.value` in `clearTimeout(searchDebounceTimer.value)` / `searchDebounceTimer.value = setTimeout(...)`.

- **C2-M2. Task 3 `vi.mock('@/stores/jd', ...)` factory references module-scope `mockFetchPositions` before its declaration site.**
  - *Plan text (line 319-320):* "在文件顶部新增 `const mockFetchPositions = vi.fn()...`" then "新增 `vi.mock('@/stores/jd', () => ({ useJdStore: () => ({ fetchPositions: mockFetchPositions, ... }) }))`"
  - *Issue:* Vitest hoists `vi.mock` calls but the factory body is evaluated lazily. The plan's wording places the `vi.mock` *after* the `const mockFetchPositions` declaration, which is the correct order — but the `beforeEach` line "在 `beforeEach` 中 `mockFetchPositions.mockClear()`" requires that the mock is captured at factory creation, not at call time. The pattern works but is fragile if executor reorders lines.
  - *Mitigation:* Add a one-line note: "`vi.mock` 工厂通过闭包捕获模块顶层 `const mockFetchPositions`；不要把工厂改成箭头函数 inline（hoist 会失效）。"

- **C2-M3. Task 3 `test_industries_escapes_like_wildcards` asserts raw SQL string, which is fragile across SQLAlchemy versions.**
  - *Plan text (line 349):* "通过请求 `?search=a%b` 断言 SQL 中含 `a\\%b`（占位断言，避免 SQL 字符串转义噪声）"
  - *Issue:* SQLAlchemy render of `ilike(pattern, escape="\\")` produces `lower(position_record.name) ILIKE %(param_1)s ESCAPE '\\'` where `%{param_1}s` is a bindparam, not the literal pattern. The current `test_position_conformance.py:59` works around this by checking for keywords (`" or "`, `"industry"`, `"name"`) rather than pattern literals. The plan's `test_industries_escapes_like_wildcards` test would need to capture `session.execute.call_args_list[1].kwargs["params"]` (the bindparams dict) and assert `params["search"] == "a\\%b"`.
  - *Mitigation:* Rewrite assertion to inspect `session.execute.call_args_list[i].kwargs['params']` instead of the SQL string.

#### LOW

- **C2-L1. Task 3 `setRouteParams` mutates a `let routeRef` — Vue's `watch()` does NOT react to plain-object mutations.**
  - *Plan text (line 335):* "mount helper 中 `useRoute` mock 改为可变：`vi.mock('vue-router', () => ({ useRoute: () => routeRef, ... }))` 且 `let routeRef = { params: { name: 'Backend-Engineer' }, ... }`，并 `export function setRouteParams(p) { routeRef = { ...routeRef, params: { ...routeRef.params, ...p } } }`"
  - *Issue:* `watch(() => route.params.name, ...)` in `PositionDetail.vue` reads `route.params.name` *through* `useRoute()`. If the mock returns the same `routeRef` object reference each time, `watch` will fire on the initial setup (already covered by `onMounted`) but NOT on `setRouteParams({ name: 'Frontend-Engineer' })` mutating the inner `params.name` — Vue's reactivity tracks Proxy traps, not raw object mutation. The test "route param change refetches (M3)" will silently fail.
  - *Mitigation:* Replace `let routeRef` with `const routeRef = ref({ params: {...}, ... })` and unwrap via `routeRef.value` in the mock factory. `setRouteParams` mutates `routeRef.value.params.name`. Alternatively use Vue Router's `useRoute()` real route and `router.push()` in tests, but that requires more setup.

- **C2-L2. Plan's Task 3 lacks an ordering constraint between `mockFetchPositions.mockClear()` and the `setRouteParams` watcher fires.**
  - *Issue:* The `route param change refetches (M3)` test asserts `mockFetchPositionDetail` is called *at least 2 times* across mount + route change. If the test uses `mockResolvedValueOnce` for the first mount and `mockResolvedValueOnce` for the route-change, but a third fire happens during `flushPromises` (due to `watch` re-firing on intermediate `routeRef.value` mutations), the third call resolves to the second `mockResolvedValueOnce` and the test may assert incorrect data.
  - *Mitigation:* Use `mockResolvedValue` (not `Once`) with explicit `vi.mocked(...).mockImplementation` to deterministically return different payloads based on call argument.

- **C2-L3. Plan's Task 1 acceptance criterion `grep -cE 'invariant|H2|H3|M1|M2|M3|M4|M5|L2|L3'` will be brittle if docs/archive/position-source-analysis.md uses different separators or anchor formats.**
  - *Plan text (line 160):* `grep -cE 'invariant|H2|H3|M1|M2|M3|M4|M5|L2|L3' docs/archive/position-source-analysis.md`
  - *Issue:* The grep counts lines matching the regex, which produces a positive number as long as those tokens appear anywhere — but if the file is *missing* any of them, the count is still positive (1 missing among 10 = count 9). The acceptance criterion should be `grep -c '^.*invariant'` per-section, or split into 10 separate grep commands. Currently the verification is a soft signal, not a hard gate.
  - *Mitigation:* Replace with explicit per-token grep (e.g., `test "$(grep -c 'invariant' file)" -ge 5 && test "$(grep -cE 'H2|H3|M1|M2|M3|M4|M5|L2|L3' file)" -ge 9`) or use a structured markdown lint.

### 4. Cycle-2 strengths (additions beyond Cycle-1)

- **The "Artifacts this phase produces" section is well-structured.** New symbols are grouped under "Modified", "New", "New Symbols / Endpoints". This correctly signals to drift verifiers (and future reviewers) which identifiers are expected to be **absent** from the live source pre-execution.
- **Task 1 ↔ Task 2/3 traceability is explicit.** Each Cycle-1 finding is named in Task 2 (e.g., "**H2 — 前端控件触发 refetch**", line 210) with a comment anchor (`# fix: H2 ...`). The acceptance_criteria use the same identifier tokens, so the executor can verify by `git grep "fix: H2"` after execution.
- **Threat model updated for new endpoint and new fixes.** T-02-06 (`list_industries` search parameter inherits `_escape_like` + P-F2), T-02-08 (Neo4j fallback `review_status` writeback for admin status badge), T-02-09 (route param stale data — mitigated by watcher). The mapping from Cycle-1 findings to threat IDs is direct and verifiable.
- **Regression-lock invariant is explicit.** "既有 Phase 13 契约回归测试 `backend/tests/integration/test_position_conformance.py` 仍 4 passed（P-F1 公开 approved / P-F2 search OR name+industry / `_escape_like`）" appears in must_haves, verification, and success_criteria. Triple-locked.
- **The "不做的（明确排除）" block (Task 2 line 256-263) is a good surgical-change discipline signal** — it prevents the executor from re-doing already-fixed items (H1/H4/L1 retirements) and accidentally regressing them.

### 5. Cycle-2 risk assessment — **LOW**

Justification:
- All 4 Cycle-1 HIGHs are FULLY RESOLVED or correctly retired.
- All 5 Cycle-1 MEDIUMs are FULLY RESOLVED with concrete acceptance_criteria.
- All 4 Cycle-1 LOWs are FULLY RESOLVED.
- New Cycle-2 findings (3 MEDIUM, 3 LOW) are execution-level implementation details (Vue reactivity, vitest hoisting, SQL assertion fragility) — none of them block the phase from achieving its goals.
- The plan's risk surface is concentrated in Task 3 (test infrastructure), where vi.mock + watch + module-scope-let interact in non-obvious ways. The M3/C2-L1 interaction is the highest-likelihood-to-fail test case.

If Task 3's mock setup is implemented per the plan's text (with `let routeRef` and inline `vi.mock` factory) without addressing C2-L1, the `route param change refetches (M3)` test will silently pass without actually exercising the watcher. **Recommend the executor address C2-L1 before writing the test**, then add the others as iterative improvements.

---

## Cycle-2 verification coverage (independently verified)

| Plan claim (Cycle-2 revised) | Verified against live | Result |
|---|---|---|
| PLAN §"PG `proficiency` 映射" marks required→精通 as invariant | `backend/app/api/v1/position.py:201` | **CONFIRMED** — Plan correctly identifies current mapping as invariant. |
| PLAN §"`goDetail` 已直接 `router.push('/position/' + id)`" | `frontend/src/pages/PositionList.vue:169` | **CONFIRMED** — No encode/decode present; plan correctly marks L1 as no-op. |
| PLAN §"搜索/行业筛选控件不触发 refetch" (H2) | `frontend/src/pages/PositionList.vue:194-201` (el-input has no `@input`), `:235-247` (industry tag click sets `selectedIndustry` only) | **CONFIRMED** — Both sites present, plan fix targets both. |
| PLAN §"`industries` 仅当前页" (H3) | `frontend/src/pages/PositionList.vue:49-52` (computed from `positions.value`) | **CONFIRMED** — Bug present; plan adds `/positions/industries` endpoint. |
| PLAN §"Neo4j fallback `PositionNode` 缺 `review_status`" (M1) | `backend/app/api/v1/position.py:393-401` (`PositionNode(...)` constructor call has no `review_status=...`) | **CONFIRMED** — Bug present; plan fix targets exactly this site. |
| PLAN §"`fetchPositionSkills` 已被 `fetchPositionDetail` 取代" (M2) | `grep -rn "fetchPositionSkills" frontend/src/` shows only `jd.ts:95` definition (no callers); `matchStore.fetchPositionSkills` at `frontend/src/stores/match.ts:88` is a *different* store | **CONFIRMED** — jd.ts version is dead code; plan correctly marks `@deprecated`. |
| PLAN §"`PositionDetail.vue` 的 `fetchToken` 只覆盖 `onMounted`" (M3) | `frontend/src/pages/PositionDetail.vue:6` (no `watch` in import), `:85-121` (only `onMounted` calls fetch) | **CONFIRMED** — Bug present; plan fix adds `watch(() => route.params.name, refetch)`. |
| PLAN §"tests lack `vi.mock('@/stores/jd')`" (M4) | `frontend/src/pages/__tests__/PositionList.spec.ts` has only `vi.mock('vue-router')` and `vi.mock('@/composables/useAuthBootstrap')` (dead mock — neither file imports `useAuthBootstrap`) | **CONFIRMED** — Bug present; plan adds `vi.mock('@/stores/jd', ...)`. |
| PLAN §"`?? 'approved'` 掩盖 Neo4j null" (M5) | `frontend/src/pages/PositionList.vue:143` `review_status: p.review_status ?? 'approved'` | **CONFIRMED** — Bug present; plan fix replaces with `?? null` + statusLabel null branch. |
| PLAN §"`PROFICIENCY_MAP[s.proficiency] ?? 0.5` 是死分支" (L2) | `frontend/src/pages/PositionDetail.vue:48`, `frontend/src/utils/proficiency.ts:1-6` | **CONFIRMED** — Dead branch present; PG/Neo4j always returns 精通/熟悉/了解 (all 3 keys in map). |
| PLAN §"未知 category 走 `:252` `?? row.category` 显示原始英文" (L3) | `frontend/src/pages/PositionDetail.vue:252` `{{ CATEGORY_LABELS[row.category] ?? row.category }}` | **CONFIRMED** — Bug present; plan fix replaces with `?? '其他'`. |
| PLAN §"`test_position_conformance.py` 4 passed 锁定 P-F1/P-F2" | `backend/tests/integration/test_position_conformance.py:48-83` | **CONFIRMED** — 4 tests (`test_escape_like_escapes_wildcards`, `test_public_search_ors_industry_and_defaults_approved`, `test_admin_include_all_drops_approved_filter`, `test_public_no_search_still_filters_approved`). |
| PLAN §"`test_position_industries_endpoint.py` 不存在 — 新建" | `ls backend/tests/integration/` (existing files: `test_extraction_api.py`, `test_graph_projector_neo4j.py`, `test_graph_projector_pg.py`, `test_pipeline_e2e.py`, `test_position_conformance.py`) | **CONFIRMED** — File absent; plan correctly adds it. |
| PLAN §"Artifacts this phase produces" — new symbols list | grep across `backend/app/api/v1/position.py`, `frontend/src/pages/PositionList.vue`, `frontend/src/pages/PositionDetail.vue`, `frontend/src/stores/jd.ts`, `frontend/src/pages/__tests__/PositionDetail.spec.ts` for `list_industries`, `IndustriesResponse`, `onIndustryChange`, `loadDetail`, `setRouteParams`, `mockFetchPositions`, `mockFetchPositionDetail` | **CONFIRMED** — None present in current source (as expected — they are new). Drift verification correctly excludes them. |

Total Cycle-2 plan claims checked: **14**. All **CONFIRMED**. No contradictions against the live source. No new HIGHs raised.

---

## Cycle-2 consensus summary

Single reviewer (substituted; Codex CLI auth still failing on retry — same Xiaomi Mimico endpoint 401, identical failure mode to Cycle-1).

### Agreed Strengths (Single-reviewer — "agreed" trivially)

- Plan correctly re-anchors to post-Phase 13 / post-Phase 23 source state; explicitly labels fixed items as `invariant` rather than re-flagging them as bugs.
- All 4 Cycle-1 HIGHs are FULLY RESOLVED or correctly retired (H4 no-op, L1 no-op).
- All 5 Cycle-1 MEDIUMs have concrete `// fix:` / `# fix:` comment anchors, file:line targets, and acceptance_criteria verifications.
- All 4 Cycle-1 LOWs are FULLY RESOLVED.
- Threat model updated to cover the new `/positions/industries` endpoint and route-watcher behavior.
- Regression-lock invariant (`test_position_conformance.py` 4 passed) is triple-locked across must_haves / verification / success_criteria.

### Agreed Concerns (Single-reviewer)

Cycle-2 new findings, ranked by execution-risk:

1. **C2-L1 (LOW → likely to fail test)** — `let routeRef` mock factory won't trigger `watch()` reactivity; "route param change refetches (M3)" test will silently pass without exercising the watcher. **Should be fixed before Task 3 test for M3 is written.**
2. **C2-M3 (MEDIUM)** — `test_industries_escapes_like_wildcards` raw-SQL-string assertion will fail under SQLAlchemy parameter binding. **Should be rewritten to inspect bindparams dict.**
3. **C2-M2 (MEDIUM)** — `vi.mock` factory closure capture ordering is fragile; pattern works but is brittle to executor line reordering. **Should add a one-line note about hoist ordering.**
4. **C2-M1 (MEDIUM)** — `let searchDebounceTimer` module-scope ambiguity; should use `ref()` for clarity.
5. **C2-L2 (LOW)** — `mockResolvedValueOnce` + intermediate `flushPromises` may over-fire; use `mockImplementation` for determinism.
6. **C2-L3 (LOW)** — Task 1 verification `grep -cE` is a soft signal; replace with per-token greps.

### Divergent Views

None (single reviewer, no cross-AI check possible due to codex CLI failure persisting).

---

> **Auditor's note for /gsd-execute-phase 2 cycle**: The plan is ready to execute. Cycle-1 HIGHs are resolved. Recommended execution order to minimize iteration: (1) Task 1 (rewrite `position-source-analysis.md`) — pure docs, no risk. (2) Task 2 backend H3 + M1 first (single-file diff, easy to verify with `test_position_conformance.py` still 4 passed). (3) Task 2 frontend M2 + L2 + L3 (low-risk single-line changes). (4) Task 2 frontend M5 + statusLabel null branch (touches admin badge display). (5) Task 2 frontend H2 + M3 (Vue reactivity wiring — test incrementally). (6) Task 3 test infrastructure: address C2-L1 (use `ref()` for routeRef) BEFORE writing the M3 test, then address C2-M3 when writing the industries-endpoint SQL assertion. (7) Task 3 final: full `pytest` + `vitest` + Playwright verification per the `<verification>` block.

---

# Cross-AI Plan Review — Phase 2 (PositionList + PositionDetail) — Cycle 3

> **Cycle-3 review (final cycle).** The plan-stage was instructed to incorporate all 6 Cycle-2 findings (C2-M1, C2-M2, C2-M3, C2-L1, C2-L2, C2-L3) into PLAN.md. This cycle verifies whether the plan has **converged** — i.e., `current_high == 0` AND `current_actionable == 0` per the CYCLE_SUMMARY contract. Codex CLI auth still failing on the third retry (verified, see frontmatter); substituted source-grounded Claude pass performed against the Cycle-3-revised plan on 2026-07-28.

---

## Codex Review (CLI auth failure — substituted by orchestrator)

### 1. Summary

The Cycle-3-revised `02-01-PLAN.md` (revised 2026-07-28 23:17, 487 lines, 51038 bytes) has **fully addressed all 6 Cycle-2 findings** with explicit `关键（C2-X）` callouts, concrete code patterns, and verification artifacts. Each Cycle-2 finding has a corresponding line in the plan that (a) names the finding verbatim, (b) explains the underlying mechanism (Vue reactivity, SQLAlchemy param binding, Vitest hoisting), and (c) provides a concrete code snippet the executor can implement. The new "New Symbols / Endpoints" subsection in "Artifacts this phase produces" correctly declares 9 new symbols (including `mockRouteRef` and `searchDebounceTimer` per the user's note) and all were grep-verified absent from the live source — no drift to exclude. Three new Cycle-3 cosmetic observations were noted, but they are all already incorporated into PLAN.md as part of the existing C2 fixes or are sub-actionable (cosmetic). **Net assessment: plan is CONVERGED; current_high=0, current_actionable=0.**

### 2. Cycle-2 finding disposition (independently verified against live source)

| Cycle-2 ID | Cycle-2 severity | Cycle-3 status | Evidence (lines = PLAN.md) |
|---|---|---|---|
| **C2-M1** — `let searchDebounceTimer` module-scope ambiguity | MEDIUM | **FULLY RESOLVED** | L213: `**关键（C2-M1）**：用 \`const searchDebounceTimer = ref<ReturnType<typeof setTimeout> \| undefined>(undefined)\` 替代模块级 \`let\``. L214 properly references `.value` in both `clearTimeout` and `setTimeout` calls. Artifacts section L486 declares `const searchDebounceTimer` as a new symbol. Live verification: `grep -n "searchDebounceTimer" frontend/src/pages/PositionList.vue` returns no matches — symbol correctly absent from current source. |
| **C2-M2** — `vi.mock` factory closure capture ordering | MEDIUM | **FULLY RESOLVED** | L335: `**关键（C2-M2）**：\`vi.mock\` 工厂通过闭包捕获模块顶层 \`const mockFetchPositionDetail\`；**不要把工厂改成 inline 箭头函数** 或把 \`const\` 提到 \`vi.mock\` 之后 —— Vitest 会 hoist \`vi.mock\` 到模块顶部，但 \`const\` 声明不会 hoist，TDZ 报错。`. The note correctly explains the Vitest hoisting semantics and the factory's lazy evaluation. |
| **C2-M3** — `test_industries_escapes_like_wildcards` raw SQL string assertion | MEDIUM | **FULLY RESOLVED** | L360: `**关键（C2-M3）** —— SQLAlchemy 渲染 \`ilike(pattern, escape="\\\\")\` 后参数走 bindparam（\`%(param_1)s\`），不在 SQL 字符串里，所以不能断言字面量 \`a\\\\%b\`。改为捕获 \`mock_session.execute.call_args_list[i]\` 的 \`kwargs['params']\` 字典，断言 \`params['search'] == "a\\\\%b"\``. Pattern correctly references `test_position_conformance.py:48-50` keyword-assertion precedent as a stylistic guide. |
| **C2-L1** — `let routeRef` mock factory won't trigger Vue `watch()` reactivity | LOW | **FULLY RESOLVED** | L336-337: explicit `**关键（C2-L1）**` note plus `const routeRef = ref({...})` declaration. L337 explains the mechanism: `\`watch\` 追踪 Proxy traps，不追踪 raw object mutation；若 \`setRouteParams\` 直接改 \`routeRef.params.name\` 而 \`routeRef\` 是普通对象，watcher 不触发，**M3 用例会 silently pass**`. The mitigation is the whole-object replacement via `routeRef.value = { ...routeRef.value, params: { ...routeRef.value.params, ...p } }`. Artifacts section L485 declares `mockRouteRef` as new symbol. Live verification: `grep -n "mockRouteRef\|setRouteParams" frontend/src/pages/__tests__/PositionDetail.spec.ts` returns no matches — symbol correctly absent. |
| **C2-L2** — `mockResolvedValueOnce` + `flushPromises` intermediate-state over-fire | LOW | **FULLY RESOLVED** | L344-350: `**关键（C2-L2）**：用 \`mockImplementation\` 按入参返回不同 payload，避免 \`mockResolvedValueOnce\` 链 + \`flushPromises\` 中间态导致的第三次 fire 拿到第二次的 payload 而断言错位`. Includes a concrete code snippet (L345-349) showing `mockImplementation((id: string) => { if (id === 'Frontend-Engineer') return Promise.resolve({...}) ... })` — the exact pattern the Cycle-2 mitigation called for. |
| **C2-L3** — `grep -cE 'invariant\|H2\|H3\|...'` soft-signal verification | LOW | **FULLY RESOLVED** | L160: Verification script was split into per-token grep checks: `INV=$(grep -c 'invariant' ...)` separately from `H2=$(grep -c 'H2' ...)`, `H3=$(grep -c 'H3' ...)`, ..., `L3=$(grep -c 'L3' ...)`, followed by `test "$INV" -ge 5 && test "$H2" -ge 1 && ... && test "$L3" -ge 1`. Each finding has a hard-gate per-token check, eliminating the soft-signal failure mode. |

**Cycle-2 finding count summary:** 6/6 fully resolved. 0 partially resolved. 0 new HIGHs raised in Cycle-3.

### 3. Cycle-3 verification of new artifacts (drift exclusion)

The user's Cycle-3 note called out two specific new symbols (`mockRouteRef`, `searchDebounceTimer`) that must be excluded from drift verification. New artifacts section (L477-486) declares 9 new symbols/endpoints. All were grep-verified against the live source:

| Symbol | Declared in PLAN | Found in live source | Status |
|---|---|---|---|
| `GET /api/v1/positions/industries` | L478 | NOT present (`grep -n '/api/v1/positions/industries' backend/app/api/v1/position.py` → empty) | New — correctly excluded from drift |
| `class IndustriesResponse(BaseModel)` | L478 | NOT present | New — correctly excluded |
| `async def list_industries(...)` | L479 | NOT present | New — correctly excluded |
| `fetchPositionSkills` JSDoc `@deprecated` | L480 | NOT present (no `@deprecated` annotation in `jd.ts`) | New annotation — correctly excluded |
| `function onIndustryChange()` | L481 | NOT present | New — correctly excluded |
| `function loadDetail(id: string)` | L482 | NOT present | New — correctly excluded |
| `export function setRouteParams(p)` | L483 | NOT present | New — correctly excluded |
| `mockFetchPositions`, `mockFetchPositionDetail` | L484 | NOT present | New — correctly excluded |
| `mockRouteRef` (Vue `ref({...})` object) | L485 | NOT present | New — correctly excluded |
| `const searchDebounceTimer = ref<...>(undefined)` | L486 | NOT present | New — correctly excluded |

**Drift verification — 100% pass.** All declared new symbols are absent from the live source, which is the expected state pre-execution. No drift to remediate.

### 4. Cycle-3 verification of pre-existing bugs (M1, M3, M5) — plan targets aligned

| Bug | Pre-existing in source | Plan fix target | Alignment |
|---|---|---|---|
| **M1** — Neo4j fallback `PositionNode` lacks `review_status` | `backend/app/api/v1/position.py:393-401` `PositionNode(position_id=..., name=..., name_cn=..., industry=..., description=..., skills_required=..., discovered_at=None)` — no `review_status=` kwarg | Plan L205-208: `在 \`PositionNode(...)\` 构造里添加 \`review_status=props.get("review_status")\``. Plan L466: `backend/app/api/v1/position.py — adds \`review_status=props.get("review_status")\` to \`_list_positions_neo4j\` \`PositionNode(...)\` (Task 2 M1)`. | ALIGNED ✓ |
| **M3** — `PositionDetail.vue` `fetchToken` only covers `onMounted` | `frontend/src/pages/PositionDetail.vue:6` `import { ref, computed, onMounted } from 'vue'` — no `watch`. Router `frontend/src/router/index.ts:19-20` confirms `name: 'position-detail'` is reused across `/position/A` ↔ `/position/B`. | Plan L229-236: `watch(() => route.params.name, (newName) => { if (newName) loadDetail(String(newName)) })` extracted from `onMounted`. | ALIGNED ✓ |
| **M5** — `PositionList.vue:142` `review_status ?? 'approved'` masks Neo4j null | `frontend/src/pages/PositionList.vue:142` `review_status: p.review_status ?? 'approved'` — confirmed present | Plan L225-227: `改为 \`review_status: p.review_status ?? null\`; 在 \`statusLabel\` 函数中追加 default 分支处理 null ... 当 \`status\` 为 null 时返回 \`'未分类'\``. | ALIGNED ✓ |

All pre-existing bugs that the plan claims to fix are still present in source, and the plan's fix targets align with the actual code locations. No silent regressions possible.

### 5. Cycle-3 cosmetic observations (sub-actionable, informational only)

These observations are NOT counted as actionable MEDIUM/LOW because they are either (a) already incorporated into PLAN.md via the C2 fix set, or (b) are below the /gsd-execute-phase visibility threshold (cosmetic, no execution-blocking risk).

- **OBS-3-1 (informational).** Plan L211 note "`Element Plus \`el-input\` 不原生支持 \`debounce\`" — correct technical detail. Element Plus `el-input` does not have a `debounce` prop; the `watch + setTimeout` pattern is the idiomatic alternative. No plan change needed.

- **OBS-3-2 (informational).** Plan L345-349 `mockImplementation` example uses positional `id` parameter. The acceptance criterion on L351 asserts `mockFetchPositionDetail.mock.calls[1][0] === 'Frontend-Engineer'`, which checks the first positional argument. Implementation matches assertion. No plan change needed.

- **OBS-3-3 (informational).** Plan L336 export of `setRouteParams` is at module scope (test file). Executor should be aware that `setRouteParams` is only callable from within the same test file (not exported from `__tests__/PositionDetail.spec.ts` via the public API). The plan's wording on L336 ("`export function setRouteParams`") is correctly `export` within the module — fine for test utilities. No plan change needed.

### 6. Cycle-3 strengths (additions beyond Cycles 1 and 2)

- **Explicit `关键（C2-X）` callouts make the Cycle-2 fix traceability auditable.** Each of the 6 Cycle-2 findings has a named inline marker in the plan (`关键（C2-M1）`, `关键（C2-M2）`, `关键（C2-M3）`, `关键（C2-L1）`, `关键（C2-L2）`). A future reviewer or executor can grep PLAN.md for `关键（C2-` to enumerate every mitigation site.

- **"New Symbols / Endpoints" subsection is a structural improvement.** Previously the "Artifacts this phase produces" section only listed "Modified" and "New" files. The Cycle-3 revision adds a "New Symbols / Endpoints" subsection (L477-486) grouping all 9 new identifiers in a single block. This is exactly the right escalation for artifacts that don't have a file (e.g., `mockRouteRef` is a Vue `ref()` object inside a test file; `searchDebounceTimer` is a `<script setup>`-local const inside a Vue component — neither has a "file" they live in alone).

- **Cycle-2 findings converted into PLAN-executable code patterns.** Every Cycle-2 finding that was originally raised as an "execution-level ambiguity" (Vue reactivity, vitest hoisting, SQLAlchemy param binding) is now expressed in PLAN.md as a concrete code snippet the executor can copy-paste. The risk of Cycle-2 findings being "claimed COVERED but actually addressed as no-ops" is now zero — the code is in the plan.

- **Defense-in-depth on the M1/M5 chain.** The Neo4j fallback `review_status` writeback (M1) is now paired with the frontend `?? 'approved'` removal (M5) in the same Task 2 sub-task, with explicit cross-references in both the threat model (T-02-08) and the artifact declarations (L466, L468). If M1 fix is applied but M5 is missed, the admin status badge regression is still present — so coupling the two in the plan prevents that failure mode.

- **Cycle-3 drift verification is exhaustive.** 10 new symbols were grep-verified against the live source. 0 drift. The plan's artifact declarations are now machine-checkable: any reviewer (or CI) can run `grep -nE 'list_industries|IndustriesResponse|onIndustryChange|loadDetail|setRouteParams|mockFetchPositions|mockFetchPositionDetail|mockRouteRef|searchDebounceTimer'` against `backend/app/api/v1/position.py` and `frontend/src/pages/` and expect zero matches. The plan's "Artifacts this phase produces" section is now self-verifying.

### 7. Cycle-3 risk assessment — **LOW**

Justification:
- All 6 Cycle-2 findings are FULLY RESOLVED with concrete code patterns in PLAN.md.
- No new HIGH or actionable MEDIUM concerns emerged in Cycle 3.
- 3 cosmetic observations are sub-actionable (informational only, no execution-blocking risk).
- All 3 pre-existing bugs (M1, M3, M5) still present in source and correctly targeted by the plan.
- All 10 new artifacts correctly absent from live source (drift free).
- The CYCLE_SUMMARY contract `current_high == 0 AND current_actionable == 0` is satisfied.

If the plan is executed per the `<verification>` block (L421-434), the residual risk is concentrated in **Task 3 test infrastructure** (where vi.mock + watch + module-scope-let interact), but the C2-L1 and C2-M1 mitigations are now in the plan, so the highest-likelihood-to-fail test cases (`route param change refetches (M3)`, `search input triggers fetchPositions`) have their reactivity prerequisites satisfied.

---

## Cycle-3 verification coverage (independently verified)

| Cycle-3 plan claim | Verified against live | Result |
|---|---|---|
| `**关键（C2-M1）**` mitigation: `const searchDebounceTimer = ref<...>` | `frontend/src/pages/PositionList.vue` — `grep -n "searchDebounceTimer"` returns no matches (new symbol correctly absent) | **CONFIRMED** — symbol is new, plan correctly implements it via `ref()` |
| `**关键（C2-M2）**` mitigation: closure capture from module-scope `const mockFetchPositionDetail` | `frontend/src/pages/__tests__/PositionDetail.spec.ts:1-40` — read pattern matches `learningPlan.test.ts:7-20` reference | **CONFIRMED** — no current code conflicts with the proposed pattern |
| `**关键（C2-M3）**` mitigation: bindparams dict inspection `params['search'] == "a\\%b"` | `backend/tests/integration/test_position_conformance.py:48-50` — existing keyword-only assertion pattern referenced | **CONFIRMED** — the bindparams-dict approach is the correct SQLAlchemy 2.x pattern |
| `**关键（C2-L1）**` mitigation: `const routeRef = ref({...})` + whole-object replacement | `frontend/src/pages/PositionDetail.spec.ts:1-40` — current `useRoute` mock returns a plain object literal | **CONFIRMED** — plain-object mutation would not trigger Vue `watch`; `ref()` wrap is required |
| `**关键（C2-L2）**` mitigation: `mockImplementation` per-id routing | Plan L344-350 includes the exact code snippet | **CONFIRMED** — pattern is correct |
| Cycle-3 grep verification split into per-token hard gates | Plan L160 — 9 individual `grep -c` checks with `test "$X" -ge N` gates | **CONFIRMED** — soft-signal failure mode eliminated |
| M1 fix targets `position.py:393-401` `PositionNode(...)` constructor | `backend/app/api/v1/position.py:393-401` — `PositionNode(position_id=..., name=..., name_cn=..., industry=..., description=..., skills_required=..., discovered_at=None)` — no `review_status=` kwarg | **CONFIRMED** — bug present, plan fix targets exactly this site |
| M3 fix targets `PositionDetail.vue:6` import + adds `watch` | `frontend/src/pages/PositionDetail.vue:6` — `import { ref, computed, onMounted } from 'vue'` — no `watch` import | **CONFIRMED** — bug present, plan fix adds `watch` |
| M5 fix targets `PositionList.vue:142` `?? 'approved'` | `frontend/src/pages/PositionList.vue:142` — `review_status: p.review_status ?? 'approved'` | **CONFIRMED** — bug present, plan fix replaces with `?? null` |
| Cycle-3 new artifact declarations match plan text | `grep -nE 'list_industries|IndustriesResponse|onIndustryChange|loadDetail|setRouteParams|mockFetchPositions|mockFetchPositionDetail|mockRouteRef|searchDebounceTimer' backend/app/api/v1/position.py frontend/src/pages/` — no matches | **CONFIRMED** — all 10 declared new symbols are absent from live source (drift free) |

Total Cycle-3 plan claims checked: **10**. All **CONFIRMED**. No contradictions against the live source. **No new HIGHs or actionable MEDIUMs raised.**

---

## Cycle-3 consensus summary

Single reviewer (substituted; Codex CLI auth still failing on third retry — same Xiaomi Mimico endpoint 401, identical failure mode to Cycles 1 and 2).

### Agreed Strengths (Single-reviewer — "agreed" trivially)

- All 6 Cycle-2 findings are FULLY RESOLVED with concrete code patterns in PLAN.md.
- The "New Symbols / Endpoints" subsection is a structural improvement that makes drift verification machine-checkable.
- Defense-in-depth on M1/M5 coupling is correctly designed.
- All 3 pre-existing bugs (M1, M3, M5) still present in source and correctly targeted by the plan.
- 0 drift on 10 declared new symbols.

### Agreed Concerns (Single-reviewer)

**None.** The 3 cosmetic observations (OBS-3-1, OBS-3-2, OBS-3-3) are sub-actionable (informational only, no execution-blocking risk). They are not counted in the CYCLE_SUMMARY because:
- OBS-3-1 (Element Plus `el-input` debounce note) — already incorporated into PLAN L211 as a one-line remark.
- OBS-3-2 (mockImplementation positional arg check) — already aligned via PLAN L351 assertion.
- OBS-3-3 (export of `setRouteParams`) — already correctly described as `export function` at module scope.

### Divergent Views

None (single reviewer, no cross-AI check possible due to codex CLI failure persisting across cycles 1/2/3).

---

## Cycle-3 CYCLE_SUMMARY

```
CYCLE_SUMMARY: current_high=0 current_actionable=0
```

The plan has **CONVERGED**. All 6 Cycle-2 findings are FULLY RESOLVED. No new HIGH or actionable MEDIUM concerns emerged in Cycle 3. The plan is ready to execute per the existing `<verification>` block (L421-434).

---

> **Auditor's final note for /gsd-execute-phase 2 cycle**: The plan is CONVERGED after 3 cycles (Cycle 1: 13 findings raised; Cycle 2: 13 resolved, 6 new raised; Cycle 3: 6 resolved, 0 new). Execute per the recommended ordering from Cycle 2 (Task 1 docs → Task 2 backend H3+M1 → Task 2 frontend M2+L2+L3 → Task 2 M5+H2+M3 → Task 3 test infrastructure with C2-L1 and C2-M3 mitigations applied FIRST → final verification). The `mockRouteRef` and `searchDebounceTimer` symbols declared in "New Symbols / Endpoints" are correctly excluded from drift verification — these are net-new identifiers that the executor will introduce.