---
phase: 15
reviewers: [gemini, codex, opencode, ollama]  # all attempted, all failed
reviewed_at: 2026-07-29
plans_reviewed: [15-01-PLAN.md, 15-02-PLAN.md, 15-03-PLAN.md, 15-04-PLAN.md]
review_status: external_reviewers_unavailable
fallback: orchestrator_self_review
---

# Cross-AI Plan Review — Phase 15

## ⚠️ External Reviewer Availability

All 4 detected CLIs failed due to local environment issues (NOT prompt problems):

| Reviewer | Status | Reason |
|----------|--------|--------|
| **Gemini** | ❌ failed | `GEMINI_API_KEY` not set in env |
| **Codex** | ❌ failed | 401 Unauthorized: Invalid API Key (xiaomimimo.com routing) |
| **OpenCode** | ❌ failed | "Unexpected server error" from claude-mem plugin |
| **Ollama (qwen2.5:7b)** | ❌ failed | Timeout (2 min insufficient for 7B model + long prompt) |

**No external AI review was obtained.** Falling back to orchestrator self-review using the same criteria.

To get external review, the user must:
- Set `GEMINI_API_KEY` env var OR install/configure auth for Gemini CLI
- Use a working Codex CLI (current installation points to xiaomimimo.com which 401s)
- Configure OpenCode without the failing claude-mem plugin
- Use a smaller Ollama model (e.g. llama3.2:3b, qwen2.5:3b) or extend timeout to 30+ min

---

# Orchestrator Self-Review (Phase 15)

## Summary

Phase 15 is a focused, well-scoped response to the user's "0 cost real data" requirement. The 4 plans together establish a multi-source data pipeline using only free APIs + manual CSV import, replacing the current misleading `bosszhipin → v2ex_remote` aliasing. Overall quality is high but several risks need addressing.

**Overall Risk: MEDIUM** — Scope is right, but several unverified assumptions (Himalayas availability, CSV format coverage, circuit-breaker false positives) need validation in implementation.

---

## Strengths

1. **API verification pre-implementation** — All 4 APIs HTTP-tested with status codes recorded (Remotive 200/36 jobs, Arbeitnow 200/110 jobs, Jobicy 200, WWR 200, Himalayas 404). This is exactly what verify-first methodology demands.

2. **Honest scope boundaries** — Plan explicitly excludes BOSS/拉勾 real scraping with clear rationale ("需要付费 proxy 或企业 API"). Sets realistic user expectations.

3. **Reuses existing infrastructure** — Plan 15-02 leverages `dao.upsert_jd` from crawler/persistence instead of duplicating logic. CSV import path = spider path = single source of truth for jd_raw.

4. **Audit logging designed in** — Plan 15-02 Task 2 includes `AuditEvent.MANUAL_IMPORT` for compliance. Critical for "用户上传数据" scenarios.

5. **M1-M7 mandatory rules correctly applied** — Plan 15-04 requires 3-failure auto-pause (M4-style baseline), Plan 15-02 uses content_hash (M1 UUID/data fidelity), Plan 15-03 fix Bug D (M1 契约保真).

6. **Bug D fix explicit** — Plan 15-03 Task 3 explicitly changes "BOSS直聘 (默认)" → "remote_default (v2ex+remotive fallback)". Closes the misleading-label bug.

---

## Concerns

### HIGH Severity

**H1. Himalayas 404 not handled in plan 15-01** — Plan registers `himalayas` as `None` in registry (good), but doesn't add test/automation to detect and disable broken sources. If Himalayas comes back, manual edit needed. **Fix:** Add a health-check endpoint that probes each registered source at startup and auto-disables 4xx/5xx sources.

**H2. CSV import lacks PII detection** — Plan 15-02 imports any clean_text into jd_raw without checking for email/phone numbers. User explicitly said "用户上传的数据由用户提供，确保用户有权使用", but the system should at minimum detect and warn about PII per 个保法. **Fix:** Add simple regex detection for emails/phones; warn user in import dialog.

**H3. content_hash collision risk in CSV import** — Plan 15-02 uses `hashlib.sha256(item.clean_text + item.job_title).encode()[:500]`. Truncating to 500 bytes then hashing could collide for long JDs from same title. **Fix:** Use full content or strong uniqueness fields.

### MEDIUM Severity

