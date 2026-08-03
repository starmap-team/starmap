# CONFORMANCE — Module 1: 全景图谱 (Home)

**Phase 13 · Wave 1 · verified 2026-07-26**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/02-frontend/05-页面组件规范.md`、`docs/ontology/starmap-ontology-v1.md`、`docs/architecture/overview.md` |
| was-analyzed | `docs/archive/home-source-analysis.md` |
| is (live) | `frontend/src/pages/Home.vue` + `stores/graph.ts` + `HomeKpiStrip.vue` + `/api/v1/graph/overview` + PG + Neo4j |

## 符合项（已验证）
- **[CONFORM]** 图谱渲染：补 582 条 `REQUIRES` 关系后，`/graph/overview` 返回 12 领域 / 11 连接；Home 渲染 3D 力导向图（canvas 存在、工具栏「12 节点」、无 empty-hint）。KPI=12/56/257/11，**0 console error**。证据 `tests/e2e/investigations/ux/home_graph_rendered.png`。
- **[CONFORM]** 技能数口径：Home KPI 用 `graphStore.independentSkills`(=257)=PG/Neo4j distinct；API 字段 `total_skills=395` **未在前端呈现**（见 OPEN-LOW）。证据：`Home.vue:38-39`、`HomeKpiStrip.vue:62`。
- **[CONFORM]** KPI 数据源 tooltip 已加（`HomeKpiStrip.vue:24` 等）。
- **[CONFORM]** SSOT：Neo4j Position 56 = PG `position_records` 56；`/admin/data-truth` sync_health=ok。
- **[CONFORM]** 测试：`Home.spec.ts` 9/9。

## 偏移 / 待办
- **[FIXED · LOW→CONFORM (M6)]** `/graph/overview` 的 `total_skills/total_positions` 原为按域/KA 累加（`total_skills=395` ≠ distinct 257，歧义）。修复 `backend/app/services/graph_service.py`：`total_*` 一律取全局去重 `independent_*`，分组视图保留在 `domains[]`。**验证**：`total_skills` 395→**257**，`total_positions=56`，M6 conform=True，`domains` 仍 12。无测试断言旧值（相关单测针对 `graph_overview` 的另两个函数）。

## 结论
模块 1 在可见层 **符合**；唯一偏移为后端 latent 字段语义（LOW，不可见）。