# 前端 API 调用层规范

## 事实源

- Base path：`src/config/apiBase.ts`。
- Axios 基础客户端：`src/api/request.ts`。
- 类型化客户端：`src/api/client.ts`（手写包装，消费生成的 `schema.ts`）。
- 契约：`starmap-contracts/openapi.yaml`。
- 运行时错误/Schema：`src/validation/`。

## 规则

- 新调用优先使用 OpenAPI 生成类型；缺失便利方法时扩展 typed client，而不是复制响应 interface。
- request 层统一处理 access token、refresh 去重、loading 和错误消息。
- API 字段保持 `snake_case`。
- 需要结构监控的 Store 调用 `useResponseValidation()`；DEV 告警不修改业务值。
- 上传、SSE 和普通 JSON 请求使用各自正确的传输边界。
- 不恢复已删除的 `request.improved.ts` 或第二个 base URL fallback。

## 同步

```bash
cd frontend && npm run gen:api && npm run typecheck
```
