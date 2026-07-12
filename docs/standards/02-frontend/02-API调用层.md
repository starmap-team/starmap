# API 调用层 规范文档

## 1. 模块概述

**职责定位**：前端与后端 `starmap-contracts/openapi.yaml` 之间的 HTTP 通信层，负责请求/响应拦截、类型安全封装、全局错误处理及加载状态管理。

**核心目标**：
- 统一所有后端 API 调用的基础配置（baseURL、timeout、headers）
- 提供类型安全的 API 客户端（`typedGet` / `typedPost`），与 OpenAPI Schema 对齐
- 实现全局 loading 条、网络状态监听、HTTP 错误友好提示
- 401 认证过期时通过事件总线通知路由层跳转登录页

**在系统中的位置**：
- 上游：`starmap-contracts/openapi.yaml`（契约定义）、`vite.config.ts`（代理配置）
- 下游：所有 `stores/`（业务状态管理）、部分 `composables/`（直接数据获取）
- 注意：当前 store 普遍直接使用 `request.ts`，`client.ts` 的 `typedGet/typedPost` 尚未完全推广

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `frontend/src/api/request.ts` | 145 | 核心 axios 实例：拦截器、loading 条、错误处理、网络监听 | `request` (default export) |
| `frontend/src/api/request.improved.ts` | 163 | **已废弃** — request.ts 的候选替代实现（X-Request-ID、activeRequests Set、后端 detail 字段优先） | `request` (default export, @deprecated) |
| `frontend/src/api/client.ts` | 98 | 类型安全 API 客户端：基于 openapi-typescript 生成的 `paths` 类型封装 typedGet/typedPost | `api` 对象、`request` (re-export) |
| `frontend/src/api/schema.ts` | 4029 | OpenAPI Schema 类型定义：由 `openapi-typescript` 从 `starmap-contracts/openapi.yaml` 自动生成 | `paths`、`components`、`operations` 等类型 |

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  starmap-contracts/openapi.yaml (4496行, 93路径, 102操作)     │
│  └── openapi-typescript → schema.ts (4029行类型定义)        │
├─────────────────────────────────────────────────────────────┤
│  client.ts                                                  │
│  ├── typedGet<P extends keyof paths>                        │
│  ├── typedPost<P extends keyof paths>                         │
│  └── api = { health, extractJd, extractResume, ... }        │
├─────────────────────────────────────────────────────────────┤
│  request.ts (当前主要使用)                                    │
│  ├── axios.create({ baseURL: '/api/v1', timeout: 30000 })    │
│  ├── 请求拦截器: showLoading() → DOM loading 条             │
│  ├── 响应拦截器: hideLoading() + 错误处理                     │
│  ├── 网络监听: offline/online ElNotification                │
│  └── 401 → dispatchEvent('auth:unauthorized')               │
├─────────────────────────────────────────────────────────────┤
│  request.improved.ts (废弃，无引用)                           │
│  ├── X-Request-ID 生成与管理                                │
│  ├── activeRequests Set 替代 DOM 计数器                     │
│  └── 优先读取后端 detail 字段                                 │
└─────────────────────────────────────────────────────────────┘
```

### 数据流向

```
Store/Component → request.get/post(url, data) → Axios → /api/v1/* (Vite proxy) → Backend
                      ↓
                拦截器处理 loading + 错误提示
                      ↓
                401 → window.dispatchEvent('auth:unauthorized')
                      ↓
                router/index.ts 监听 → 跳转 /login
```

## 4. 接口规范

### 4.1 request.ts 导出

```typescript
import request from '@/api/request'

// request 是配置好的 AxiosInstance
// 响应拦截器已提取 resp.data，因此返回值直接是响应体（非 AxiosResponse）
request.get(url: string, config?: AxiosRequestConfig): Promise<any>
request.post(url: string, data?: any, config?: AxiosRequestConfig): Promise<any>
```

### 4.2 client.ts 导出

```typescript
import { api, request } from '@/api/client'

// 类型安全请求（基于 schema.ts 的 paths 类型）
async function typedGet<P extends string>(
  url: P,
  params?: Record<string, unknown>
): Promise<ResponseBody<P, 'get'>>

async function typedPost<P extends string>(
  url: P,
  body?: RequestBody<P, 'post'>
): Promise<ResponseBody<P, 'post'>>

// 便捷方法（推荐新代码使用）
const api = {
  health: () => typedGet('/health'),
  extractJd: (body: RequestBody<'/extract/jd', 'post'>) => typedPost('/extract/jd', body),
  extractResume: (body: RequestBody<'/extract/resume', 'post'>) => typedPost('/extract/resume', body),
  listPositions: (params?: Record<string, unknown>) => typedGet('/positions', params),
  getPositionDetail: (positionId: string) => typedGet(`/positions/${positionId}`),
  runMatch: (body: any) => typedPost('/match/position', body),  // 待迁移到精确类型
  getEvolutionTrends: (params?: Record<string, unknown>) => typedGet('/evolution/trends', params),
  getEvolutionPaths: (positionId: string) => typedGet(`/evolution/paths/${positionId}`),
  getQualityDashboard: () => typedGet('/quality/dashboard'),
  getGraphOverview: () => typedGet('/graph/overview'),
  getPipelineStatus: (runId: string) => typedGet(`/pipeline/runs/${runId}`),
} as const
```

### 4.3 schema.ts 类型（节选）

```typescript
// 由 openapi-typescript 自动生成，禁止手动修改
export interface paths {
  '/health': { get: { responses: { 200: { content: { 'application/json': { status: string; version: string; env: string } } } } } }
  '/extract/jd': { post: { requestBody: { content: { 'application/json': { jd_text: string } } }; responses: { ... } } }
  // ... 93 路径 × 多方法
}
```

## 5. 编码规范（本模块特有）

### 5.1 请求方式选择
- **新代码优先使用 `client.ts` 的 `api.*` 方法**，获得完整的类型推断
- **存量代码使用 `request.ts`**，迁移到 `client.ts` 需逐步进行
- **禁止**在业务代码中直接创建新的 `axios.create()` 实例

### 5.2 错误处理约定
- `request.ts` 拦截器已将 HTTP 错误转换为友好中文提示（`ElMessage` / `ElNotification`）
- 业务代码中 **不需要** 再包裹 `try/catch` 处理通用 HTTP 错误（400/403/404/500 等）
- 业务代码 **需要** 处理业务逻辑错误（如后端返回 200 但 `success: false`）
- 401 特殊处理：派发 `auth:unauthorized` 事件，由路由层统一跳转

### 5.3 Loading 管理
- 全局 loading 条通过 DOM 计数器实现（`loadingCount` + `loadingEl`）
- 多个并发请求共享同一个 loading 条，最后一个请求完成后移除
- 孤儿 DOM 清理：响应拦截器在 `loadingCount === 0` 时执行 `querySelectorAll('.global-loading-bar').forEach(el => el.remove())`

### 5.4 网络监听
- `offline` 事件：显示持久警告通知（`duration: 0`）
- `online` 事件：显示恢复成功通知，重置 `hasShownOffline` 标志

### 5.5 反模式
- **禁止**在 `request.ts` 中引入 `vue-router`（会导致 Pinia/Router 循环依赖）
- **禁止**在业务代码中重复实现错误提示（拦截器已统一处理）
- **禁止**直接修改 `schema.ts`（应修改 `openapi.yaml` 后执行 `npm run gen:api`）
- **禁止**使用 `request.improved.ts`（已废弃，无文件引用）

## 6. 测试规范

| 测试文件 | 覆盖范围 | 策略 |
|---------|---------|------|
| `frontend/src/api/__tests__/request.test.ts` (建议创建) | 拦截器逻辑、错误映射、loading 计数器 | mock axios + jsdom |
| `frontend/src/api/__tests__/client.test.ts` (建议创建) | typedGet/typedPost 类型约束、api 方法调用 | mock request.ts |

**覆盖率要求**：
- 错误状态码映射表覆盖（400/401/403/404/422/429/500/502/503/504）
- loading 计数器边界（0→1→2→1→0）
- 网络离线/恢复通知触发

**Mock 策略**：
- `axios.create` → `vi.mock('axios')`
- `ElMessage` / `ElNotification` → `vi.mock('element-plus')`
- `window.addEventListener` → jsdom 原生支持
- `schema.ts` 类型 → 无需 mock（编译时检查）

## 7. 变更管理

### 修改检查清单

- [ ] 修改 `request.ts` 时，是否同步更新 `request.improved.ts`（保持参考一致性）？
- [ ] 新增 API 端点时，是否在 `client.ts` 的 `api` 对象中添加对应方法？
- [ ] 新增 API 是否已更新 `starmap-contracts/openapi.yaml`？
- [ ] 更新 `openapi.yaml` 后是否执行了 `npm run gen:api` 重新生成 `schema.ts`？
- [ ] 类型变更是否影响 `client.ts` 中的 `RequestBody` / `ResponseBody` 推导？
- [ ] 错误码映射表是否需要新增条目？

### 契约影响
- `schema.ts` 是 `openapi.yaml` 的派生文件，任何契约变更必须通过 `openapi.yaml` → `gen:api` 流程
- `client.ts` 中的路径字符串必须与 `openapi.yaml` 的 `paths` 键名完全一致（大小写敏感）
- `api.runMatch` 当前使用 `body: any`，迁移到精确类型时需与后端确认请求体 schema

### 迁移要求
- 从 `request.ts` 迁移到 `client.ts`：将 `request.get('/positions')` 替换为 `api.listPositions()`
- 迁移后删除 `as any` 类型断言
- 批量迁移建议按 store 逐个进行，避免一次性大规模改动
