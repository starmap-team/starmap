# StarMap 前端

Vue 3 + TypeScript + Element Plus + Pinia + ECharts + AntV G6 应用。

## 启动

```bash
cd frontend
npm install
npm run gen:api
npm run dev
```

或从仓库根运行 `docker compose -f docker-compose.dev.yml up -d frontend`。开发地址：<http://localhost:5173>。

## 命令

| 命令 | 作用 |
|---|---|
| `npm run dev` | Vite 开发服务器 |
| `npm run gen:api` | 从 OpenAPI 生成 `src/api/schema.ts` |
| `npm run typecheck` | Vue/TypeScript 类型检查 |
| `npm run lint` | ESLint |
| `npm run test` | Vitest |
| `npm run build` | 类型检查后构建生产包 |

## 数据边界

- `src/config/apiBase.ts` 是 API base path 的唯一来源，当前为 `/api/v1`。
- `src/api/request.ts` 负责 token、refresh、loading 和统一错误消息。
- `src/api/client.ts` 提供 OpenAPI 类型包装；迁移仍在进行，不假设所有 Store 已使用它。
- `src/validation/` 使用导出的 JSON Schema 做表单和响应校验。
- 当前应用不使用 MSW，也不存在 `src/mock/`；单元测试使用 Vitest，浏览器测试使用 Playwright 路由替身或真实后端。

## 结构约定

页面只做路由级编排；跨组件状态进入 Store；生命周期、SSE 和复杂交互进入 composable；可复用视图进入 components。API 字段保持后端的 `snake_case`，不做隐式 camelCase 转换。