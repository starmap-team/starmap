# StarMap Project — 全系统二次开发

**Last updated:** 2026-07-02
**Branch:** fix/all-26-bugs
**Status:** Active development — 全系统功能闭环

## What This Is

StarMap（星图）是一个**人才能力星云导航系统**，面向IT岗位的技能图谱与匹配诊断平台。核心产品价值：把IT行业海量JD与求职者的技能图谱对齐，让求职者看到自己当前的"能力星云"，并通过可信的演化趋势/匹配诊断/学习路径推荐，找到迈向目标岗位的最短路径。

系统的差异化点：
- **可追溯**：每个技能/匹配/推荐都有源（source）、时间（temporal）、交叉验证（cross-source）三重可信度
- **反幻觉**：仅采纳 ≥3 个独立来源、≥4 周时间跨度、跨源一致的技能作为"已验证"
- **可演化**：跟踪技能/岗位的兴衰周期，识别新兴技能（emerging/rising/declining）

## Current Milestone: v2.0 全系统功能闭环

**Goal:** 将StarMap从"半成品状态"演进为"所有模块功能闭环、页面样式统一、业务流程完整"的可交付系统。

**核心问题诊断：**
1. **后端硬编码**：匹配引擎8个岗位Profile硬编码、学习路径20+前置依赖硬编码、演化趋势模拟数据
2. **前端功能断裂**：Admin编辑不调API、LearningCenter按钮无handler、演化视图仅有radio button
3. **数据流断裂**：sync_from_pipeline未实现、EVOLVES_TO仅写PG不写Neo4j、闭环Step3永远降级
4. **运行时Bug**：snapshot_at列名错误、内存存储重启丢失、Cypher注入风险
5. **架构债务**：Home.vue 1316行上帝页面、3套颜色系统、6个死端点

**Target capabilities:**
- 所有14个页面功能完整闭环，无死按钮/空状态/模拟数据
- 后端所有API返回真实数据，无硬编码Profile/模拟趋势
- 数据流端到端贯通：抽取→图谱→匹配→演化→质量→管理
- 前端样式统一，使用design tokens
- 赛题5大核心功能+2项创新点全部可演示

## Validated Capabilities (v1.0 baseline)

- 后端 FastAPI + Pydantic + SQLAlchemy(异步) + Neo4j + Chroma + Redis
- 5 阶段 DAG 流水线架构（crawl → dedup ∥ clean → import → graph_sync）
- Celery 异步任务调度 + SSE 实时事件推送
- 24 张 PostgreSQL 表已迁移
- 真实种子数据：52 岗位 / 655 技能 / 82 知识领域 / 61 EVOLVES_TO
- 前端 Vue 3 + Element Plus + Pinia + ECharts + G6 + 3D Force Graph
- 14 个页面路由，8 个核心页面浏览器QA通过
- JD抽取F1=92.06%，匹配准确率100%(20/20 Golden Set)
- 后端测试覆盖率65.43%，CI 4/4全绿

## Key Decisions

- **DEC-001**: 功能闭环优先 — 先修复所有功能缺失和Bug，确保业务闭环，再考虑架构重构
- **DEC-002**: 6 Phase串行 — P1核心Bug→P2后端硬编码→P3前端功能→P4数据流→P5样式统一→P6架构重构
- **DEC-003**: Brownfield模式 — 不重写已有架构，仅做修复/补全/重构
- **DEC-004**: API/DB仅允许追加字段，不删不改类型（死端点除外）
- **DEC-005**: 赛题核心功能优先 — 5大功能+2创新点必须可演示
- **DEC-006**: Home.vue重构延后到Phase 6 — 先确保功能可用，再优化架构

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
