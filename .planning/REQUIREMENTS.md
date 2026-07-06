# Requirements: StarMap v2.0 全系统功能闭环

**Defined:** 2026-07-02
**Core Value:** 所有模块功能闭环、页面样式统一、业务流程完整、赛题核心功能可演示

## v2.0 Requirements (Active)

按 Phase 分组，每个 REQ-ID 锁定一个可验证的验收点。

---

### Phase 1 — 核心Bug修复 (BUGFIX)

#### 运行时错误修复 (RUNTIME)
- [ ] **RUNTIME-01**: `status_aggregator.py` 修复 `EvolutionSnapshot.snapshot_at` → `snapshot_date`（运行时AttributeError）
- [ ] **RUNTIME-02**: `loop_orchestrator.py` Step3 `sync_from_pipeline` 未实现导致永远降级 — 实现 `graph_service.sync_from_pipeline()`
- [ ] **RUNTIME-03**: `match_service.py` 修复 `__import__("json")` 内联导入 → 顶部 `import json`

#### 内存存储持久化 (PERSIST)
- [ ] **PERSIST-01**: `match_service._MATCH_RESULTS` 内存缓存 → PostgreSQL match_results 表持久化
- [ ] **PERSIST-02**: `loop_orchestrator._LOOP_RESULTS` 内存存储 → PostgreSQL 持久化
- [ ] **PERSIST-03**: `admin._demo_audit_queue` 内存存储 → PostgreSQL review_queue 表持久化（已有模型）

#### 安全修复 (SEC)
- [ ] **SEC-01**: `admin.py` 图谱节点CRUD Cypher注入 → 参数化查询
- [ ] **SEC-02**: `config.py` 默认密码移至 `.env`，源码中不含明文密码

---

### Phase 2 — 后端硬编码消除 (HARDCODE)

#### 匹配引擎图谱驱动 (MATCH)
- [ ] **MATCH-01**: 删除 `POSITION_SKILL_PROFILES` 硬编码字典（8个岗位）
- [ ] **MATCH-02**: `_load_target_profile()` 改为从 Neo4j 加载（通过 `fetch_position_graph`）
- [ ] **MATCH-03**: 从 Neo4j REQUIRES 关系提取 required_skills 和 bonus_skills（基于 importance 属性）
- [ ] **MATCH-04**: 删除 `_fallback_profile()` 硬编码 fallback → Neo4j 不可用时返回 404
- [ ] **MATCH-05**: 技能匹配增加语义相似度（ChromaDB 向量检索），不再仅字符串匹配

#### EVOLVES_TO 写入 Neo4j (EVOLVE)
- [ ] **EVOLVE-01**: `orchestrator._save_paths_to_db()` 末尾添加 Neo4j 写入
- [ ] **EVOLVE-02**: 构建 EVOLVES_TO 三元组: (source_pos)-[EVOLVES_TO]->(target_pos)
- [ ] **EVOLVE-03**: 属性: direction, skill_overlap, key_gaps, evidence_count, trust_score
- [ ] **EVOLVE-04**: 调用 `graph_writer.write_triples_to_graph()` 写入 Neo4j

#### 学习路径去硬编码 (LEARN)
- [ ] **LEARN-01**: `path_engine.DEFAULT_PREREQUISITES` → 从 Neo4j PREREQUISITE 关系加载
- [ ] **LEARN-02**: `path_engine._BASE_HOURS` → 从 Neo4j Skill 节点属性加载
- [ ] **LEARN-03**: 学习路径时间线组件从 JSON 数组 → 格式化卡片/时间线UI

#### 演化趋势真实数据 (TREND)
- [ ] **TREND-01**: `/evolution/trends` 移除模拟CII时序数据fallback → 无数据时返回空数组+提示
- [ ] **TREND-02**: `/quality/dashboard` 幻觉趋势移除4季度模拟数据 → 从真实 timeseries 计算
- [ ] **TREND-03**: `evolution.py` `/trends` 的 `days` 查询参数不再被忽略

#### Pipeline executor 去硬编码 (PIPE-HC)
- [ ] **PIPE-HC-01**: `execute_crawl` 移除硬编码 `keyword="python"` → 从 DataSourceRecord 配置读取
- [ ] **PIPE-HC-02**: `execute_crawl` 移除硬编码 `max_count=50/200` → 可配置
- [ ] **PIPE-HC-03**: `_update_source_after_dedup` 移除硬编码 `"bosszhipin"` → 从 run context 读取

