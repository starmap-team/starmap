# Phase 9: 前端关闭 Mock - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

关闭 MSW Mock 拦截、删除 placeholder 图表、配置 Vite 代理、清理 mock 文件，确保前端走真实后端 API。这是 v2.1"真实数据切换"的第二层：让前端不再使用假数据，所有 API 请求走真实后端。**不涉及**后端 demo 清理（Phase 8 已完成）、不涉及 Pipeline 实际采集（Phase 10）、不重写已有架构（DEC-003）、不新增前端功能。

前置状态（**不在本阶段重做**）：
- ✅ Phase 8 D-03: 已删除 `useAdminReset.ts`、`resetToDemo()` action、Admin.vue 重置按钮 — 前端 demo 协调清理已完成
- ✅ Phase 8 D-05: `/health/detail` 端点已添加 — 前端可检测后端服务状态
- ✅ `vite.config.ts:17-21` — `/api` 代理已存在，target 为 `VITE_API_BASE_URL || http://localhost:8000`
- ✅ `docker-compose.dev.yml:89` — 已设 `VITE_USE_MSW=false`
- ✅ `request.ts` — baseURL 为 `/api/v1`，与 vite proxy 匹配
- ✅ 18 个组件已有 `custom-empty` 空状态样式模式（`.empty-icon-wrapper` + `.empty-text` + `.empty-hint-text`）

本阶段 4 个灰色地带（仅实现决策，不重做）：
1. MSW 关闭策略（彻底删除 vs 保留开关 vs 删调用保留依赖）
2. 空状态展示方式（隐藏图表 vs 空状态组件 vs 保留占位改文案）
3. 环境变量与代理确认（创建 .env.development vs 用代码默认值）
4. msw 依赖清理（保留 vs 移除）

</domain>

<decisions>
## Implementation Decisions

### G1 MSW 关闭策略（MSW-01/04）
- **D-01:** **删除 enableMocking() 调用和 mock/ 目录，保留 msw 在 devDependencies** — 从 `main.ts` 删除 `import { enableMocking } from './mock/msw-browser'` 和 `await enableMocking()` 调用；删除 `frontend/src/mock/` 目录（handlers.ts + msw-browser.ts）；删除 `frontend/public/mockServiceWorker.js`。保留 `msw` 在 `package.json` devDependencies 中以备未来可能需要 mock 新 API。理由：彻底清除运行时 mock 拦截，但保留依赖避免未来重新安装和 init 的开销

### G2 空状态展示方式（MSW-02）
- **D-02:** **删除 getPlaceholder* 函数，无数据时显示 custom-empty 空状态组件** — 移除 `useDashboardCharts.ts` 中 4 个 `getPlaceholder*` 函数（Pie/Treemap/Trend/Radar），无数据时返回 null/undefined 触发父组件显示空状态。使用项目已有的 `custom-empty` CSS 模式（`.empty-icon-wrapper` + `.empty-text` + `.empty-hint-text`），与 18 个现有组件保持一致。理由：placeholder 半透明占位图给用户"有数据但很淡"的错觉，空状态组件明确告知"暂无数据"更诚实

### G3 环境变量与代理确认（MSW-01/03）
- **D-03:** **创建 .env.development 文件，补全 env.d.ts 声明** — 创建 `frontend/.env.development` 固化 `VITE_USE_MSW=false` + `VITE_API_BASE_URL=http://localhost:8000`；在 `frontend/src/env.d.ts` 的 `ImportMetaEnv` 接口中添加 `VITE_USE_MSW` 声明。理由：本地开发默认走真实 API，环境变量显式声明避免隐式依赖；Docker Compose 已有 `VITE_USE_MSW=false` 覆盖，.env.development 仅影响本地开发

### G4 msw 依赖清理（MSW-04）
- **D-04:** **保留 msw 在 devDependencies，不修改 package.json** — 与 D-01 一致，仅删除运行时 mock 代码，保留依赖以备未来。不重新生成 lockfile

