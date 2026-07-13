---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: 质量加固与架构优化
status: ready_to_plan
last_updated: 2026-07-12T00:00:00.000Z
last_activity: 2026-07-12 -- P0/P1 fixes applied (8 commits), v2.2 roadmap created
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
stopped_at: v2.2 roadmap created — ready for /gsd:plan-phase 12
---

# Project State

## Current Position

Phase: 12 (next)
Plan: Not yet planned
Status: 📋 Ready to plan — v2.2 roadmap defined, 6 phases with 32 requirements
Last activity: 2026-07-12

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

### Blockers

(none)

## Phase Progress

| Phase | Name | Status | Verified |
|-------|------|--------|----------|
| 12 | 安全加固 | 📋 Ready to plan | — |
| 13 | 测试覆盖率提升 | 📋 Ready to plan | — |
| 14 | 大文件拆分与重构 | 📋 Ready to plan | — |
| 15 | 类型安全与代码质量 | 📋 Ready to plan | — |
| 16 | 依赖升级与性能优化 | 📋 Ready to plan | — |
| 17 | 可观测性与开发体验 | 📋 Ready to plan | — |

## Current Baseline (2026-07-12)

| Metric | Value |
|--------|-------|
| vue-tsc errors | **0** |
| eslint errors | **0** |
| ruff check | **All passed** |
| pytest | **529 passed / ~35% coverage** |
| 前端 any | **30+** (production + test) |
| 硬编码颜色 | **0** |
| 运行时Bug | **0** |
| 内存存储 | **0** |
| IDOR vulnerabilities | **0** (fixed in P1) |
| Exception leakage | **0** (fixed in P1) |
| N+1 queries | **0** in list_positions (fixed) |
| Dead code | **0** request.improved.ts (removed) |
| Service HTTP coupling | **0** (domain exceptions) |