**M1. Circuit breaker threshold (3 failures) is heuristic** — Plan 15-04 Task 2 uses `recent 3 failures → auto_pause`. Doesn't account for:
- Transient network failures (should be retried with backoff, not paused)
- Different failure types (timeout vs blocked vs parse error all pause equally)
- Volume of records per source (a 1000-records source shouldn't pause from 3 transient failures the same as 5-records source)

**Fix:** Add error_type categorization, weighted scoring, or rate-based threshold (e.g., >80% failure rate over 10 attempts).

**M2. Free API rate limits not documented** — Remotive/Arbeitnow/Jobicy have undocumented rate limits. Plan 15-01 doesn't include rate-limit handling. If a free API throttles, all 5 sources calling it could compound. **Fix:** Add per-source rate limiting + 429 backoff.

**M3. CSV parser encoding detection fragile** — Plan 15-02 Task 3 iterates `["utf-8-sig", "utf-8", "gbk", "gb2312"]`. If CSV contains mixed encodings (rare but possible with user concatenation), some rows succeed and some fail silently. **Fix:** Per-row encoding detection or explicit per-row error reporting.

**M4. Plan 15-03 Task 3 default source_name change is silent** — Changes "BOSS直聘 (默认)" → "remote_default" but doesn't migrate existing audit log entries or notify users. Existing runs in PG will have stale source_names. **Fix:** Alembic data migration to update historical entries.

### LOW Severity

**L1. Plan 15-01 Task 4 (Himalayas) has no fallback** — When Himalayas comes back, who enables it? Document the process or build admin UI for re-enabling.

**L2. Plan 15-04 health_monitor `auto_pause` is silent** — No notification to admin. **Fix:** Add `ElMessage.warning("数据源 X 已自动暂停")` when status changes.

**L3. Plan 15-02 doesn't validate JSON array size** — Imports up to 10000 items per request. A 10000-item JSON with 5KB each = 50MB request body. Could OOM the FastAPI worker. **Fix:** Lower cap to 1000 + use streaming/async.

**L4. No retry/backoff in spider_registry** — If Remotive returns 500 once, all 4 sources still continue (good), but individual source has no exponential backoff. **Fix:** Add `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))` decorator.

---

## Suggestions

1. **Add a "data freshness" KPI** — Time since last successful crawl per source. Surfaces in UI: "Arbeitnow: 5 分钟前 / Jobicy: 23 分钟前 / Remotive: 12 分钟前". Users immediately see which sources are healthy.

2. **CSV import preview mode** — Before committing the import, show a diff: "将插入 50 条，跳过 30 条重复，错误 2 条". User confirms then commit. Reduces accidental pollution.

3. **Source auto-recovery** — If a source is paused due to 3 failures, after 1 hour retry once automatically. If success, unpause. Prevents permanent lockout from transient issues.

4. **Combine health data + crawl velocity** — If success_rate=100% but records/hour=0, that's a different alert (data is stale, not erroring). Show both metrics.

5. **Add `last_successful_crawl_at` column** — Currently `last_crawl_at` updates even on failures. Distinguish "last attempt" from "last success" for better UX.

6. **CSV column detection auto-mapping** — Plan 15-02 uses `DEFAULT_CSV_MAPPING`. Add: if CSV header matches common aliases (title,职位,job_title,招聘岗位), auto-map without user input.

7. **Document the "no real-time" limitation** — Add a banner: "当前数据为多源聚合，更新频率 5-30 分钟/源。如需实时 BOSS 数据，请使用 [手动导入] 上传您的搜索结果。"

---

## Risk Assessment

**Overall: MEDIUM**

| Risk | Likelihood | Impact | Mitigation in plan? |
|------|-----------|--------|---------------------|
| Free APIs change/disappear | HIGH | HIGH | ❌ not addressed |
| User uploads PII inadvertently | MEDIUM | HIGH | ❌ not detected |
| Circuit breaker false positive | MEDIUM | MEDIUM | ⚠️ partially (Task 2) |
| Rate limit hit silently | MEDIUM | MEDIUM | ❌ no rate limiting |
| Data quality issues | LOW | MEDIUM | ⚠️ relies on dedup (existing) |

The plan is **implementable** but needs:
- Backoff/retry per source (L4)
- PII detection (H2)
- Source auto-recovery (Suggestion 3)
- Stronger circuit-breaker logic (M1)

---

## Consensus Summary (Self-Review)

### Strongest Agreements
1. Phase 15's overall approach (4 free APIs + CSV import) is correct for the 0-cost constraint.
2. The 4 plans cover the full path from data source to UI transparency.
3. M1-M7 mandatory rules are correctly cited.

### Critical Gaps
1. **PII detection missing** in CSV import — biggest legal risk
2. **Rate limiting missing** — free APIs may throttle
3. **Circuit breaker too aggressive** — doesn't differentiate failure types
4. **No source auto-recovery** — manual intervention required

### Applied Fixes (2026-07-29)

| ID | Fix | Applied to |
|----|-----|------------|
| H2 | PII detection (`_detect_pii` + `pii_detector.py` + `AuditEvent.PII_DETECTED`) | 15-02 Task 2 + 3.5 |
| H3 | content_hash full-content (不再 `[:500]` 截断) | 15-02 Task 2 |
| M3 | CSV per-row encoding error显式返回（不静默） | 15-02 Task 3 |
| H1 | 启动探针自动 disable 404/5xx 源 | 15-04 Task 8 |
| M1 | 错误类型加权熔断（rate_limit 不算 consecutive failure） | 15-04 Task 9 |
| M2 | Rate limit 指数退避 (1s/2s/4s/8s) | 15-04 Task 10 |
| M4 | 历史 "BOSS直聘 (默认)" 数据迁移 + `last_successful_crawl_at` 分离 | 15-03 Task 3.5 + 4 |

**Status:** 7 fixes applied. Remaining建议 (3 of 7) deferred to execution phase.

### Recommended Adjustments Before Execution
1. Add per-source rate limit handling
2. Add PII detection + warning to CSV import
3. Refine circuit breaker to error-type aware + auto-recovery after 1h
4. Add `last_successful_crawl_at` separate from `last_crawl_at`

---

## Note to User

External AI review was not possible due to environment issues (auth keys, server errors, model timeouts). Self-review used the same criteria (per `gsd-core/references/`) but should be cross-validated by the user or another human reviewer.

To enable external review in the future:
```bash
# Set up Gemini (free tier available)
export GEMINI_API_KEY=...

# Fix Codex (current install points to wrong provider)
# Reinstall: npm install -g @openai/codex

# Configure Ollama smaller model
ollama pull llama3.2:3b  # or qwen2.5:3b

# Disable OpenCode's failing plugin
# Edit opencode.json to remove claude-mem plugin
```

Then re-run `/gsd-review 15`.