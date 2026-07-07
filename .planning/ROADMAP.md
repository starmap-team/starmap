# Roadmap: StarMap v2.0 全系统功能闭环

**Created:** 2026-07-02
**Milestone:** v2.0 — 全系统功能闭环
**Total phases:** 6
**Total requirements:** 72

## Phase Summary

| # | Phase | Goal | Requirements | Est. Days | Success Criteria |
|---|-------|------|--------------|-----------|------------------|
| 1 | 核心Bug修复 | 修复运行时错误、内存存储持久化、安全漏洞 | 8 | 1-2 | 0运行时Bug、0内存存储、0 Cypher注入 |
| 2 | 后端硬编码消除 | 匹配引擎图谱驱动、EVOLVES_TO入图、学习路径去硬编码 | 14 | 2-3 | 0硬编码Profile、EVOLVES_TO在Neo4j、真实趋势数据 |
| 3 | 前端功能闭环 | 所有页面功能完整、无死按钮、演化视图实现 | 16 | 2-3 | 14页面全功能、0死按钮、演化视图可用 |
| 4 | 数据流贯通 | 抽取→图谱→匹配→演化→质量端到端贯通 | 10 | 1-2 | 闭环5步全真实、评估函数实现、三方准确率报告 |
| 5 | 样式统一与体验优化 | Design tokens统一、颜色系统合并、死代码清理 | 12 | 1-2 | 1套颜色、GraphToolbar受控、6死端点删除 |
| 6 | 架构重构 | Home.vue拆分、Pipeline模块拆分、重复代码消除 | 12 | 2-3 | Home≤350行、pipeline.py≤300行、0重复代码 |

**Coverage:** 100% (72/72 requirements mapped across 6 phases)

---

## Phase 1: 核心Bug修复

**Goal:** 修复所有运行时错误，将内存存储迁移到持久化，消除安全漏洞。

**Requirements:**
- RUNTIME-01 ~ RUNTIME-03 (3) — 运行时错误
- PERSIST-01 ~ PERSIST-03 (3) — 内存存储持久化
- SEC-01 ~ SEC-02 (2) — 安全修复

**Success criteria:**
1. `pytest` 全部通过，0 运行时 AttributeError
2. 重启后端后 match_results / loop_results / review_queue 数据不丢失
3. Cypher 查询全部参数化，无字符串拼接
4. 源码中无明文密码

**Key files:**
- `backend/app/core/pipeline/status_aggregator.py` — snapshot_at bug
- `backend/app/core/pipeline/loop_orchestrator.py` — sync_from_pipeline TODO
- `backend/app/services/match_service.py` — 内存缓存 + json import
- `backend/app/api/v1/admin.py` — Cypher注入 + 内存审核队列
- `backend/app/config.py` — 默认密码

---

## Phase 2: 后端硬编码消除

**Goal:** 消除所有硬编码数据源，让系统从Neo4j图谱动态加载，确保52个岗位全部可匹配。

**Requirements:**
- MATCH-01 ~ MATCH-05 (5) — 匹配引擎图谱驱动
- EVOLVE-01 ~ EVOLVE-04 (4) — EVOLVES_TO写入Neo4j
- LEARN-01 ~ LEARN-03 (3) — 学习路径去硬编码
- TREND-01 ~ TREND-03 (3) — 演化趋势真实数据
- PIPE-HC-01 ~ PIPE-HC-03 (3) — Pipeline executor去硬编码

**Success criteria:**
1. 52个岗位全部可匹配（不再只有8个硬编码岗位）
2. `MATCH (a:Position)-[r:EVOLVES_TO]->(b:Position) RETURN count(r)` > 0
3. `/evolution/trends` 返回真实CII数据（非模拟）
4. `/quality/dashboard` 幻觉趋势从真实timeseries计算
5. Pipeline crawl keyword 从 DataSourceRecord 读取

