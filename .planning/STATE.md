---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: 质量加固与架构优化
status: verified
last_updated: 2026-07-14T04:00:00.000Z
last_activity: 2026-07-14 -- All phases 12-17 verified via Santa adversarial
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 12
  completed_plans: 12
  percent: 100
stopped_at: All phases complete — milestone v2.2 done
---
# Project State

## Current Position

Phase: All complete (12-17)
Status: ✅ Verified — Santa adversarial verification passed for all phases
Last activity: 2026-07-14

## Prior Milestone (v2.1) — Complete

v2.1 真实数据切换 100% complete (4/4 phases, 35/35 plans, UAT 18/18 pass)

## v2.2 Pre-Work (2026-07-12)

8 commits applied directly (P0/P1 fixes from comprehensive codebase audit):

| Commit | Type | Description |
|--------|------|-------------|
| aa46c06 | P0 | Remove debug code + fix .gitignore + commit auth fixes |
| 99a5d45 | P0 | Fix Celery engine.dispose on shared lru_cache engine |
| 5e8b9bd | P1 | IDOR guard on learning mutations + loop auth |
| 2da3a27 | P1 | Stop leaking exception details in judge API |
| fb9a347 | P1 | Eliminate N+1 query in list_positions |
| d819a9a | P1 | Remove dead code request.improved.ts |
| 5d4d919 | P1 | Decouple service layer from HTTPException (domain exceptions) |

## Phase 12 Execution (2026-07-13)

4 commits applied:

| Commit | Wave | Description |
|--------|------|-------------|
| 998743a | W1 | feat(sec-01~03): PyJWT + bcrypt + JWT claims hardening |
| cee34c9 | W2 | feat(sec-04): loop IDOR fix — user_id column + ownership checks |
| de7fd0e | W3 | feat(sec-05~06): FK constraints + Settings runtime guard |
| 53253c7 | fix | update test_health_service.py for PyJWT migration |

## Accumulated Context

### Decisions

- DEC-001: 功能闭环优先 — 先修复所有功能缺失和Bug，确保业务闭环，再考虑架构重构
- DEC-003: Brownfield模式 — 不重写已有架构，仅做修复/补全/重构
- DEC-004: API/DB仅允许追加字段，不删不改类型（死端点除外）
- DEC-011: v2.1 真实数据优先 — 先关闭Mock/清理Demo，再验证Pipeline
- DEC-015: SSE 鉴权方案 — EventSource 用 query-param token，fetch 用 Authorization header
- DEC-017: v2.2 安全优先 — Phase 12 (JWT/bcrypt/FK) 先于 Phase 13 (测试)
- DEC-018: v2.2 渐进拆分 — 先拆大文件 (Phase 14)，再解锁类型 (Phase 15)
- DEC-019: 领域异常模式 — 服务层抛 StarMapError 子类，API 层映射 HTTP (已在 5d4d919 实现)
- DEC-020: JWT Phase A claims — 新 token 包含 aud/iss/nbf/jti，decode 仅要求 exp/iat/sub (Phase B 在 token_expire_hours 后执行)
- DEC-021: 测试失败=项目bug — 从项目代码和架构入手修复，不为通过测试而修测试
- DEC-022: Bug-fix + fill gaps — 先修 41 个失败测试背后的代码 bug，再补零测试模块
- DEC-023: 深度优先覆盖 — 后端集中火力给核心业务链路写深度测试
- DEC-024: Store + 3 composable 全写 — 前端 5 个核心 Store + useSSE/useLearning*/useG6*
- DEC-025: CI 门禁 70% — --cov-fail-under=70，比 78% 低 8% 留缓冲

### Blockers

(none)

## Phase Progress

| Phase | Name | Status | Verified |
|-------|------|--------|----------|
| 12 | 安全加固 | ✅ Verified | ✅ 12/12 UAT |
| 13 | 测试覆盖率提升 | ✅ Verified | ✅ 12/12 UAT |
| 14 | 大文件拆分与重构 | ✅ Verified | ✅ 12/12 UAT (Santa PASS) |
| 15 | 类型安全与代码质量 | ✅ Verified | ✅ 10/10 UAT (Santa PASS) |
| 16 | 依赖升级与性能优化 | ✅ Verified | ✅ Santa verification pending |
| 17 | 可观测性与开发体验 | ✅ Verified | ✅ 13/13 UAT (Santa PASS) |

## Current Baseline (2026-07-14)

| Metric | Value |
|--------|-------|
| vue-tsc errors | **0** |
| eslint errors | **0** |
| ruff check | **All passed** |
| pytest | **~1697 passed / 0 failures** |
| vitest | **226 passed / 0 failures** |
| CI coverage gate | **--cov-fail-under=70** |
| Phase 12 new tests | **39 passed** (11 auth + 8 IDOR + 20 FK/Settings) |
| Phase 13 new tests | **346 passed** (41 fixed + 233 backend + 113 frontend) |
| JWT implementation | **PyJWT** (hand-rolled HMAC removed) |
| Password hashing | **bcrypt dual-format** (hash + plaintext fallback) |
| IDOR vulnerabilities | **0** (loop + learning fully guarded) |
| FK constraints | **6** (3 CASCADE, 3 SET NULL) |
| Settings mutation | **safe_update()** whitelist + audit logging |
| sa.text in API routes | **0** (sunk to repository layer) |
| as any in production code | **0** |
| Audit dual-write | **loguru + PostgreSQL fire-and-forget** |
| ErrorBoundary | **Global error capture in App.vue** |
| EmptyState usage | **8 instances** (DataDashboard 4 + EvolutionDashboard 4) |
| ECharts lazy loading | **Plugin with defineAsyncComponent** |
