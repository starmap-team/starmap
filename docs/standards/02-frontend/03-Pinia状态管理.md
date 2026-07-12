# Pinia 状态管理 规范文档

## 1. 模块概述

**职责定位**：前端全局状态管理中心，采用 Pinia 框架管理 14 个业务域的状态，提供响应式数据、计算属性及异步 action。

**核心目标**：
- 按业务域拆分 store，避免单一巨型 store
- 统一使用 `request.ts` 进行 API 调用（`client.ts` 尚未完全推广）
- 支持持久化（localStorage）和跨组件状态共享
- 废弃 store 通过 re-export 保持向后兼容

**在系统中的位置**：
- 上游：`api/request.ts`（数据获取）、`api/client.ts`（类型安全 API，待推广）
- 下游：所有 `pages/`（页面组件）、`composables/`（组合函数）、`components/`（通用组件）
- 契约依赖：`starmap-contracts/models/__init__.py` 的 Pydantic 模型与 store 类型定义语义对齐

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `frontend/src/stores/datasource.ts` | ~200 | 数据源管理：多源数据融合（BOSS/拉勾/51Job/GitHub/ESCO）、CRUD、统计查询、同步触发 | `useDataSourceStore` |
| `frontend/src/stores/dashboard.ts` | ~280 | 数据大屏：全系统指标聚合（图谱统计、来源分布、质量指标、实时处理量） | `useDashboardStore` |
| `frontend/src/stores/graph.ts` | ~350 | 全景图谱：三层视图架构（domain/position/detail）、节点/边数据、视图模式 | `useGraphStore` |
| `frontend/src/stores/pipeline.ts` | ~400 | 数据流水线：ETL 全链路状态、DAG 并行、阶段监控、SSE 实时进度 | `usePipelineStore` |
| `frontend/src/stores/loop.ts` | ~380 | 闭环演示：5 步端到端闭环状态管理、步骤结果、历史记录 | `useLoopStore` |
| `frontend/src/stores/learning.ts` | ~420 | 学习中心：技能进度追踪、学习路径规划、计划 ID 持久化（localStorage） | `useLearningStore` |
| `frontend/src/stores/match.ts` | ~180 | 匹配诊断：岗位-技能匹配分析、差距等级、诊断报告 | `useMatchStore` |
| `frontend/src/stores/jd.ts` | ~150 | JD 抽取：职位描述解析、技能提取结果、抽取历史 | `useJdStore` |
| `frontend/src/stores/evolution.ts` | ~120 | 演化看板：技能演化趋势、岗位演进路径、新兴技能追踪 | `useEvolutionStore` |
| `frontend/src/stores/quality.ts` | ~180 | 图谱质量：质量评分、数据完整性、幻觉检测、审核队列 | `useQualityStore` |
| `frontend/src/stores/jobseeker.ts` | ~140 | 求职者分析：简历解析、技能画像、求职匹配度 | `useJobseekerStore` |
| `frontend/src/stores/resume.ts` | ~60 | 简历管理：简历上传、解析状态、解析结果 | `useResumeStore` |
| `frontend/src/stores/user.ts` | ~60 | 用户认证：登录状态、用户信息、admin 权限 | `useUserStore` |
| `frontend/src/stores/admin.ts` | ~20 | **已废弃** — re-export `useDataSourceStore` 保持兼容 | `useAdminStore` (alias) |

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (request.ts / client.ts)                          │
├─────────────────────────────────────────────────────────────┤
│  Pinia Stores (14个)                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ datasource  │ │  dashboard  │ │    graph    │           │
│  │   (数据层)   │ │  (聚合层)    │ │  (图谱层)    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   pipeline  │ │    loop     │ │   learning  │           │
│  │  (流水线)    │ │  (闭环演示)  │ │  (学习中心)  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │    match    │ │     jd      │ │  evolution  │           │
│  │  (匹配诊断)  │ │  (JD抽取)   │ │  (演化看板)  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   quality   │ │  jobseeker  │ │   resume    │           │
│  │  (质量监控)  │ │ (求职者分析) │ │  (简历管理)  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐                           │
│  │    user     │ │ admin(废弃)  │                           │
│  │  (用户认证)  │ │             │                           │
│  └─────────────┘ └─────────────┘                           │
├─────────────────────────────────────────────────────────────┤
│  Consumers: pages/ + composables/ + components/             │
└─────────────────────────────────────────────────────────────┘
```

### 依赖关系

- **dashboard store** 依赖：datasource、pipeline、quality（聚合展示）
- **loop store** 独立，不与 pipeline store 合并（Phase 6 D-13 决策）
- **learning store** 使用 localStorage 持久化 `plan_id`
- **graph store** 为 Graph2D/Graph3D 组件提供只读数据

## 4. 接口规范

### 4.1 Store 通用模式

```typescript
// 所有 store 遵循统一模式
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'