**Key files:**
- `backend/app/services/match_service.py` — POSITION_SKILL_PROFILES
- `backend/app/core/evolution/orchestrator.py` — EVOLVES_TO Neo4j写入
- `backend/app/core/learning/path_engine.py` — DEFAULT_PREREQUISITES
- `backend/app/api/v1/evolution.py` — 模拟CII数据
- `backend/app/api/v1/quality.py` — 模拟幻觉趋势
- `backend/app/core/pipeline/executor.py` — 硬编码keyword

---

## Phase 3: 前端功能闭环

**Goal:** 所有14个页面功能完整闭环，无死按钮、无空功能、演化视图实现。

**Plans:** 3/3 plans complete

Plans:
- [x] 03-01-PLAN.md — Admin + LearningCenter 功能闭环 (ADMIN-01~03, LEARN-FE-01~04) — committed 128294a/924ab5e/5865a01
- [x] 03-02-PLAN.md — 演化视图 3D 渲染 + 时间线滑块 (EVOLVE-FE-01~04)
- [x] 03-03-PLAN.md — 匹配诊断增强 + Pipeline 闭环 + Dashboard (MATCH-FE-01~02, PIPE-FE-01~05, DASH-FE-01~02)

**Requirements:**
- ADMIN-01 ~ ADMIN-03 (3) — Admin功能闭环
- LEARN-FE-01 ~ LEARN-FE-04 (4) — LearningCenter功能闭环
- EVOLVE-FE-01 ~ EVOLVE-FE-04 (4) — 演化视图实现
- MATCH-FE-01 ~ MATCH-FE-02 (2) — 匹配诊断增强
- PIPE-FE-01 ~ PIPE-FE-05 (5) — Pipeline前端闭环
- DASH-FE-01 ~ DASH-FE-02 (2) — DataDashboard增强

**Success criteria:**
1. Admin 编辑/保存数据源 → API调用 → 刷新列表
2. LearningCenter "加入计划" → 创建学习计划 → 显示进度
3. 图谱"演化"视图显示 EVOLVES_TO 关系边（绿/灰/红着色）
4. 匹配诊断学习路径 → 格式化时间线（非JSON数组）
5. PipelineMonitor 重试/配置/调度全部联动
6. 0个死按钮（所有按钮有handler且调API）

**Key files:**
- `frontend/src/pages/Admin.vue` — handleSaveSource
- `frontend/src/pages/LearningCenter.vue` — 加入计划 + demo数据
- `frontend/src/pages/Home.vue` — 演化视图
- `frontend/src/pages/MatchDiagnosis.vue` — 学习路径格式化
- `frontend/src/pages/PipelineMonitor.vue` — 重试/配置/调度
- `frontend/src/pages/EvolutionDashboard.vue` — 时间线滑块

---

## Phase 4: 数据流贯通 ✓

**Goal:** 端到端数据流贯通，从JD抽取到图谱写入到匹配诊断到演化分析到质量监控，全链路真实执行。

**Plans:** 3/3 plans complete

Plans:
- [x] 04-01-PLAN.md — EVAL-02 LLM Judge 超时降级 (EVAL-02) — committed 5d163ad/3551f0f
- [x] 04-02-PLAN.md — quality_report.py --ci 子命令 (EVAL-01/03/04) — committed a68cb9a/3551f0f
- [x] 04-03-PLAN.md — E2E 闭环 5 步验证 (LOOP-FLOW-02) — committed 5772056

**Requirements:**
- EXTRACT-FLOW-01 ~ EXTRACT-FLOW-03 (3) — 抽取→图谱链路
- LOOP-FLOW-01 ~ LOOP-FLOW-03 (3) — 闭环流程贯通
- MATCH-LEARN-01 ~ MATCH-LEARN-02 (2) — 匹配→学习路径链路
- EVAL-01 ~ EVAL-04 (4) — 评估链路补全

**Success criteria:**
1. JD抽取 → 技能归一化 → 图谱写入 → 匹配可用（端到端）
2. 闭环5步全部真实执行，0降级步骤
3. 匹配诊断差距分析 → 自动生成学习计划
4. `scripts/quality_report.py` 3个评估函数返回真实结果
5. 三方准确率报告完整（JD F1 + Resume F1 + Match Accuracy）

