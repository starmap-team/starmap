# Phase 7: 审计闭环 — 29 个剩余 Findings

**触发:** /goal 检索审计修复内容，基于GSD相关规范驱动流程，完成整套闭环开发流程
**日期:** 2026-07-07
**前置:** Milestone v2.0 完成 (6/6 Phase), 审计 56 findings 中 27 已修复

---

## 剩余 Findings 分组与修复计划

### 批次 A: 快速修复 (1h, 纯机械改动)
- [x] B5-rem: PositionDetail.vue + PositionList.vue 直接 request → jd.ts store
- [x] c1: graph_service.py inline import loguru → 顶层
- [x] c3: 已修复 (timeseries_loader 消除了 datetime inline import)
- [x] c4: evolution.py coalesce(..., 0.5) → DEFAULT_SIMILARITY 常量
- [x] m4: evolution.py magic number 7 → 命名常量
- [x] c5: usePipelineMonitor.ts refreshInterval=10 → 常量
- [x] c6: useSSE.ts 默认参数加 JSDoc
- [x] c7: LoopDemo.vue timeout=180000 → 常量
- [x] c8: jd.ts page_size=100 → 常量

### 批次 B: 小型重构 (2h, 需要理解上下文)
- [x] m2: main.py 硬编码 CORS → settings.cors_origins
- [x] m3: admin.py 硬编码 authority scores → config
- [x] m12: Graph2D.vue tooltip inline style → chartTheme.ts
- [x] m13: G6 lifecycle 重复 → composables/useG6Graph.ts
- [x] m14: PositionSearch.vue 直接 request → jd.ts store
- [x] m17: 已修复 (datasource.ts config 用 Record<string, unknown>)
- [x] m16: 已修复 (datasource.ts 有 error ref)

### 批次 C: 中型重构 (4h, 跨文件改动)
- [x] M23: 3 页面直接 import request → store 迁移 (Admin/ExtractJD/MatchDiagnosis)
- [x] m7: graph_service.py 823→564 行 → graph_sync.py 拆分
- [x] m8: DataDashboard.vue 20+ rgba → CSS variables (--dash-*)
- [x] m9: DashboardLayout.vue 18+ 硬编码颜色 → tokens (--dash-*)
- [x] m15: pipeline.ts 462 行 — 未超限，暂不拆分

### 批次 D: 大型重构 (长期, 超大文件拆分)
- [ ] M13: LoopDemo.vue 1682 行 → 子组件
- [ ] M14: MatchDiagnosis.vue 1467 行 → step 组件 + store
- [ ] M15: DataDashboard.vue 1217 行 → composable
- [ ] M16: EvolutionDashboard.vue 976 行 (已用 store, 行数仍超)

### 批次 E: 类型安全 (长期)
- [ ] m10: Graph3D.vue 15+ any → @types/three + shim
- [ ] m11: env.d.ts 35 any-typed → 同 m10

---

## 执行策略

1. 先执行 A+B 批次（快速修复，低风险）
2. C 批次逐个推进（每个独立 commit）
3. D+E 批次按 Ponytail 原则渐进，不追求一次全改
4. 每个 batch 完成后运行 ruff + lint + typecheck 验证
5. 最后更新审计报告，标记闭环完成
