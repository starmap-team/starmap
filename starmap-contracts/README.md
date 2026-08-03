# StarMap Contracts

`starmap-contracts/` 是跨后端、前端和数据流程的 API 契约真相源。

## 内容

| 路径 | 作用 |
|---|---|
| `openapi.yaml` | OpenAPI 路径、方法、请求、响应和安全定义 |
| `schemas/` | 从后端 Pydantic 模型导出的 JSON Schema |
| `models/` | 共享模型与兼容定义 |
| `graph_cypher/` | 跨模块复用的 Cypher 契约/模板 |
| `validate.py` | 契约语法和一致性检查 |
| `CHANGELOG.md` | 已发布契约变更记录 |
| `API_INTEGRATION_GUIDE.md` | 联调流程和示例 |

## 变更顺序

1. 修改 `openapi.yaml`。
2. 修改后端集中 Schema 和实现。
3. 导出 `schemas/*.schema.json`。
4. 生成前端 `src/api/schema.ts`。
5. 更新请求/响应运行时校验和测试。
6. 更新 CHANGELOG（发布的兼容性变化）。

## 验证

```bash
python starmap-contracts/validate.py
cd backend && poetry run python ../scripts/export_json_schemas.py
cd ../frontend && npm run gen:api && npm run typecheck
```

历史契约审计位于 `docs/archive/audits/`，不能代表当前契约状态。