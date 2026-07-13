# Roadmap: StarMap v2.2 — 质量加固与架构优化

**Created:** 2026-07-12
**Milestone:** v2.2 — 质量加固与架构优化
**Prerequisite:** v2.1 complete (100%, 4/4 phases done)
**Total phases:** 6
**Total requirements:** 32

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 12 | 安全加固 | JWT/密码哈希升级 + loop IDOR 完整修复 + ForeignKey 约束 | SEC-01~06 (6) | PyJWT+bcrypt 替换手写 JWT、loop_results 有 user_id、FK 约束生效 |
| 13 | 测试覆盖率提升 | 后端 35%→60% + 前端核心组件/Store 测试 | TEST-01~06 (6) | pytest cov ≥60%、核心 Store 有测试、composable 有测试 |
| 14 | 大文件拆分与重构 | LoopDemo/Graph3D 拆分 + Store 拆分 + composable 提取 | REFACTOR-01~06 (6) | 无 >800 行组件、learning store 拆分、G6 逻辑复用 |
| 15 | 类型安全与代码质量 | mypy 解锁 + `as any` 消除 + pre-commit + eslint strict | QUALITY-01~05 (5) | mypy 核心 0 error、`as any` <10、pre-commit 生效 |
| 16 | 依赖升级与性能优化 | 后端/前端依赖升级 + ChromaDB 批量查询 + 复合索引 | PERF-01~05 (5) | FastAPI 0.139、Redis 8、Vite 8、N+1 消除 |
| 17 | 可观测性与 DX | 审计日志持久化 + 结构化日志 + 错误边界 + 开发体验 | DX-01~04 (4) | 审计写 DB、ErrorBoundary 组件、统一 logger |

**Coverage:** 100% (32/32 requirements mapped across 6 phases)

---

## Phase 12: 安全加固

**Goal:** 将手写 JWT 替换为 PyJWT + bcrypt，为 loop_results 添加 user_id 实现完整 IDOR 修复，添加 ForeignKey 约束保证引用完整性。

**Requirements:**
- SEC-01 — PyJWT 替换手写 HMAC+base64 JWT 实现
- SEC-02 — bcrypt 密码哈希替换明文比较
- SEC-03 — JWT 声明完善：aud/iss/nbf + 时钟偏移容忍
- SEC-04 — loop_results 表添加 user_id 字段 + 迁移 + IDOR 校验
- SEC-05 — 所有模型关联字段添加 ForeignKey 约束 + 新迁移
- SEC-06 — Settings 运行时修改防护（pipeline config 端点）

**Wave dependency:**
- Wave 1 (no deps) — SEC-01 + SEC-02 + SEC-03 parallel (JWT + bcrypt + claims)
- Wave 2 (blocked on Wave 1) — SEC-04 depends on SEC-01 (user_id needs auth context)
- Wave 3 (blocked on Wave 2) — SEC-05 + SEC-06 parallel (FK constraints + settings guard)

**Success criteria:**
1. `auth.py` 使用 `PyJWT.encode/decode`，无手写 HMAC
2. 密码比较使用 `bcrypt.checkpw()`，`AUTH_USERS` 存储 bcrypt hash
3. JWT 包含 `aud`, `iss`, `nbf` 声明，`leeway=30s` 时钟偏移
4. `loop_results` 表有 `user_id` 列，loop 端点验证 `run.user_id == current_user`
5. `PositionSkillRelation.plan_id`, `LearningProgress.plan_id` 等有 ForeignKey 约束
6. `PUT /pipeline/config` 不直接修改 settings 单例

**Key files:**
- `backend/app/api/v1/auth.py` — JWT 实现
- `backend/app/config.py` — 密码验证
- `backend/app/dependencies.py` — token 解码
- `backend/alembic/versions/009_*.py` — 新迁移 (loop user_id + FK)
- `backend/app/models/pipeline_models.py` — LoopResult 添加 user_id
- `backend/app/api/v1/loop.py` — IDOR 校验
- `backend/app/api/v1/pipeline/routes.py` — settings 防护

