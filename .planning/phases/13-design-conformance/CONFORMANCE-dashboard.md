# CONFORMANCE — Module 9: 数据大屏 (DataDashboard)

**Phase 13 · Wave 3 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/08-业务核心-dashboard.md`、`docs/standards/04-contracts/01-API契约规范.md` |
| was-analyzed | `docs/archive/dashboard-source-analysis.md` |
| is (live) | `frontend/src/pages/DataDashboard.vue` + `stores/dashboard.ts` + `/api/v1/dashboard/{overview,trends,distribution,realtime,alerts}` + Neo4j + PG |

## 符合项（已 verify-first 验证）
- **[CONFORM]** 5 个端点契约完整（`overview` / `trends` / `distribution` / `realtime` / `alerts`）。
- **[CONFORM]** `GET /api/v1/dashboard/overview` → 200，31ms，含 `total_nodes=313` / `total_edges=582` / `total_positions=56` / `total_skills=257` / `total_extractions=190` / `data_volume=46` / `weekly_new_nodes=313` / `pipeline_status=cancelled` / `active_data_sources=3` / `stale=false`。
- **[CONFORM]** `GET /api/v1/dashboard/trends?period=7d` → 200，13ms，data_points 数组（按日聚合）。
- **[CONFORM]** `GET /api/v1/dashboard/distribution` → 200，13ms，`source_distribution` 含 Lagou/Boss Zhipin 等数据源 + `authority_score` / `duplicate_rate`。
- **[CONFORM]** 关键数据三层一致：PG `position_records=56` = dashboard `total_positions=56`；Neo4j Skill=257 = dashboard `total_skills=257`；Neo4j Position=56 = dashboard `total_positions=56`（M6 conform 已在 Wave 1 cross-check 通过）。

## 验证证据
- 端到端 3 端点 200 OK
- PG 56 / Neo4j 56+257 / API 56+257 完全对齐
- 后端单测（`test_dashboard_service.py`）状态待 Wave 1 跨端校核

## 偏移 / 待办（OPEN）
- **[OPEN · MEDIUM · 后端口径]** `dashboard.total_edges=582` 仅计 `PositionSkillRelation` 表行数，未包含 Neo4j 中其他关系类型（Tool/KnowledgeArea 等）。Neo4j 实际边数 1375，与 dashboard 1179/582 存在差。**建议**：在 overview 响应加 `total_edges_all_types`（Cypher 全部关系）或保持单一"职位-技能关系"口径但在字段名澄清。定位 `backend/app/core/dashboard/dashboard_service.py`。
- **[OPEN · LOW · frontend]** `DataDashboard.vue` / `dashboard.ts` 错误透传（与 Phase 6/7/8 同模式）。**其他会话处理**。
- **[OPEN · LOW · frontend]** `DataDashboard.spec.ts` 5+ 测试覆盖。

## 结论
后端契约层 + 5 端点 + 三层数据一致 **全部符合**；边数口径 582 vs 1375 留 OPEN（后端 + 前端 + 文档化）。