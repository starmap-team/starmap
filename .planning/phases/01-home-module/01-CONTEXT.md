# Phase 1 — 全景图谱模块 CONTEXT.md

> Phase ID: `01-home-module` · Milestone: v5.0 · Status: executing  
> Blueprint: `plans/panorama-graph-views-blueprint.md` (8 步)

## Objective

让 Home.vue 全景图谱从"3 视图同源"演进为"4 视图真实化"——**领域视图 ≠ 技术栈视图**、**级别视图有初级节点**、**新增热度视图**。全程 verify-first（curl 单测 + Playwright 截图 + 0 console error）。

## User-Visible Outcome

- 领域视图：13 大行业（互联网/AI/金融/医疗…），按 industry 聚类，颜色与现有 ts-* 完全区分
- 技术栈视图：12 ts-* 节点（按 tech_stack 分类），**与领域视图节点集完全不同**
- 级别视图：3 个域泡（lv-junior 0/0 占位 + lv-mid 45 岗 + lv-senior 11 岗），3 视图全维度
- 热度视图：高频需求技能按频次热力图着色（红/黄/蓝 3 档）

## Hard Constraints（spec 对标）

- `docs/星图-项目设计文档v2.0.md:713-718` — 4 视图显式要求
- `docs/ontology/starmap-ontology-v1.md:53` — 领域→子领域→技能 三层树
- `docs/星图-项目设计文档v2.0.md:390-396` — KnowledgeArea 节点属性（name/description/parent_area/color）
- `docs/星图-项目设计文档v2.0.md:439-450` — Skill→KA 必属关系 + 12 个 KA 种子
- `docs/星图-项目设计文档v2.0.md:368` — Position.level 字段
- `docs/standards/04-contracts/01-API契约规范.md` — M1 路径参数保真 / M2 错误语义不混淆 / M3 可选依赖降级 / M4 评估基线 / M5 零数据空态 / M6 口径单一 / M7 verify-first 闭环

## Soft Constraints（已存代码约束）

- Phase 5 架构修复：Neo4j 是 PG 投影，canonical_id 对齐
- 已有 `_prune_connections` 后端 helper（Phase 13 R1 修复）— 4 端点复用
- 已有前端 `visibleEdges` 按 `domains.id` 过滤（Phase 13 R2 防御）
- 已有 `Graph3D.vue` 命名空间检测 + 重建（Phase 13 R3）
- 已有 `_lastNamespace` + `linksForNodes` 防御性过滤（Phase 13 R4）
- `M6 闭环（Home total_skills）`：graph_service.py `total_*` 改取 `independent_*` — 单测已有 baseline 56/257/582

## Design Decisions

- **Step 1 选 industry 归一（13 大行业）而非重新设计维度** → 与 spec 业务层 12 行业对齐，与 tech_stack 维度天然互斥
- **Step 5 用 `lv-junior` 0/0 占位而非虚构数据** → 数据完整性 > KPI 美观
- **Step 3 KA 种子幂等 (`MERGE`)** → 重复跑无副作用
- **后端 4 端点共享 helper**（`_prune_connections` + `_fetch_independent_counts`）→ 不重复实现

## Out of Scope（独立 PR/Phase）

- Phase B industry 归一表（细粒度）— 独立 phase
- G6 → 3d-force-graph 切换重构 — 独立 phase
- 领域→子领域→技能 3 层树 UI（Home 的二级下钻）— Phase D
- 热度视图 KPI 卡片动态化（KPI 4 套）— Step 6 范围内

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| industry 字段 PG 中值为空/脏数据 → domain 视图空 | Medium | High | Step 1 先 SELECT DISTINCT 看分布；空 industry 用"未分类"占位 |
| KA 12 节点种子与现有 Position.industry 不匹配 | Low | Medium | Step 3 用 industry 软关联（非硬映射），缺挂的归"未分类" |
| `lv-junior` 兜底在 spec 上违规（虚构） | None | None | 数据完整性 > spec 表面合规；0/0 占位是 spec 列 12 的最佳解 |
| 前端 store 扩展破坏现有 3 视图 | Low | Medium | Step 6 用 additive 扩展 (`'domain' | 'tech_stack' | 'level' | 'heat'`)，现有消费者只识别前 3 值 |
| 4 视图切换性能 | Low | Low | 每次切换仅重 fetch 一次，缓存 + debounce 已有 |

## Success Criteria

1. `curl /api/v1/graph/overview?group_by=domain` 返回的 domains 集合 ≠ `group_by=tech_stack` 返回的（spec 排他性）
2. `curl /api/v1/graph/overview?group_by=level` 返回 3 个域泡（lv-junior 0/0 占位 + lv-mid 45 + lv-senior 11）
3. `curl /api/v1/graph/overview?group_by=heat` 返回频率热力图数据
4. Home.vue 4 视图可正常切换，KPI 卡片随视图动态变化
5. 0 console error，4 张截图互不重复
6. 后端 4 端点 + 1 单测文件 = 测试覆盖 ≥ 80%

## Reference Map

- 现状：`01-01-PLAN.md`（原 phase 1 执行计划）+ `01-01-SUMMARY.md` + `01-RESEARCH-AFTER.md`
- 设计：`DESIGN-graph-views.md`（图谱视图设计）
- 审计：`01-UI-REVIEW.md`（6 栏分级报告 + 缺陷清单）
- 蓝图：`plans/panorama-graph-views-blueprint.md`（8 步执行计划）
- 上下文：本文件 `01-CONTEXT.md`（顶层约束 + 决策）

*Generated 2026-07-27 by /gsd-plan-phase 1. Phase 1 已完成第一轮（Home 源码分析 + 联调 + 测试 + summary），本轮扩展 4 视图真实化（蓝图 Step 1-8）。*