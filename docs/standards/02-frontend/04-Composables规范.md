# Composables 规范文档

## 1. 模块概述

**职责定位**：Vue 3 Composition API 的业务逻辑封装层，将页面组件中的复杂逻辑提取为可复用的组合函数，实现关注点分离和跨页面逻辑复用。

**核心目标**：
- 提取页面组件中的复杂逻辑（图表配置、数据处理、交互状态）
- 实现跨页面复用的业务逻辑（SSE 连接、图谱交互、数据格式化）
- 保持组件模板简洁，聚焦 UI 呈现
- 提供类型安全的组合函数接口

**在系统中的位置**：
- 上游：`stores/`（状态管理）、`api/`（数据获取）
- 下游：`pages/`（页面组件）、`components/`（通用组件）
- 依赖：`utils/`（工具函数）、`types/`（类型定义）

## 2. 文件清单

### 2.1 根目录 Composables（20 个）

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `frontend/src/composables/useDashboardCharts.ts` | ~220 | 数据大屏图表配置：饼图、Treemap、折线图、雷达图的 ECharts option 生成 | `useDashboardCharts` |
| `frontend/src/composables/useDashboardDisplay.ts` | ~80 | 数据大屏展示逻辑：流水线阶段映射、状态颜色、事件图标、时间格式化 | `useDashboardDisplay` |
| `frontend/src/composables/useDashboardKpiCards.ts` | ~60 | 数据大屏 KPI 卡片配置：指标定义、趋势计算、格式化 | `useDashboardKpiCards` |
| `frontend/src/composables/useDashboardRealtimeSync.ts` | ~90 | 数据大屏实时同步：SSE 连接、定时刷新、时钟管理 | `useDashboardRealtimeSync` |
| `frontend/src/composables/useDataSourceActions.ts` | ~60 | 数据源操作：CRUD 动作封装、批量操作 | `useDataSourceActions` |
| `frontend/src/composables/useDataSourceCharts.ts` | ~120 | 数据源图表：来源分布、质量趋势、采集量统计 | `useDataSourceCharts` |
| `frontend/src/composables/useDataSourceSummary.ts` | ~40 | 数据源摘要：统计计算、状态汇总 | `useDataSourceSummary` |
| `frontend/src/composables/useEvolutionActions.ts` | ~80 | 演化操作：趋势计算、路径分析、对比操作 | `useEvolutionActions` |
| `frontend/src/composables/useEvolutionCharts.ts` | ~180 | 演化图表：趋势折线图、技能雷达图、对比柱状图 | `useEvolutionCharts` |
| `frontend/src/composables/useEvolutionFormatters.ts` | ~30 | 演化数据格式化：日期、百分比、趋势方向格式化 | `useEvolutionFormatters` |
| `frontend/src/composables/useG6.ts` | ~20 | G6 动态加载：按需导入 @antv/g6，缓存 Graph 类 | `ensureG6Loaded` |
| `frontend/src/composables/useG6Graph.ts` | ~50 | G6 图谱实例管理：创建、销毁、事件绑定 | `useG6Graph` |
| `frontend/src/composables/useGraphNodeEditor.ts` | ~100 | 图谱节点编辑：节点属性编辑、标签管理 | `useGraphNodeEditor` |
| `frontend/src/composables/useGraphNodeLabels.ts` | ~30 | 图谱节点标签：标签生成、格式化、截断 | `useGraphNodeLabels` |
| `frontend/src/composables/useGraphNodeList.ts` | ~60 | 图谱节点列表：节点筛选、排序、分页 | `useGraphNodeList` |
| `frontend/src/composables/useKPIMetrics.ts` | ~40 | KPI 指标计算：岗位数、技能数、领域数、关系数聚合 | `useKPIMetrics` |
| `frontend/src/composables/useLearningActions.ts` | ~80 | 学习操作：计划创建、进度更新、路径规划 | `useLearningActions` |
| `frontend/src/composables/useLearningFilters.ts` | ~40 | 学习筛选：技能分类、状态、优先级筛选逻辑 | `useLearningFilters` |
| `frontend/src/composables/useLearningMetrics.ts` | ~50 | 学习指标：完成率、预估时间、掌握度计算 | `useLearningMetrics` |
| `frontend/src/composables/useLearningPriority.ts` | ~30 | 学习优先级：技能优先级排序、推荐算法 | `useLearningPriority` |

