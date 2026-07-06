# Phase 3: 前端功能闭环 - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning

<domain>
## Phase Boundary

所有 14 个页面功能完整闭环——把"看起来有按钮但不工作"的界面变成真正调 API、有反馈、有数据的闭环。不涉及架构重构（DEC-006：Home.vue 拆分延后 Phase 6）、不涉及样式统一（Phase 5）、不修改后端 schema（DEC-004：仅追加字段）。后端 API 已就绪，Phase 3 是纯前端接线工作。

</domain>

<decisions>
## Implementation Decisions

### 演化视图集成方式
- **D-01:** EVOLVES_TO 边以**独立图层**形式集成，可叠加在任意 overview 模式上（非新增第 4 个 overview 模式）
- **D-02:** 演化图层默认**聚焦当前岗位**，仅渲染选中岗位的演化上下游（调 `/evolution/paths/{position}`），非全量渲染
- **D-03:** 演化图层**仅在 3D 视图**生效（viewMode='3d'），2D 视图不实现演化边
- **D-04:** 演化边**仅显示当前知识领域内**的关系，跨领域演化目标不渲染（可作 Phase 4/6 增强）
- **D-05:** 演化边着色遵循 EVOLVE-FE-02 规则：rising=绿、stable=灰、declining=红；trust_score 用边透明度微调

### 学习计划数据闭环
- **D-06:** 学习计划绑定用 **localStorage 暂存 plan_id**（无用户系统前提下）
- **D-07:** plan_id **每次打开 LearningCenter 时验证有效性**（调 GET），无效则清除并显示空状态
- **D-08:** **单计划模式**，localStorage 存一个 plan_id；"加入计划"时已有计划则**覆盖前确认**
- **D-09:** "加入计划"按钮调用 `POST /learning/plan`，进度从 `GET /learning/plan/{plan_id}` 读取

### 演化交互细节
- **D-10:** EvolutionDashboard 时间线滑块**控制快照时间点**，选中后显示该时间点的演化关系
- **D-11:** 点击 EVOLVES_TO 边弹出演化详情（技能变化、时间跨度）——形态由 Claude 决定（el-drawer 或 el-popover，与 D-12 一致则用 el-drawer）

### 操作反馈一致性
- **D-12:** 编辑弹窗统一用 **el-drawer 抽屉**（右侧滑出），适用于 Admin/PIPE/MATCH 所有编辑场景
- **D-13:** 保存成功后**自动刷新列表**，同时显示 toast 提示
- **D-14:** Toast 文案风格**简洁统一**：成功='保存成功'，失败='保存失败，请重试'

### Claude's Discretion
- 演化图层开关的 UI 位置（建议放在现有 radio-group 旁）
- 演化边的箭头样式和加载动画
- 未选岗位时演化图层的默认状态（建议显示提示文案"点击岗位查看演化路径"）
- 快照时间点无数据时的降级显示
- EVOLVES_TO 边点击详情的具体字段布局
- LearningCenter 空状态引导文案
- 学习进度百分比的可视化形式（进度条/环形图）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` — 项目定义、核心问题诊断、5大功能+2创新点
- `.planning/REQUIREMENTS.md` §Phase 3 — 16 个前端功能闭环需求（ADMIN-01~03, LEARN-FE-01~04, EVOLVE-FE-01~04, MATCH-FE-01~02, PIPE-FE-01~05, DASH-FE-01~02）
- `.planning/ROADMAP.md` §Phase 3 — 成功标准、关键文件
- `.planning/STATE.md` — 当前状态和已锁定决策（DEC-001~006）

### 前序阶段决策
- `.planning/phases/01-core-bugfix/01-CONTEXT.md` — Phase 1 技术决策（match_results 双写、loop_results 新建表等）

### 后端 API（已就绪，Phase 3 直接调用）
- `backend/app/api/v1/evolution.py` — `/evolution/paths/all`, `/evolution/paths/{position}`, `/evolution/snapshots`, `/evolution/changelog/{position}`, `/evolution/trends`
- `backend/app/api/v1/learning.py` — `POST /learning/plan`, `GET /learning/plans`, `GET /learning/plan/{plan_id}`, `PUT /learning/plan/{plan_id}/progress`
- `backend/app/api/v1/graph.py` — `/overview` (domain/tech_stack/level 模式)
- `backend/app/api/v1/match.py` — 匹配诊断 API
- `backend/app/api/v1/pipeline.py` — Pipeline 监控 API

### 前端关键文件
- `frontend/src/pages/Home.vue` — 图谱主页面，viewMode/overviewMode/ViewLayer 三层导航
- `frontend/src/pages/EvolutionDashboard.vue` — 839 行，0 handler，需实现时间线滑块
- `frontend/src/pages/LearningCenter.vue` — 758 行，1 handler，需实现"加入计划"+进度
- `frontend/src/pages/MatchDiagnosis.vue` — 1467 行，学习路径 JSON→格式化
- `frontend/src/pages/Admin.vue` — 702 行，8 handler，handleSaveSource 需调 API
- `frontend/src/pages/PipelineMonitor.vue` — 600 行，8 handler，重试/配置/调度需联动
- `frontend/src/stores/graph.ts` — GraphStore，overviewMode/ViewLayer/domains/domainConnections

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `el-drawer`（Element Plus）：D-12 统一编辑形态，所有页面复用
- `ElMessage`（Element Plus toast）：D-14 统一反馈，已有使用先例
- `useGraphStore`：已有 overviewMode/viewMode/currentLayer 三层导航，演化图层在此扩展
- `/evolution/paths/{position}` API：后端已实现，返回 EVOLVES_TO 关系列表，直接调
- `/learning/plan` API 套件：后端已实现 CRUD，前端直接接线

### Established Patterns
- Home.vue 三层导航：domain → position → detail，演化图层在 position 层启用
- Graph3D.vue：3D 力导向图，需在此添加演化边渲染逻辑
- localStorage 模式：D-06/D-07/D-08 学习计划暂存方案

### Integration Points
- Home.vue Graph3D 组件：演化边渲染入口（D-03 仅 3D）
- graphStore：需新增 evolveLayer 开关 + focusedPositionId + evolutionPaths 状态
- LearningCenter.vue："加入计划"按钮 → POST /learning/plan → localStorage 存 plan_id
- MatchDiagnosis.vue：学习路径 JSON 数组 → 格式化时间线/卡片组件
- Admin.vue：handleSaveSource → 实际调 API → 自动刷新列表
- PipelineMonitor.vue：重试/配置/调度 → API 调用 + loading + toast

</code_context>

<specifics>
## Specific Ideas

- 演化图层打开后未选岗位时，显示提示文案"点击岗位查看演化路径"
- 跨领域演化目标不渲染（D-04），后续可增强为虚拟节点或弹窗列表
- 学习计划"覆盖前确认"用 el-message-box confirm

</specifics>

<deferred>
## Deferred Ideas

- **用户系统（登录/注册/权限）** — 全新能力，不属于任何现有 Phase，建议 Phase 7 或后续里程碑。当前学习计划用 localStorage 暂存 plan_id 作为权宜方案。
- **2D 视图演化边渲染** — D-03 决定仅 3D，2D 演化可作 Phase 5/6 增强
- **跨领域演化目标渲染** — D-04 决定仅当前领域内，跨领域可作 Phase 4/6 增强（虚拟节点/弹窗列表）
- **演化动画播放** — 时间线滑块控制快照切换（D-10），动画播放可作后续增强

</deferred>

---

*Phase: 03-frontend-closure*
*Context gathered: 2026-07-06*