### Claude's Discretion
- `main.ts` 删除 enableMocking 后的 bootstrap() 函数简化（是否保留 async/await 结构 — 建议保留，未来可能需要其他异步初始化）
- `useDashboardCharts.ts` 删除 getPlaceholder* 后，computed 返回 null 时的父组件 DataDashboard.vue 处理逻辑（需检查 v-chart 组件对 null option 的容错性）
- custom-empty 空状态的具体文案（建议："暂无数据" + 提示"数据加载中或暂无记录"）
- 是否同时清理 `env.d.ts` 中 `VITE_USE_MSW` 在删除 enableMocking 后是否仍有必要（建议保留 — msw 依赖仍在，未来可能重新启用）

### 验证指标（硬性）
- **D-05:** **0 MSW 拦截** — `main.ts` 中无 enableMocking() 调用，浏览器 Network 面板无 MSW Service Worker 注册
- **D-06:** **0 placeholder 图表** — `useDashboardCharts.ts` 中无 `getPlaceholder*` 函数，后端无数据时显示空状态
- **D-07:** **Vite proxy 到后端** — `vite.config.ts` 有 `/api` → `http://localhost:8000` 代理规则（已存在，确认即可）
- **D-08:** **无 mock 目录** — `frontend/src/mock/` 目录和 `frontend/public/mockServiceWorker.js` 已删除
- **D-09:** **`vue-tsc --noEmit` 和 `eslint` 通过** — 删除代码后无类型/引用错误

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` - 项目定义、v2.1 真实数据切换目标、DEC-001~006、DEC-011
- `.planning/REQUIREMENTS.md` §MSW-01~04 - 4 个需求（前端关闭 Mock）
- `.planning/ROADMAP.md` §Phase 9 - 成功标准、关键文件
- `.planning/STATE.md` - 当前状态、DEC-001~011 已锁定决策

### 前序阶段决策（不重做）
- `.planning/phases/08-backend-cleanup/08-CONTEXT.md` - Phase 8 后端清理决策（D-03 前端 demo 协调清理已完成、D-05 /health/detail 已添加）
- `.planning/phases/04-dataflow/04-CONTEXT.md` - Phase 4 数据流决策（D-08 真实计算为准，不引入 mock，与 v2.1 目标一致）

### MSW 与 Mock 清理目标（核心改造）
- `frontend/src/main.ts:15,22` - `import { enableMocking }` + `await enableMocking()` 调用（D-01 删除）
- `frontend/src/mock/msw-browser.ts` - MSW 浏览器初始化（D-01 删除整个文件）
- `frontend/src/mock/handlers.ts` - 8 个 API mock handler（D-01 删除整个文件）
- `frontend/public/mockServiceWorker.js` - MSW Service Worker 文件（D-01 删除）

### Placeholder 图表清理目标（MSW-02）
- `frontend/src/composables/useDashboardCharts.ts:66-76` - `getPlaceholderPie()` 函数（D-02 删除）
- `frontend/src/composables/useDashboardCharts.ts:136-155` - `getPlaceholderTreemap()` 函数（D-02 删除）
- `frontend/src/composables/useDashboardCharts.ts:254-283` - `getPlaceholderTrend()` 函数（D-02 删除）
- `frontend/src/composables/useDashboardCharts.ts:345-367` - `getPlaceholderRadar()` 函数（D-02 删除）
- `frontend/src/composables/useDashboardCharts.ts:21,82,160,288` - 4 处 `return getPlaceholder*()` 调用（D-02 改为返回 null）

### 环境变量与代理（MSW-01/03）
- `frontend/vite.config.ts:17-21` - `/api` 代理配置（已存在，确认即可）
- `frontend/src/env.d.ts:49-53` - `ImportMetaEnv` 接口（D-03 补充 `VITE_USE_MSW` 声明）
- `frontend/.env.development` - 需创建（D-03）
- `docker-compose.dev.yml:89` - 已设 `VITE_USE_MSW=false`（不修改）

### 空状态组件模式（D-02 参考）
- `frontend/src/App.vue:530-540` - `.custom-empty` / `.empty-icon-wrapper` / `.empty-text` / `.empty-hint-text` CSS 定义
- `frontend/src/components/CareerPathGraph.vue:159-183` - custom-empty 使用示例
- `frontend/src/components/CompetitivenessChart.vue:108-135` - custom-empty 使用示例
- `frontend/src/pages/PipelineAnalysis.vue:242` - `el-empty` 使用示例
- `frontend/src/components/AlertList.vue:84` - `empty-text` 属性使用示例

### API 请求层（确认无需修改）
- `frontend/src/api/request.ts` - axios 实例，baseURL `/api/v1`，与 vite proxy 匹配

### 测试与验证
- `frontend/package.json` - msw 依赖（D-04 保留不删）
- `frontend/tsconfig.json` / `frontend/tsconfig.app.json` - TypeScript 配置（确认删除后无引用错误）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `custom-empty` CSS 模式（App.vue:530-540）— D-02 空状态组件复用此样式，18 个组件已验证可用
- `el-empty` Element Plus 组件 — PipelineAnalysis.vue 已使用，可作为备选
- `vite.config.ts` proxy 配置 — 已存在 `/api` → `localhost:8000`，无需新增
- `request.ts` axios 实例 — baseURL `/api/v1` 已与 proxy 匹配，无需修改

### Established Patterns
- **空状态 pattern:** `custom-empty` div 包裹 `.empty-icon-wrapper` + `.empty-text` + `.empty-hint-text`，v-if/v-else 切换（18 个组件已确立）
- **环境变量 pattern:** `ImportMetaEnv` 接口声明 + `.env.development` 文件（VITE_API_BASE_URL 已有此模式，D-03 沿用）
- **Vite proxy pattern:** `server.proxy` 配置 + `VITE_API_BASE_URL` 环境变量 fallback（vite.config.ts 已确立）

### Integration Points
- `frontend/src/main.ts` — D-01 删除 enableMocking() 调用和 import
- `frontend/src/composables/useDashboardCharts.ts` — D-02 删除 getPlaceholder* 函数，computed 返回 null
- `frontend/src/pages/DataDashboard.vue` — D-02 需处理 v-chart option 为 null 时的空状态展示
- `frontend/src/env.d.ts` — D-03 补充 VITE_USE_MSW 声明
- `frontend/.env.development` — D-03 新建文件

</code_context>

<specifics>
## Specific Ideas

- D-01 main.ts 简化后：`bootstrap()` 保留 async 结构但移除 `await enableMocking()`，直接 `const app = createApp(App)` 开始
- D-02 useDashboardCharts.ts 改造：4 个 computed 中 `if (!data?.length) return null`，删除 4 个 getPlaceholder* 函数定义
- D-02 DataDashboard.vue 需添加：`v-if="chartOption"` 显示 v-chart，`v-else` 显示 custom-empty 空状态
- D-03 .env.development 内容：`VITE_USE_MSW=false\nVITE_API_BASE_URL=http://localhost:8000`
- D-03 env.d.ts 补充：`readonly VITE_USE_MSW: string` 加入 ImportMetaEnv 接口
- D-01 删除 mock/ 目录后，`handlers.ts` 底部的 `export { MOCK_RESUME_RESULT }` 也随之删除 — 需确认无其他文件引用此 export（已确认：grep 无结果）

</specifics>

<deferred>
## Deferred Ideas

- **msw 依赖彻底移除** — D-04 决定保留以备未来，彻底移除推 v2.2+ 确认不再需要 mock 后
- **.env.production 文件** — 生产环境配置属部署范畴，超出 v2.1 开发环境目标
- **前端 API 错误重试/降级策略** — request.ts 已有错误提示，但无自动重试或降级到缓存数据的逻辑，属未来优化
- **图表骨架屏（skeleton）** — 当前用 custom-empty 空状态替代 placeholder，骨架屏（加载中动画）属 UX 优化范畴
- **MSW 单元测试 mock** — msw 依赖保留后，未来可能用于 Vitest 单元测试 mock（当前前端无单元测试）

</deferred>

---

*Phase: 09-frontend-mock-off*
*Context gathered: 2026-07-10*