**Key files:**
- `backend/app/core/extraction/prompt.py` — 增加字段提取
- `backend/app/core/extraction/graph_writer.py` — 激活死代码
- `backend/app/services/graph_service.py` — sync_from_pipeline + depth参数
- `backend/app/core/pipeline/loop_orchestrator.py` — 闭环贯通
- `scripts/quality_report.py` — 评估函数实现
- `evaluation/judge_eval.py` — LLM judge实现

---

## Phase 5: 样式统一与体验优化 ✓

**Goal:** 统一设计系统，合并颜色源，清理死代码，提升用户体验一致性。

**Plans:** 4/4 plans complete

Plans:
- [x] 05-01-PLAN.md — ECHARTS_PALETTE + DataDashboard 迁移 (COLOR-01~04, STYLE-01)
- [x] 05-02-PLAN.md — NodeTooltip3D Slate 替换 + design-tokens 补全 (COLOR-03, STYLE-04)
- [x] 05-03-PLAN.md — 2D/3D KA 一致性 Playwright harness (COLOR-04)
- [x] 05-04-PLAN.md — P5 收尾验证 + STATE 更新

**Requirements:**
- STYLE-01 ~ STYLE-04 (4) — Design Tokens统一
- COLOR-01 ~ COLOR-04 (4) — 颜色系统统一
- TOOLBAR-01 ~ TOOLBAR-03 (3) — GraphToolbar受控化
- SCHEMA-01 ~ SCHEMA-02 (2) — schema.ts补全
- CLEANUP-01 ~ CLEANUP-04 (4) — 清理

**Success criteria:**
1. 所有页面使用 design tokens，无硬编码颜色值
2. 仅1个颜色源文件 `utils/graphColors.ts`
3. GraphToolbar 无内部状态ref，纯受控组件
4. `npm run gen:api` 后 schema.ts 覆盖所有API
5. 后端6个死端点删除，ruff + pytest 通过
6. 2D/3D KA节点颜色一致

**Key files:**
- `frontend/src/utils/graphColors.ts` — 颜色统一
- `frontend/src/composables/useGraphColors.ts` — 删除
- `frontend/src/components/GraphToolbar.vue` — 受控化
- `frontend/src/components/NodeTooltip3D.vue` — TYPE_INFO
- `frontend/src/components/Graph3D.vue` — console.log
- `backend/app/api/v1/graph.py` — 死端点删除
- `frontend/src/pages/PipelineAnalysis.vue` — design tokens
- `tests/e2e/test_2d_3d_color_consistency.py` — Playwright harness

---

## Phase 6: 架构重构

**Goal:** 拆分巨型文件，消除代码重复，建立可维护的模块化架构。

**Requirements:**
- HOME-SPLIT-01 ~ HOME-SPLIT-04 (4) — Home.vue拆分
- PIPE-SPLIT-01 ~ PIPE-SPLIT-04 (4) — Pipeline模块拆分
- DEDUP-01 ~ DEDUP-03 (3) — 重复代码消除

**Success criteria:**
1. Home.vue ≤ 350行（含template + style）
2. Graph2D.vue ~450行，封装G6渲染
3. `pipeline.py` 拆分为3个文件，每个≤300行
4. SimHash仅1个模块
5. `create_async_engine` 仅1处调用
6. `run_async` 仅1处定义
7. vue-tsc + eslint + ruff + pytest 全部通过

**Key files:**
- `frontend/src/pages/Home.vue` — 1316行→350行
- `frontend/src/components/Graph2D.vue` — 新建
- `backend/app/api/v1/pipeline.py` — 拆分
- `backend/app/core/pipeline/simhash.py` — 合并
- `backend/app/core/pipeline/data_fusion.py` — dead code删除

---

## ▶ Next Up

**Phase 1: 核心Bug修复** — 修复运行时错误、内存存储持久化、安全漏洞

执行命令: `/gsd-plan-phase 1`
