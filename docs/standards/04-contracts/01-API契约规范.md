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