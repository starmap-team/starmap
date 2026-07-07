# StarMap 全栈代码质量 & 复用性审计报告

**日期:** 2026-07-07
**范围:** 前端 (79 文件, ~26,500 行) + 后端 (Python/FastAPI)
**触发:** `/gsd-verify-work --all 同时进行代码质量评审及复用性审计`

---

## BLOCKER (7 findings)

### 后端

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| B1 | `PROFICIENCY_SCORE` dict 在 4 处重复定义 | scorer.py:14, service.py:27, path_engine.py:25, match_service_legacy.py:36 | 统一到 `matching/constants.py` |
| B2 | `_extraction_payload_from_record` 在 2 处逐字复制 | graph_service.py:837, stage3_services.py:36 | 提取为 `JDExtractionRecord` class method |
| B3 | `ALLOWED_LABELS` 在 2 处定义且集合不一致 | admin.py:122 (缺 Certificate/LearningResource), graph_writer.py:38 (缺 Domain) | 统一 `ALLOWED_NODE_LABELS` in graph_writer.py |

### 前端

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| B4 | `api/schema.ts` 1228 行从未被 import — 57 个 `as any` 类型转换无依据 | 25 个文件 | 创建 `api/client.ts` 用 `schema.paths` 做类型化调用 |
| B5 | 3 个页面绕过 store 直接 `request` 调用 | PositionDetail.vue, PositionList.vue, EvolutionDashboard.vue | 将 fetch 移入 store |
| B6 | `admin.ts` 和 `datasource.ts` store 重复 fetch `/datasources` | admin.ts:34, datasource.ts:50 | 统一为 `datasource.ts` 单一真相源 |
| B7 | `LearningPathItem` interface 在 2 个 store 中完全相同定义 | learning.ts:34, loop.ts:62 | 提取到 `types/learning.ts` |

---

## MAJOR (24 findings)

### 后端 (12)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| M1 | Skill timeseries 加载模式在 7+ 处重复 (~15行块) | evolution.py 5处, orchestrator.py, position.py | 提取 `_load_skill_timeseries_data()` |
| M2 | `match_service_legacy.py` 1036 行是已重构模块的死亡副本 | services/match_service_legacy.py | **删除** |
| M3 | `_load_target_profile` 实现 3 次 | legacy, service.py, match_service.py wrapper | 仅保留 MatchService 公开方法 |
| M4 | `_apply_inflation_correction` 实现 2 次 | legacy:408, service.py:180 | 仅保留 service.py 版本 |
| M5 | `enrich_learning_paths` 实现 2 次（相同 Neo4j 查询） | legacy:492, match_service.py:95 | 单一实现 in core/matching/ |
| M6 | `compute_competitiveness` 实现 2 次（相同公式） | legacy:924, match_service.py:191 | 单一实现 |
| M7 | `run_batch_match` 实现 2 次（相同结构） | legacy:843, match_service.py:132 | 单一实现 |
| M8 | `_normalize_proficiency` 在 2 处重复且关键词集略有不同 | graph_writer.py:123, graph_service.py:153 | 统一到 `normalize.py` |
| M9 | `senior_keywords` 硬编码集合在同一文件定义 2 次 | evolution.py:601, :634 | 提取为 module-level constant |
| M10 | `_skill_entry_name` / `_skill_name` 在 2 模块重复 | graph_writer.py:111, stage3_services.py:24 | 共享 utility function |
| M11 | `_skill_entry_category` / `_skill_category` 在 2 模块重复 | graph_writer.py:132, stage3_services.py:30 | 共享 utility function |
| M12 | 混合 logging 框架 (`logging` vs `loguru`) | graph_service.py, config.py, cron_scheduler.py, celery_app.py 等 6 文件 | 统一到 loguru |

### 前端 (12)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| M13 | `LoopDemo.vue` 1682 行 — 5 步渲染器巨型单体 | pages/LoopDemo.vue | 提取每步为子组件 |
| M14 | `MatchDiagnosis.vue` 1467 行 — inline 数据获取 | pages/MatchDiagnosis.vue | 提取 step 组件 + 移 fetch 到 store |
| M15 | `DataDashboard.vue` 1217 行 — chart configs + SSE + KPI 全 inline | pages/DataDashboard.vue | 提取 `useDataDashboardCharts.ts` composable |
| M16 | `EvolutionDashboard.vue` 976 行 + 直接 API 调用 | pages/EvolutionDashboard.vue | 添加 evolution store |
| M17 | `cv()` CSS variable reader 在 4 处重复 | chartTheme.ts, useHomeInteractions.ts, Graph2D.vue, LearningPathFlow.vue, LoopDemo.vue | 统一从 `chartTheme.ts` export |
| M18 | `ensureG6Loaded()` 在 3 处重复 | CareerPathGraph.vue, LearningPathFlow.vue, LoopDemo.vue | 提取到 `composables/useG6.ts` |
| M19 | `PROFICIENCY_MAP` 在 2 页面独立定义且标准化不一致 | MatchDiagnosis.vue:66, PositionDetail.vue:41 | `utils/proficiency.ts` 单一规范 |
| M20 | `QualityAlert` interface 在 2 store 定义且字段不一致 | quality.ts:61, pipeline.ts:91 | 统一到 `types/quality.ts` |
| M21 | 24 个 `console.log/warn/error/info` 仍留在生产代码 | 11 文件 | 替换为 logger 或 Vite `drop_console` |
| M22 | `DataSource` interface 与 `DataSourceDetail` 近乎相同 | pipeline.ts:41, datasource.ts:12 | pipeline.ts import datasource.ts 版本 |
| M23 | 18 文件直接 import `request` — 无 store/API 边界 | 5 页面 + 1 组件 + 12 stores | lint 规则禁止 `.vue` 文件 import request |
| M24 | `EmergingSkill` interface 仅在 dashboard.ts 定义但跨域使用 | dashboard.ts:74 | 移到 `types/evolution.ts` |

