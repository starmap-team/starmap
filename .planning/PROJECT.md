# StarMap Project — 全系统二次开发

**Last updated:** 2026-07-09
**Branch:** main
**Status:** Active development — 真实数据切换

## What This Is

StarMap（星图）是一个**人才能力星云导航系统**，面向IT岗位的技能图谱与匹配诊断平台。核心产品价值：把IT行业海量JD与求职者的技能图谱对齐，让求职者看到自己当前的"能力星云"，并通过可信的演化趋势/匹配诊断/学习路径推荐，找到迈向目标岗位的最短路径。

系统的差异化点：
- **可追溯**：每个技能/匹配/推荐都有源（source）、时间（temporal）、交叉验证（cross-source）三重可信度
- **反幻觉**：仅采纳 ≥3 个独立来源、≥4 周时间跨度、跨源一致的技能作为"已验证"
- **可演化**：跟踪技能/岗位的兴衰周期，识别新兴技能（emerging/rising/declining）

## Current Milestone: v2.1 真实数据切换

**Goal:** 将 StarMap 从演示/假数据模式切换为真实数据模式，确保前端展示和后端处理全部使用真实 API 和数据库数据。

**核心问题诊断：**
1. **前端全量 Mock**：MSW 拦截所有 API 请求返回硬编码假数据，默认启用；图表无数据时显示 placeholder
2. **后端 Demo 种子**：6+ 个 `seed_*_demo.py` 脚本填充假数据；Review Queue 为空时 auto-seed；`/reset-demo` 端点重置为假数据
3. **LLM 未配置**：MiMo/DeepSeek/星火 API Key 全部为空，LLM 降级链无可用供应商
4. **爬虫未实跑**：Pipeline 从未被触发真实采集，数据库中无爬取数据

**Target capabilities:**
- 前端所有页面走真实后端 API，无 MSW 拦截、无 placeholder 图表
- 后端无 demo/auto-seed 逻辑，所有数据来自真实爬取或 LLM 抽取
- 至少一个 LLM 供应商可用，降级链正常工作
- Pipeline 可触发端到端真实数据采集（crawl → dedup → clean → import → graph_sync）

## Validated Capabilities (v2.0 baseline)

- 后端 FastAPI + Pydantic + SQLAlchemy(异步) + Neo4j + Chroma + Redis
- 5 阶段 DAG 流水线架构（crawl → dedup ∥ clean → import → graph_sync）
- Celery 异步任务调度 + SSE 实时事件推送
- 24 张 PostgreSQL 表已迁移
- 真实种子数据：52 岗位 / 655 技能 / 82 知识领域 / 61 EVOLVES_TO
- 前端 Vue 3 + Element Plus + Pinia + ECharts + G6 + 3D Force Graph
- 14 个页面路由，8 个核心页面浏览器QA通过
- JD抽取F1=92.06%，匹配准确率100%(20/20 Golden Set)
- 后端测试覆盖率62%，CI 4/4全绿
- vue-tsc 0 errors, eslint 0 errors, ruff all passed
- 硬编码颜色 0, 运行时Bug 0, 内存存储 0

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
