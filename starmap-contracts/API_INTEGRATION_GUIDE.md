# StarMap API 联调指南

> 状态：活文档
> 最近核对：2026-07-24

## 契约优先流程

1. 修改 `starmap-contracts/openapi.yaml`。
2. 修改 `backend/app/schemas/`、服务和路由。
3. 导出 `starmap-contracts/schemas/*.schema.json`。
4. 在 frontend 运行 `npm run gen:api`。
5. 更新 typed client/Store、运行时响应校验和测试。
6. 发布兼容性变化时更新 `CHANGELOG.md`。

## URL

浏览器和前端统一使用 `/api/v1` base path。开发 Vite 把 `/api` 代理到后端并保留路径；后端将业务 router 挂在 `/api/v1`。不要在调用点追加第二个 `/api/v1`。

## 字段与错误

- 请求/响应字段使用 `snake_case`。
- 后端错误：`{detail, code, timestamp, fields?}`。
- 422 字段错误通过统一 validation handler 返回。
- 前端错误消息优先服务端 `detail` 和字段错误。
- API 认证使用 Bearer access token；refresh 由基础 request 层去重处理。

## 生成与校验

```bash
python starmap-contracts/validate.py
cd backend && poetry run python ../scripts/export_json_schemas.py
cd ../frontend && npm run gen:api && npm run typecheck
```

后端路径一致性由 CI 比较 FastAPI OpenAPI 与契约。前端 `schema.ts` 是生成文件，不手工修改。

## 新端点检查

- OpenAPI 有 method/path、security、请求/响应和错误 Schema。
- Pydantic Field 有 description 与约束。
- 路由只调用服务，不内联 API model。
- Store/client 使用生成类型，DEV 响应校验已接入。
- 单元/契约测试覆盖成功和错误路径。

历史契约审计已移至 `docs/archive/audits/contract-audit-2026-07-10.md`，仅用于追溯当时问题。