### 2.2 根目录 Composables（续，8 个）

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `frontend/src/composables/usePipelineMonitor.ts` | ~380 | 流水线监控：自动刷新、阶段状态、数据质量、SSE 进度 | `usePipelineMonitor` |
| `frontend/src/composables/useQualityActions.ts` | ~60 | 质量操作：审核、评分、告警处理 | `useQualityActions` |
| `frontend/src/composables/useQualityDashboard.ts` | ~60 | 质量看板：质量指标聚合、趋势分析 | `useQualityDashboard` |
| `frontend/src/composables/useQualityDashboardCharts.ts` | ~180 | 质量图表：质量趋势、分布、对比图表配置 | `useQualityDashboardCharts` |
| `frontend/src/composables/useSSE.ts` | ~260 | SSE 连接管理：指数退避、轮询降级、事件分发 | `useSSE` |

### 2.3 home/ 子目录 Composables（8 个）

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `frontend/src/composables/home/index.ts` | ~10 | Home 页面 composables 统一导出 | 聚合导出 |
| `frontend/src/composables/home/useEvolutionPanel.ts` | ~40 | 演化面板：面板显示/隐藏、演化链路数据 | `useEvolutionPanel` |
| `frontend/src/composables/home/useGraph2DData.ts` | ~50 | 2D 图谱数据：节点/边数据转换、领域着色 | `useGraph2DData` |
| `frontend/src/composables/home/useGraph3DData.ts` | ~50 | 3D 图谱数据：节点/边数据转换、3D 坐标计算 | `useGraph3DData` |
| `frontend/src/composables/home/useGraphToolbarState.ts` | ~40 | 工具栏状态：布局模式、最大节点数、熟练度筛选 | `useGraphToolbarState` |
| `frontend/src/composables/home/useHomeInteractions.ts` | ~380 | 首页交互：节点点击、搜索、画布点击、面包屑、高亮 | `useHomeInteractions` |
| `frontend/src/composables/home/useHomeLayout.ts` | ~20 | 首页布局：视图模式（2D/3D）、自动旋转 | `useHomeLayout` |
| `frontend/src/composables/home/useNodeSelection.ts` | ~20 | 节点选中：选中状态管理、清除选择 | `useNodeSelection` |

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Pages (15个)                                               │
│  ├── Home.vue                                               │
│  │   ├── useHomeInteractions                                │
│  │   ├── useGraph2DData / useGraph3DData                    │
│  │   ├── useGraphToolbarState                               │
│  │   ├── useEvolutionPanel                                   │
│  │   ├── useHomeLayout                                      │
│  │   └── useNodeSelection                                   │
│  ├── DataDashboard.vue                                      │
│  │   ├── useDashboardCharts                                 │
│  │   ├── useDashboardDisplay                                  │
│  │   ├── useDashboardKpiCards                               │
│  │   └── useDashboardRealtimeSync                            │
│  ├── PipelineMonitor.vue                                    │
│  │   └── usePipelineMonitor                                 │
│  └── ...                                                    │
├─────────────────────────────────────────────────────────────┤
│  Composables (28个)                                         │
│  ├── 图表类: use*Charts (6个)                               │
│  ├── 数据类: use*Data / use*Summary (4个)                   │
│  ├── 交互类: use*Actions / use*Interactions (6个)           │
│  ├── 展示类: use*Display / use*Formatters (3个)             │
│  ├── 连接类: useSSE (1个)                                   │
│  ├── 图谱类: useG6 / useG6Graph / useGraph* (4个)           │
│  └── 首页专用: home/ (8个)                                  │
├─────────────────────────────────────────────────────────────┤
│  Stores (14个)                                              │
│  └── 为 composables 提供原始数据                             │
└─────────────────────────────────────────────────────────────┘
```

### 依赖关系

- **图表类 composables** → `stores/`（数据） + `utils/chartTheme.ts`（主题）
- **交互类 composables** → `stores/`（数据） + `api/`（操作）
- **useSSE** → 独立，不依赖 store，可被任何组件/composable 使用
- **home/ 子目录** → 专为 `Home.vue` 服务，不对外暴露

## 4. 接口规范

### 4.1 useSSE 接口（核心基础设施）

```typescript
export interface UseSSEOptions {
  onMessage: (event: MessageEvent) => void
  onError?: (err: Event) => void
  baseDelay?: number        // 默认 1000
  maxDelay?: number         // 默认 30000
  maxRetries?: number       // 默认 10
  pollThreshold?: number    // 默认 3
  pollInterval?: number     // 默认 5000
  pollUrl?: string
  storeHandlers?: Record<string, (data: unknown) => void>
}

