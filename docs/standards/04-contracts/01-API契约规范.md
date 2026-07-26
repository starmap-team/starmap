# API 契约规范

## 权威来源

`starmap-contracts/openapi.yaml` 定义公共路径、方法、Schema 和安全；后端 API 模型位于 `backend/app/schemas/`，JSON Schema 位于 `starmap-contracts/schemas/`，前端类型由 OpenAPI 生成。

## 变更流程

1. 修改 OpenAPI 并说明兼容性。
2. 修改后端集中 Schema、服务和路由。
3. 导出 JSON Schema。
4. 运行前端 `npm run gen:api`。
5. 更新 Store/client 运行时校验与测试。
6. 发布型变化更新 contracts CHANGELOG。

## 规则

- 字段使用 `snake_case`，必填/nullable/默认值语义一致。
- 每个 Field 有 description 和合理约束。
- 错误响应统一 `{detail, code, timestamp, fields?}`。
- 删除/重命名已发布路径或字段需要明确版本与迁移策略。
- OpenAPI、Pydantic、JSON Schema、前端类型不能独立演化。
- 历史 contract audit 已归档，不作为变更日志。

## 验证

```bash
python starmap-contracts/validate.py
cd backend && poetry run python ../scripts/export_json_schemas.py
cd ../frontend && npm run gen:api && npm run typecheck
```

## 数据与接口一致性强制规范（Phase 13 审计沉淀 · MUST）

> 以下条目由跨端一致性审计（设计 vs 多端真实实现）沉淀，**全部为必修项**；违反即视为契约/规范不符合，须在 Phase 13 各模块闭环中修复，并以三层证据（页面截图 + API 返回 + DB/图查询）佐证。

- **M1 路径参数类型保真**（源 `04-contracts` + `01-backend/02`）：路径参数为实体 id 时必须为 UUID；前后端测试夹具**禁止**使用 int / 伪 id（如 `/1`、`src-42`），须用 UUID 形态，否则对真实解析路径产生虚假信心。
- **M2 错误码语义不混淆**（源 `04-contracts` + `01-backend/06`）：`404` 仅用于“资源真不存在”；“资源存在但暂无可用画像/数据”须返回 `200` + 解释字段或专用业务 code，**禁止**与 not-found 混用。
- **M3 可选依赖必须降级**（源 `01-backend/06` + 架构总纲“每阶段独立降级”）：可选外部依赖（如向量库 Chroma）不可用时必须降级到次级算法并返回有效结果，**禁止**将其异常升级为致命错误致整接口 500；须负缓存避免重复失败尝试。
- **M4 评估指标真实性**（源 `05-evaluation` + `01-backend/08`）：无评估基线（golden/标注集为空）时，precision/recall/F1 必须置 `baseline_available=false` 且 `warning_level` **不得为 red**（用 gray/“未评估”），并附 `explanation`；**禁止**把“未评估”呈现为“质量差”。
- **M5 零数据空态与可追溯**（源 `02-frontend/05` + `01-backend/09`）：计数为 0 的指标/列表须有明确“未采集/待同步/无数据”空态文案，**禁止**暗示存在数据；KPI 数字须可追溯单一数据源，歧义口径须加 tooltip/解释。
- **M6 多端口径单一性**（源 `04-contracts` + 架构 SSOT：PG 权威 / Neo4j 只读投影）：同一业务量在不同端点/页面须同口径或显式标注口径差异；聚合字段（如按域累加的技能数）**不得**与去重计数同名混用，须命名/文档化区分。
- **M7 verify-first 闭环**（源 `governance/documentation` + 本里程碑方法）：任一一致性修复须附三层证据方可记为闭环；仅改代码未验证者状态保持 **OPEN**，不得标完成。