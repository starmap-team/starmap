# Phase 9: 前端关闭 Mock - Research

**Researched:** 2026-07-10
**Phase:** 09-frontend-mock-off

---

## 1. DataDashboard.vue 结构

**File:** `frontend/src/pages/DataDashboard.vue`

DataDashboard 直接将 `useDashboardCharts` 的 4 个 computed 绑定到 `<VChart :option="xxx">` — **没有任何空状态处理**：

```
Line 113-118: <VChart :option="darkPieOption" autoresize :style="{ height: '100%' }" />
Line 128-132: <VChart :option="treemapOption" autoresize :style="{ height: '100%' }" />
Line 142-148: <VChart :option="trendOption" autoresize :style="{ height: '100%' }" />
Line 251-255: <VChart :option="radarOption" autoresize :style="{ height: '100%' }" />
```

每个图表都在 `.chart-container` div 内（flex:1, min-height:0, padding:4px）。

**关键发现：** 需要在每个 `<VChart>` 外层添加 `v-if` / `v-else` 条件渲染，当 option 为 null 时显示 custom-empty 空状态。

**模板改造模式：**
```html
<div class="chart-container">
  <VChart v-if="darkPieOption" :option="darkPieOption" autoresize :style="{ height: '100%' }" />
  <div v-else class="custom-empty">
    <div class="empty-icon-wrapper">📊</div>
    <p class="empty-text">暂无数据</p>
    <p class="empty-hint-text">数据加载中或暂无记录</p>
  </div>
</div>
```

---

## 2. vue-echarts (VChart) null option 处理

**File:** `frontend/src/main.ts:7` — `import VChart from 'vue-echarts'`

vue-echarts 行为：
- 当 `option` 为 `null` / `undefined` 时，echarts 实例仍会创建，但渲染空白 canvas（不报错）
- 这不是理想行为 — 用户看到空白区域而非明确的"暂无数据"提示
- **结论：** 必须在 DataDashboard.vue 中用 `v-if` 控制，当 option 为 null 时不渲染 VChart，而是显示空状态

---

## 3. custom-empty 空状态模式

**CSS 定义:** `frontend/src/App.vue:530-540`
```css
.custom-empty { /* flex center layout */ }
.empty-icon-wrapper { color: var(--muted-foreground); opacity: 0.35; margin-bottom: var(--space-4); }
.empty-text { font-size: var(--font-size-base); font-weight: 600; color: var(--foreground); margin: 0; }
.empty-hint-text { font-size: var(--font-size-sm); color: var(--muted-foreground); margin: var(--space-1) 0 0; }
```

**典型使用 (CareerPathGraph.vue:159-183):**
```html
<div v-else class="custom-empty">
  <div class="empty-icon-wrapper">🗺️</div>
  <p class="empty-text">暂无路径数据</p>
  <p class="empty-hint-text">选择目标岗位后生成学习路径</p>
</div>
```

**但 DataDashboard 使用暗色主题** — `--dash-surface` / `--dash-text-*` CSS 变量。custom-empty 使用 `--foreground` / `--muted-foreground`，在暗色主题下可能不可见。**需要验证或使用 dash 主题变量。**

**备选方案：** 直接使用 `el-empty` Element Plus 组件（PipelineAnalysis.vue:242 已在用），它自带暗色适配。

---

## 4. MSW 移除影响

**mock 目录内容：**
- `frontend/src/mock/handlers.ts` — 8 个 API mock handler
- `frontend/src/mock/msw-browser.ts` — MSW 浏览器初始化

**mock 外部引用：** 仅 `frontend/src/main.ts:15,22` 引用 mock 模块：
```typescript
import { enableMocking } from './mock/msw-browser'
await enableMocking()
```

**handlers.ts 底部 export：** `export { MOCK_RESUME_RESULT }` — grep 确认无其他文件引用此 export。

**mockServiceWorker.js：** `frontend/public/mockServiceWorker.js` — 9469 bytes，仅 MSW 运行时使用，无其他引用。

**测试文件：** 前端无 MSW 相关测试文件（前端当前无单元测试）。

**结论：** 删除 mock/ 目录和 mockServiceWorker.js 不会破坏任何其他文件。仅需修改 main.ts。

---

## 5. Dashboard Store 数据流

**File:** `frontend/src/stores/dashboard.ts`

| Chart Computed | Store 数据 | API 端点 | 无数据含义 |
|---|---|---|---|
| `darkPieOption` | `store.sourceDistribution` | `fetchSourceDistribution()` → `/api/v1/dashboard/source-distribution` | 空数组 `[]` |
| `treemapOption` | `store.skillDomains` | `fetchSkillDomains()` → `/api/v1/dashboard/skill-domains` | 空数组 `[]` |
| `trendOption` | `store.qualityTrends` | (从 overview 推导) | 空数组 `[]` |
| `radarOption` | `store.emergingSkills` | `fetchEmergingSkills()` → `/api/v1/evolution/emerging-skills` | 空数组 `[]` |

**关键发现：** useDashboardCharts.ts 中 4 个 computed 的空数据检测逻辑：
- `darkPieOption`: `if (!data?.length)` — 空数组触发 placeholder
- `treemapOption`: `if (!data?.length)` — 同上
- `trendOption`: `if (!trends?.length)` — 同上
- `radarOption`: `if (!skills?.length)` — 同上

**改造方案：** 将 `return getPlaceholder*()` 改为 `return null`，DataDashboard.vue 用 `v-if` 检测 null 显示空状态。

---

## 6. env.d.ts 影响

**File:** `frontend/src/env.d.ts:49-53`

当前 `ImportMetaEnv` 接口：
```typescript
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}
```

**需要添加：**
```typescript
readonly VITE_USE_MSW: string  // 'true' | 'false' | undefined
```

---

## 7. 构建验证 — mock 模块引用

**搜索范围:** `frontend/src/` 所有 `.ts` / `.vue` 文件

**结果：** 仅 `main.ts` 引用 mock 模块：
```
frontend/src/main.ts:15: import { enableMocking } from './mock/msw-browser'
```

**无其他文件导入 `@/mock/` 或 `./mock/`。** handlers.ts 的 `MOCK_RESUME_RESULT` export 无外部消费者。

**删除 mock/ 后的 vue-tsc 影响：** 删除 main.ts 中的 import 后，mock/ 目录可安全删除，无类型引用残留。

---

## 风险与边缘情况

1. **暗色主题适配：** DataDashboard 使用 `--dash-*` CSS 变量，custom-empty 用 `--foreground` 系变量。需验证在暗色大屏中空状态是否可见，或需使用 dash 变量覆盖。
2. **VChart 初始化时序：** 删除 `await enableMocking()` 后，bootstrap() 不再需要 await（MSW worker.start 是异步的）。保留 async 函数结构不影响功能。
3. **Docker 环境：** docker-compose.dev.yml 已设 `VITE_USE_MSW=false`。本地开发 `.env.development` 需同步设置。
4. **lockfile 影响：** 保留 msw 依赖不修改 package.json，无需重新生成 lockfile。

---

## RESEARCH COMPLETE