**Recommended GSD agents:**
- `gsd-phase-researcher` — 研究 PyJWT 最佳实践和 bcrypt 迁移路径
- `gsd-planner` — 拆分 3 wave 执行计划
- `gsd-executor` — 原子提交每个 SEC 修复
- `gsd-verifier` — 验证 JWT 签名、bcrypt 哈希、FK 约束

---

## Phase 13: 测试覆盖率提升

**Goal:** 后端覆盖率从 35% 提升到 60%（CI 门禁），前端核心 Store 和组件添加单元测试。

**Requirements:**
- TEST-01 — 后端 4 个零测试模块添加测试 (evolution, learning, pipeline, loop)
- TEST-02 — 后端 API 端点 auth guard 测试补全
- TEST-03 — 后端服务层单元测试 (graph_service, match_service, judge_service)
- TEST-04 — 前端核心 Store 测试 (learning, pipeline, loop, dashboard, evolution)
- TEST-05 — 前端核心 composable 测试 (useSSE, useLearning*, useG6*)
- TEST-06 — CI 覆盖率门禁验证 (pytest --cov-fail-under=60)

**Wave dependency:**
- Wave 1 (no deps) — TEST-01 + TEST-02 + TEST-03 parallel (后端)
- Wave 2 (no deps) — TEST-04 + TEST-05 parallel (前端)
- Wave 3 (blocked on Wave 1+2) — TEST-06 (CI gate verification)

**Success criteria:**
1. `pytest --cov` 报告 ≥60% 覆盖率
2. evolution, learning, pipeline, loop 模块各有 ≥5 个测试
3. 所有 API 端点有 auth guard 测试 (401/403)
4. learning, pipeline, loop, dashboard, evolution store 有测试
5. useSSE, useLearningActions, useG6 composable 有测试
6. CI `pytest --cov-fail-under=60` 通过

**Key files:**
- `backend/tests/unit/test_evolution_*.py` — new
- `backend/tests/unit/test_learning_*.py` — new
- `backend/tests/unit/test_pipeline_*.py` — new
- `backend/tests/unit/test_loop_*.py` — new
- `frontend/src/stores/__tests__/learning.test.ts` — new
- `frontend/src/stores/__tests__/pipeline.test.ts` — new
- `frontend/src/stores/__tests__/loop.test.ts` — new
- `frontend/src/composables/__tests__/` — new directory

**Recommended GSD agents:**
- `gsd-add-tests` — 自动生成测试骨架
- `gsd-executor` — 逐模块提交测试
- `gsd-nyquist-auditor` — 验证覆盖率缺口

---

## Phase 14: 大文件拆分与重构

**Goal:** 将超大组件和 Store 拆分为可维护的子模块，提取共享 composable 消除代码重复。

**Requirements:**
- REFACTOR-01 — LoopDemo.vue (1677行) 拆为 6 子组件 + useLoopGraph composable
- REFACTOR-02 — Graph3D.vue (1018行) 提取 useNodeThreeObject + useGlowTexture + useCameraPresets
- REFACTOR-02b — Graph2D.vue (656行) 提取 useDomainLayer + usePositionLayer + useDetailLayer
- REFACTOR-03 — learning.ts store 拆为 learningPlan + learningRecommendation + learningAnalytics
- REFACTOR-04 — pipeline.ts store 拆为 pipelineRun + pipelineConfig
- REFACTOR-05 — 提取 useAsyncAction composable (统一 loading/error 模式)
- REFACTOR-06 — 提取 useExport composable (JSON/CSV 导出逻辑复用)

**Wave dependency:**
- Wave 1 (no deps) — REFACTOR-01 + REFACTOR-02 + REFACTOR-02b parallel (组件拆分)
- Wave 2 (blocked on Wave 1) — REFACTOR-03 + REFACTOR-04 parallel (Store 拆分)
- Wave 3 (blocked on Wave 2) — REFACTOR-05 + REFACTOR-06 parallel (composable 提取)