export function useSSE(url: string, options: UseSSEOptions): {
  connected: Ref<boolean>
  disconnect: () => void
}
```

### 4.2 useDashboardCharts 接口

```typescript
export function useDashboardCharts(store: DashboardStore): {
  darkPieOption: ComputedRef<EChartsOption | undefined>
  treemapOption: ComputedRef<EChartsOption | undefined>
  trendOption: ComputedRef<EChartsOption | undefined>
  radarOption: ComputedRef<EChartsOption | undefined>
}
```

### 4.3 usePipelineMonitor 接口

```typescript
export function usePipelineMonitor(): {
  pipeline: PipelineStore
  autoRefresh: Ref<boolean>
  refreshInterval: Ref<number>
  lastRefresh: Ref<string>
  loadAll: () => Promise<void>
  startAutoRefresh: () => void
  toggleAutoRefresh: (val: boolean) => void
  // ... 其他导出
}
```

### 4.4 useHomeInteractions 接口

```typescript
export function useHomeInteractions(storeFactory: () => GraphStore): {
  graph2DRef: Ref<InstanceType<typeof Graph2D> | null>
  graph3DRef: Ref<InstanceType<typeof Graph3D> | null>
  breadcrumb: Ref<string[]>
  selectedNode: Ref<GraphNode | null>
  handleNodeClick: (id: string, selectedNode: Ref<GraphNode | null>) => void
  handleSearchSelect: (id: string, name: string, type: string, selectedNode: Ref<GraphNode | null>) => void
  // ... 其他导出
}
```

## 5. 编码规范（本模块特有）

### 5.1 Composable 命名约定
- **必须**以 `use` 前缀开头（Vue 社区约定）
- **必须**使用 camelCase（如 `useDashboardCharts`）
- 功能分类命名：`use{Domain}{Function}`（如 `usePipelineMonitor`）
- 首页专用 composables 放入 `home/` 子目录

### 5.2 返回值约定
- 返回对象解构，便于按需取用
- reactive 数据使用 `ref()` / `computed()`
- 方法函数直接返回（不包装）
- 生命周期相关（如 SSE 连接）返回 `disconnect` 清理函数

### 5.3 依赖注入约定
- **优先**通过参数传递 store 实例，而非在 composable 内部 `import` store
- 示例：`useDashboardCharts(store)` 而非 `useDashboardCharts()` 内部调用 `useDashboardStore()`
- 例外：纯工具 composable（如 `useSSE`）不依赖 store，可直接使用

### 5.4 图表 Composable 约定
- 返回 `ComputedRef<EChartsOption>`，由调用方决定何时渲染
- 图表主题通过 `utils/chartTheme.ts` 统一获取
- 动画配置使用 `chartAnimationConfig()` 保持一致性

### 5.5 反模式
- **禁止**在 composable 中直接操作 DOM（应通过组件的 `ref` 传递）
- **禁止**在 composable 中引入 `vue-router`（导航应在组件层处理）
- **禁止**创建不返回 reactive 数据的 composable（应使用普通工具函数）
- **禁止**在 composable 中定义过多副作用（如多个 `watch`），应拆分为多个 composable

## 6. 测试规范

| 测试文件 | 覆盖范围 | 策略 |
|---------|---------|------|
| `frontend/src/composables/__tests__/useSSE.test.ts` | SSE 连接、重连、轮询降级 | mock EventSource + timer |
| `frontend/src/composables/__tests__/useDashboardCharts.test.ts` | 图表 option 生成、空数据处理 | mock store + snapshot |
| `frontend/src/composables/__tests__/usePipelineMonitor.test.ts` | 自动刷新、阶段状态 | mock store + vi.useFakeTimers |

**覆盖率要求**：
- 每个 composable 的导出函数至少覆盖正常路径和异常路径
- 涉及 SSE/WebSocket 的需覆盖连接失败、重连、降级场景
- 图表 composables 需覆盖空数据、单条数据、多条数据场景

**Mock 策略**：
- `stores/` → `vi.mock('@/stores/xxx')` 或使用 `createTestingPinia`
- `EventSource` → jsdom 不支持，需 mock 全局 `EventSource`
- `setInterval` / `setTimeout` → `vi.useFakeTimers()`

## 7. 变更管理

### 修改检查清单

- [ ] 新增 composable 是否以 `use` 开头？
- [ ] 返回值是否为对象解构形式？
- [ ] 是否通过参数注入 store 依赖（而非内部 import）？
- [ ] 是否导出了清理函数（如 SSE disconnect）？
- [ ] 是否提取了可复用的纯函数到 `utils/`？
- [ ] 是否更新了 `home/index.ts` 的聚合导出（如为 home 子目录新增）？

### 契约影响
- Composables 不直接依赖 `starmap-contracts`，通过 store 间接使用
- 修改 composable 的输入/输出类型时，需检查所有引用该 composable 的组件

### 迁移要求
- Composable 拆分：将一个大的 composable 拆分为多个时，需同步更新所有引用
- Composable 合并：合并前需确认无循环依赖
- 参数变更：新增参数需有默认值，避免破坏现有调用方