---

## MINOR (17 findings)

### 后端 (7)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| m1 | 死表达式 `set(person_level_map)` | scorer.py:108 | 删除 |
| m2 | 硬编码 CORS origins | main.py:45 | 移到 `settings.cors_origins` |
| m3 | 硬编码 authority scores | admin.py:201-205 | 移到 config 或 DB |
| m4 | Magic number 7 (CII source threshold) | evolution.py:525 | 提取为命名常量 |
| m5 | `_save_match_result` 原始 SQL 在 legacy 和 service 重复 | legacy:585, service.py:385 | 单一 repository method |
| m6 | `ReviewQueue` 在 admin.py 函数体内 6 次 inline import | admin.py:156,225,271,297,325,359 | 加入顶层 import |
| m7 | `graph_service.py` 857 行超限 | services/graph_service.py | 分拆为 serializers/queries/sync |

### 前端 (10)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| m8 | DataDashboard.vue 20+ 硬编码 `rgba(...)` 不引用 tokens | DataDashboard.vue:786-1170 | 替换为 CSS variables |
| m9 | DashboardLayout.vue 18+ 硬编码颜色值 | DashboardLayout.vue:88-200 | 引用 tokens |
| m10 | Graph3D.vue 15+ `any` 类型 | Graph3D.vue 多处 | 安装 @types/three + 写 d3-force-3d shim |
| m11 | env.d.ts 35 个 `any`-typed module exports | env.d.ts:1-43 | 同 m10 |
| m12 | Tooltip inline style 在 3 文件重复 | Graph2D.vue, LoopDemo.vue, LearningPathFlow.vue | 提取到 chartTheme.ts |
| m13 | G6 lifecycle (mount/resize/destroy) 在 2 组件重复 | CareerPathGraph.vue, LearningPathFlow.vue | `composables/useG6Graph.ts` |
| m14 | PositionSearch.vue 直接 `request.get('/positions')` | PositionSearch.vue:24 | 用 jd.ts store |
| m15 | pipeline.ts 486 行管理 9 域概念 | stores/pipeline.ts | 分拆为 status + config |
| m16 | admin.ts 无 error state | stores/admin.ts:31-39 | 添加 `error: ref<string|null>` |
| m17 | `SourceConfig` config 字段用 `Record<string, any>` | admin.ts:16 | 类型化或用 `unknown` |

---

## COSMETIC (7 findings)

### 后端 (3)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| c1 | graph_service.py 在异常处理内 inline import loguru | :451,537,687 | 移到顶层 |
| c2 | ReviewQueue 别名 ReviewQueueModel | admin.py 多处 | 重命名消歧 |
| c3 | `datetime.UTC` 在函数体内 import | evolution.py:130, orchestrator.py:685 | 顶层 import |
| c4 | Neo4j EVOLVES_TO 查询 10+ 处 `coalesce(..., 0.5)` | evolution.py 多处 | `DEFAULT_SIMILARITY=0.5` |

### 前端 (4)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| c5 | `refreshInterval=10` 硬编码 | usePipelineMonitor.ts:19 | 常量/环境变量 |
| c6 | `maxRetries=10`, `baseDelay=1000` 默认未文档 | useSSE.ts:21-22 | JSDoc |
| c7 | `timeout=180000` 硬编码 inline | LoopDemo.vue:159 | `LOOP_RUN_TIMEOUT_MS` |
| c8 | `page_size=100` 硬编码 | jd.ts:26 | 可配置常量 |

---

## 统计

| 严重级别 | 后端 | 前端 | 合计 |
|----------|------|------|------|
| Blocker  | 3    | 4    | 7    |
| Major    | 12   | 12   | 24   |
| Minor    | 7    | 10   | 17   |
| Cosmetic | 4    | 4    | 8    |
| **合计** | **26** | **30** | **56** |

## 按类别统计

| 类别 | 数量 | 占比 |
|------|------|------|
| 代码重复 | 22 | 39% |
| 代码质量 | 15 | 27% |
| 架构问题 | 5 | 9% |
| 复用机会 | 4 | 7% |
| 其他 | 10 | 18% |

---

## Top 5 修复优先级（投入产出最高）

### 1. 删除 `match_service_legacy.py` ⚡ 6 个 major 消除
一次性删除 1036 行死亡副本 + 清理 `match_service.py` wrapper，消除 M2-M7 + m5 + m11（共 8 个 findings）。

### 2. 统一共享常量 ⚡ 3 个 blocker 消除
- `PROFICIENCY_SCORE` → `matching/constants.py`
- `ALLOWED_NODE_LABELS` → 合并 admin.py + graph_writer.py
- `senior_keywords` → evolution.py module-level

### 3. 提取前端共享 composables ⚡ 4 个 major + 3 个 minor 消除
- `cv()` → 从 `chartTheme.ts` 统一导出
- `ensureG6Loaded()` → `composables/useG6.ts`
- `PROFICIENCY_MAP` → `utils/proficiency.ts`
- G6 lifecycle → `composables/useG6Graph.ts`

### 4. 接入 `api/schema.ts` 类型 ⚡ 57 个 `as any` 消除
创建 `api/client.ts` 类型化 wrapper，逐步替换 store/page 中的 `as any` casts。

### 5. 前端超大文件拆分 ⚡ 长期可维护性
LoopDemo(1682)、MatchDiagnosis(1467)、DataDashboard(1217)、EvolutionDashboard(976) 四个文件需逐步拆分。建议作为 Phase 7+ 任务，按 Ponytail 原则逐个处理。

---

*审计完成: 2026-07-07*