**Success criteria:**
1. 无 Vue 组件超过 800 行
2. LoopDemo.vue < 400 行，逻辑在子组件和 composable 中
3. Graph3D.vue < 400 行，Three.js 对象构建在 composable 中
4. learning store 拆为 3 个独立 store，各 < 200 行
5. pipeline store 拆为 2 个独立 store
6. useAsyncAction 统一 loading/error，所有 store 使用

**Key files:**
- `frontend/src/pages/LoopDemo.vue` — 拆分
- `frontend/src/components/loop/` — new (LoopStepInput, LoopStepSkills, etc.)
- `frontend/src/composables/useLoopGraph.ts` — new
- `frontend/src/components/Graph3D.vue` — 拆分
- `frontend/src/composables/useNodeThreeObject.ts` — new
- `frontend/src/stores/learningPlan.ts` — new
- `frontend/src/stores/learningRecommendation.ts` — new
- `frontend/src/stores/pipelineRun.ts` — new
- `frontend/src/composables/useAsyncAction.ts` — new

**Recommended GSD agents:**
- `gsd-pattern-mapper` — 分析现有模式，映射新文件到最近类比
- `gsd-planner` — 设计拆分策略和依赖关系
- `gsd-executor` — 逐文件拆分提交
- `gsd-code-reviewer` — 审查拆分后代码质量

---

## Phase 15: 类型安全与代码质量

**Goal:** 解锁 mypy 核心模块类型检查，消除前端 `as any` 断言，添加 pre-commit hooks。

**Requirements:**
- QUALITY-01 — mypy 解锁：matching, graph_service, match_service, celery_app (12 模块)
- QUALITY-02 — 前端 `as any` 消除：30+ 处替换为具体类型 (优先生产代码)
- QUALITY-03 — pre-commit hooks：ruff + eslint + vue-tsc 门禁
- QUALITY-04 — eslint strict：@typescript-eslint/no-explicit-any 改为 warn
- QUALITY-05 — 原始 SQL 下沉：extract.py/match.py 中 sa.text() 移至 repository 层

**Wave dependency:**
- Wave 1 (no deps) — QUALITY-01 + QUALITY-05 parallel (后端类型 + SQL 下沉)
- Wave 2 (no deps) — QUALITY-02 + QUALITY-04 parallel (前端类型)
- Wave 3 (blocked on Wave 1+2) — QUALITY-03 (pre-commit，依赖所有检查通过)

**Success criteria:**
1. mypy 核心 4 模块 `ignore_errors=true` 移除，0 error
2. 前端生产代码 `as any` < 10 处（仅库边界）
3. `.pre-commit-config.yaml` 包含 ruff, eslint, vue-tsc
4. `@typescript-eslint/no-explicit-any` 为 warn，新代码有类型
5. API 路由层无 `sa.text()` 调用

**Key files:**
- `backend/pyproject.toml` — mypy 配置
- `backend/mypy.ini` — disable_error_code 移除
- `frontend/src/stores/loop.ts` — StepResult.data 类型
- `frontend/src/api/client.ts` — runMatch body 类型
- `frontend/src/pages/LoopDemo.vue` — G6 node/edge 类型
- `.pre-commit-config.yaml` — new
- `backend/app/repositories/` — new (SQL 下沉目标)

**Recommended GSD agents:**
- `gsd-code-reviewer` — 审查类型安全改进
- `gsd-executor` — 逐模块提交类型修复
- `code-simplifier` — 简化类型断言

---

## Phase 16: 依赖升级与性能优化

**Goal:** 升级过时依赖，优化 ChromaDB 批量查询，添加数据库复合索引。

**Requirements:**
- PERF-01 — 后端依赖升级：FastAPI 0.139, Redis 8, Neo4j 6, Celery 5.6
- PERF-02 — 前端依赖升级：Vite 8, Vitest 4, Pinia 3, ECharts 6
- PERF-03 — ChromaDB 批量查询替代逐技能查询 (scorer.py)
- PERF-04 — 数据库复合索引 (plan_id+skill_id, skill_name+window_start)
- PERF-05 — Session 提交一致性修复 (get_db_session auto commit/rollback)