---

### Phase 3 — 前端功能闭环 (FRONTEND)

#### Admin 功能闭环 (ADMIN)
- [ ] **ADMIN-01**: `handleSaveSource` 实际调用 API（当前只改本地状态）
- [ ] **ADMIN-02**: 审核队列"编辑"按钮实现编辑弹窗+API调用
- [ ] **ADMIN-03**: 数据源"编辑"保存后刷新列表

#### LearningCenter 功能闭环 (LEARN-FE)
- [ ] **LEARN-FE-01**: "加入计划"按钮绑定 handler → 调用 `POST /learning/plans`
- [ ] **LEARN-FE-02**: 移除硬编码 demo 数据 → 从 API 加载
- [ ] **LEARN-FE-03**: 学习进度展示 → 调用 `GET /learning/progress/{plan_id}`
- [ ] **LEARN-FE-04**: 空状态引导（无学习计划时显示引导）

#### 演化视图实现 (EVOLVE-FE)
- [ ] **EVOLVE-FE-01**: 图谱页面"演化"视图模式实现 EVOLVES_TO 关系边渲染
- [ ] **EVOLVE-FE-02**: EVOLVES_TO 边着色：rising=绿, stable=灰, declining=红
- [ ] **EVOLVE-FE-03**: 点击 EVOLVES_TO 边弹出演化详情（技能变化、时间跨度）
- [ ] **EVOLVE-FE-04**: 演化看板添加时间线滑块（快照时间点选择）

#### 匹配诊断增强 (MATCH-FE)
- [ ] **MATCH-FE-01**: 学习路径从 JSON 数组 → 格式化时间线/卡片组件
- [ ] **MATCH-FE-02**: 岗位详情"热度"列从原始数字 → 进度条/星级显示

#### Pipeline 前端闭环 (PIPE-FE)
- [ ] **PIPE-FE-01**: PipelineStageCard failed 时红色边框高亮
- [ ] **PIPE-FE-02**: 重试按钮点击后 loading spinner
- [ ] **PIPE-FE-03**: 配置保存后 toast 提示 "已更新，下一个 run 生效"
- [ ] **PIPE-FE-04**: 调度列表显示 last_run_at 和 next_run_at
- [ ] **PIPE-FE-05**: 支持"立即执行"按钮

#### DataDashboard 增强 (DASH-FE)
- [ ] **DASH-FE-01**: KPI 卡片点击跳转到对应详情页
- [ ] **DASH-FE-02**: SSE 事件驱动 KPI 实时更新

---

### Phase 4 — 数据流贯通 (DATAFLOW)

#### 抽取→图谱链路 (EXTRACT-FLOW)
- [ ] **EXTRACT-FLOW-01**: 抽取 Prompt 增加 prerequisites/learning_resources/evolves_to/tools 字段提取
- [ ] **EXTRACT-FLOW-02**: graph_writer 中4-7个死代码函数（基于上述字段）被激活
- [ ] **EXTRACT-FLOW-03**: 图谱 depth 参数不再被忽略 → Cypher 多跳遍历

#### 闭环流程贯通 (LOOP-FLOW)
- [ ] **LOOP-FLOW-01**: `sync_from_pipeline` 实现完整：从 pipeline_runs 提取数据写入 Neo4j
- [ ] **LOOP-FLOW-02**: 闭环5步全部真实执行（不再有降级步骤）
- [ ] **LOOP-FLOW-03**: 闭环结果写入 PostgreSQL（不再内存存储）

#### 匹配→学习路径链路 (MATCH-LEARN)
- [ ] **MATCH-LEARN-01**: 匹配诊断差距分析 → 自动生成学习计划
- [ ] **MATCH-LEARN-02**: 学习计划关联匹配结果 ID

#### 评估链路补全 (EVAL)
- [ ] **EVAL-01**: `scripts/quality_report.py` 3个评估函数从 "pending" → 真实实现
- [ ] **EVAL-02**: `evaluation/judge_eval.py` LLM judge 评估从 "not yet implemented" → 实现
- [ ] **EVAL-03**: 简历提取 F1 测量执行（10条 Golden Set）
- [ ] **EVAL-04**: 三方准确率报告生成（JD F1 + Resume F1 + Match Accuracy）