export const useXxxStore = defineStore('xxx', () => {
  // ── State ──
  const data = ref<T[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── Getters (computed) ──
  const itemCount = computed(() => data.value.length)

  // ── Actions ──
  async function fetchData() {
    loading.value = true
    try {
      const res = await request.get('/xxx')
      data.value = res.data
    } catch (e) {
      error.value = String(e)
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, itemCount, fetchData }
})
```

### 4.2 各 Store 核心导出

| Store | 核心 State | 核心 Actions | 持久化 |
|-------|-----------|-------------|--------|
| `useDataSourceStore` | `sources`, `stats`, `auditQueue` | `fetchSources`, `syncSource`, `approveAudit` | 无 |
| `useDashboardStore` | `overview`, `sourceDistribution`, `qualityTrend` | `fetchOverview`, `fetchRealtime` | 无 |
| `useGraphStore` | `nodes`, `edges`, `viewLayer` | `fetchGraph`, `switchLayer` | 无 |
| `usePipelineStore` | `runs`, `stages`, `alerts` | `fetchStatus`, `triggerRun`, `cancelRun` | 无 |
| `useLoopStore` | `currentRun`, `history`, `steps` | `startLoop`, `retryStep` | 无 |
| `useLearningStore` | `plan`, `progress`, `paths` | `fetchPlan`, `updateProgress` | `plan_id` → localStorage |
| `useMatchStore` | `diagnosis`, `gaps` | `runMatch`, `fetchDiagnosis` | 无 |
| `useJdStore` | `extractions`, `currentJd` | `extractJd`, `fetchHistory` | 无 |
| `useEvolutionStore` | `trends`, `paths` | `fetchTrends`, `fetchPaths` | 无 |
| `useQualityStore` | `score`, `alerts`, `metrics` | `fetchDashboard`, `fetchAlerts` | 无 |
| `useJobseekerStore` | `profile`, `matches` | `fetchProfile`, `fetchMatches` | 无 |
| `useResumeStore` | `resumes`, `parsingStatus` | `uploadResume`, `fetchResumes` | 无 |
| `useUserStore` | `token`, `userInfo`, `isAdmin` | `login`, `logout` | `starmap_token` → localStorage |

## 5. 编码规范（本模块特有）

### 5.1 Store 定义约定
- **必须**使用 Composition API 风格（`defineStore('id', () => { ... })`）
- **必须**在 store 顶部添加 JSDoc 注释说明职责和 Sprint 版本
- **必须**使用 `ref()` 定义状态，`computed()` 定义派生状态
- **推荐**在 action 中统一处理 loading/error 状态
- **禁止**在 store 中直接操作 DOM（应通过组件或 composable 处理）

### 5.2 API 调用约定
- **当前**：使用 `request.get/post`（`request.ts`）
- **目标**：逐步迁移到 `client.ts` 的 `api.*` 方法以获得类型安全
- **禁止**在 store 中引入新的 axios 实例

### 5.3 类型定义约定
- 内联类型定义在 store 文件中（如 `DataSourceStats`、`PipelineStage`）
- 共享类型应提取到 `types/` 目录（如 `types/datasource.ts`、`types/quality.ts`）
- re-export 共享类型以保持向后兼容：`export type { Xxx } from '@/types/xxx'`

### 5.4 持久化约定
- localStorage 键名使用 `starmap_` 前缀（如 `starmap_token`、`starmap_learning_plan_id`）
- 读写 localStorage 必须包裹 `try/catch`（隐私模式可能禁用）
- 敏感信息（token）应同时考虑 Cookie 作为 fallback

### 5.5 反模式
- **禁止**创建跨多个业务域的"上帝 store"
- **禁止**在 store 中直接调用 `useRouter()`（应在组件层处理导航）
- **禁止**在 store 之间直接 import 其他 store 的实例（使用函数参数传递）
- **禁止**使用 Options API 风格定义 store

## 6. 测试规范

| 测试文件 | 覆盖范围 | 策略 |
|---------|---------|------|
| `frontend/src/stores/__tests__/datasource.test.ts` | 数据源 CRUD、审核流程 | mock request + createTestingPinia |
| `frontend/src/stores/__tests__/pipeline.test.ts` | 流水线状态机、阶段转换 | mock request + timer |
| `frontend/src/stores/__tests__/loop.test.ts` | 闭环步骤状态流转 | mock request |
| `frontend/src/stores/__tests__/learning.test.ts` | localStorage 持久化 | mock localStorage |

**覆盖率要求**：
- 每个 store 的 action 至少覆盖成功/失败两种路径
- computed getter 覆盖边界条件（空数组、null 等）
- 涉及 localStorage 的 store 需覆盖读写异常

**Mock 策略**：
- `request` → `vi.mock('@/api/request')`
- `localStorage` → `vi.spyOn(Storage.prototype, 'getItem')`
- Pinia → `import { createTestingPinia } from '@pinia/testing'`

## 7. 变更管理

### 修改检查清单

- [ ] 新增 store 是否遵循 Composition API 风格？
- [ ] 新增 store 的 `id` 是否全局唯一？
- [ ] 是否定义了清晰的 State / Getter / Action 边界？
- [ ] API 调用是否使用 `request.ts`（或已迁移到 `client.ts`）？
- [ ] 新增类型是否已提取到 `types/` 目录（如为共享类型）？
- [ ] 是否需要 localStorage 持久化？键名是否加 `starmap_` 前缀？
- [ ] 是否与 `starmap-contracts/models/` 的 Pydantic 模型语义一致？

### 契约影响
- Store 中的类型定义应与 `starmap-contracts/models/__init__.py` 保持字段名一致
- 后端 API 响应结构变更 → 需同步更新对应 store 的类型定义和解析逻辑
- 新增业务域 → 需确认 `openapi.yaml` 中已有对应端点定义

### 迁移要求
- 废弃 store（如 `admin.ts`）通过 re-export 保持兼容，至少保留一个 Sprint 周期
- Store 拆分/合并时，需同步更新所有引用该 store 的组件和 composable
- 从 `request.ts` 迁移到 `client.ts` 时，按 store 逐个迁移，每次迁移后运行完整测试