**Wave dependency:**
- Wave 1 (no deps) — PERF-01 + PERF-02 parallel (依赖升级)
- Wave 2 (no deps) — PERF-03 + PERF-04 + PERF-05 parallel (性能优化)

**Success criteria:**
1. FastAPI ≥0.139, Redis ≥8, Neo4j ≥6, Celery ≥5.6
2. Vite ≥8, Vitest ≥4, Pinia ≥3
3. scorer.py 单次 ChromaDB 查询替代 N 次循环
4. 复合索引在 alembic 迁移中创建
5. `get_db_session` yield 后自动 commit/rollback

**Key files:**
- `backend/pyproject.toml` — 依赖版本
- `frontend/package.json` — 依赖版本
- `backend/app/core/matching/scorer.py` — ChromaDB 查询
- `backend/alembic/versions/010_*.py` — 复合索引迁移
- `backend/app/db/session.py` — Session 生命周期

**Recommended GSD agents:**
- `gsd-phase-researcher` — 研究依赖 breaking changes
- `gsd-executor` — 逐依赖升级提交
- `codspeed-optimize` — 性能基准测试

---

## Phase 17: 可观测性与开发体验

**Goal:** 审计日志持久化到数据库，添加前端 ErrorBoundary，统一日志格式，改善开发体验。

**Requirements:**
- DX-01 — 审计日志持久化：audit.py 写 DB 替代仅写文件
- DX-02 — 前端 ErrorBoundary 组件 + 全局错误捕获
- DX-03 — 前端 EmptyState/SkeletonCard 共享组件
- DX-04 — ECharts 懒加载插件注册 (替代每页 eager import)

**Wave dependency:**
- Wave 1 (no deps) — DX-01 + DX-02 parallel (后端审计 + 前端错误边界)
- Wave 2 (no deps) — DX-03 + DX-04 parallel (共享组件 + 懒加载)

**Success criteria:**
1. 审计事件写入 PostgreSQL `audit_events` 表
2. Vue `onErrorCaptured` 全局错误边界，页面不白屏
3. EmptyState 组件在 8+ 页面复用
4. ECharts 组件通过插件懒加载，首屏 bundle 减小

**Key files:**
- `backend/app/utils/audit.py` — 写 DB
- `backend/app/models/audit_models.py` — new (AuditEvent)
- `frontend/src/components/ErrorBoundary.vue` — new
- `frontend/src/components/EmptyState.vue` — new
- `frontend/src/plugins/echarts.ts` — new (懒加载插件)

**Recommended GSD agents:**
- `gsd-planner` — 设计审计表和 ErrorBoundary API
- `gsd-executor` — 实现并提交
- `gsd-verifier` — 验证错误边界和审计持久化

---

## ▶ Execution Order

```
Phase 12 (安全加固)        → 2-3 天  → /gsd:plan-phase 12 → /gsd:execute-phase 12
Phase 13 (测试覆盖率)      → 2-3 天  → /gsd:plan-phase 13 → /gsd:execute-phase 13
Phase 14 (大文件拆分)      → 2-3 天  → /gsd:plan-phase 14 → /gsd:execute-phase 14
Phase 15 (类型安全)        → 1-2 天  → /gsd:plan-phase 15 → /gsd:execute-phase 15
Phase 16 (依赖升级)        → 1-2 天  → /gsd:plan-phase 16 → /gsd:execute-phase 16
Phase 17 (可观测性)        → 1-2 天  → /gsd:plan-phase 17 → /gsd:execute-phase 17
```

**Total estimated:** 9-15 天

**Phase dependencies:**
- Phase 12 独立（安全优先）
- Phase 13 独立（可与 12 并行，但建议串行避免冲突）
- Phase 14 建议在 13 之后（拆分后需补测试）
- Phase 15 建议在 14 之后（拆分后类型更清晰）
- Phase 16 独立（可随时执行，但建议在 12 之后避免 rebase）
- Phase 17 独立（可随时执行）