---

### Phase 5 — 样式统一与体验优化 (UX)

#### Design Tokens 统一 (STYLE)
- [ ] **STYLE-01**: `PipelineAnalysis.vue` 使用 design tokens + MainLayout 包裹
- [ ] **STYLE-02**: `DataQualityGauge.vue` 修复乱码编码
- [ ] **STYLE-03**: 所有页面统一使用 `MainLayout` 或 `DashboardLayout`
- [ ] **STYLE-04**: 统一空状态组件（无数据时的友好提示）

#### 颜色系统统一 (COLOR)
- [ ] **COLOR-01**: 合并3套颜色源为1个 `utils/graphColors.ts`
- [ ] **COLOR-02**: 删除 `composables/useGraphColors.ts`
- [ ] **COLOR-03**: `NodeTooltip3D.vue` 使用 `TYPE_INFO` 替代内联颜色映射
- [ ] **COLOR-04**: 2D/3D KA 节点颜色一致

#### GraphToolbar 受控化 (TOOLBAR)
- [ ] **TOOLBAR-01**: GraphToolbar 删除内部 maxNodes/selectedProficiencies ref
- [ ] **TOOLBAR-02**: 改为受控组件：props in, events out
- [ ] **TOOLBAR-03**: Home.vue 单向数据流管理

#### schema.ts 补全 (SCHEMA)
- [ ] **SCHEMA-01**: `npm run gen:api` 重新生成 schema.ts 覆盖所有 API 端点
- [ ] **SCHEMA-02**: 前端 stores 中所有 API 调用使用 schema 类型

#### 清理 (CLEANUP)
- [ ] **CLEANUP-01**: 删除后端6个死端点（graph.py: query/panorama/position-name/domain/domains/domain-switch）
- [ ] **CLEANUP-02**: 删除对应 Pydantic models 和 service 函数
- [ ] **CLEANUP-03**: 删除前端 mock handler 中 `/api/v1/graph/panorama`
- [ ] **CLEANUP-04**: Graph3D.vue 删除 console.log 残留

---

### Phase 6 — 架构重构 (REFACTOR)

#### Home.vue 拆分 (HOME-SPLIT)
- [ ] **HOME-SPLIT-01**: 新建 `Graph2D.vue` (~450行) — G6 渲染封装
- [ ] **HOME-SPLIT-02**: Home.vue 从1316行 → ~350行（状态管理+事件桥接）
- [ ] **HOME-SPLIT-03**: G6 相关逻辑（initGraph/render三层/highlightNode/resize）移入 Graph2D
- [ ] **HOME-SPLIT-04**: 2D/3D 统一用 v-if，删除 graph3DReady hack

#### Pipeline 模块拆分 (PIPE-SPLIT)
- [ ] **PIPE-SPLIT-01**: `pipeline.py` 拆分为 schemas.py + serializers.py + routes.py
- [ ] **PIPE-SPLIT-02**: SimHash 3处实现合并为1个模块
- [ ] **PIPE-SPLIT-03**: 共享 Session 上下文（替换6处内联 create_async_engine）
- [ ] **PIPE-SPLIT-04**: pipeline.ts + loop.ts 合并为1个 store

#### 重复代码消除 (DEDUP)
- [ ] **DEDUP-01**: `run_async/_run_async` 3处重复 → 统一到 `app/utils/async_helpers.py`
- [ ] **DEDUP-02**: `data_fusion.py` 中 SimHash dead code 删除
- [ ] **DEDUP-03**: `resume_eval.py` 如无调用者则移入 evaluation 模块

---

## Out of Scope

- ❌ 引入新数据库（保持 PostgreSQL 16 + Neo4j + Redis + ChromaDB）
- ❌ 更换前端框架（保持 Vue 3 + Element Plus + Pinia）
- ❌ 更换后端框架（保持 FastAPI）
- ❌ UI视觉重新设计（仅功能闭环和样式统一）
- ❌ PPT/演示视频制作（文档范畴，非代码开发）
- ❌ 性能优化（无当前瓶颈）
- ❌ 新增爬虫（保持5个现有爬虫）
- ❌ 国际化（保持中文为主）

## Traceability

> This section maps requirements → phases

See `.planning/ROADMAP.md` for the mapping.
