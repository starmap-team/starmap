# Phase 5: 样式统一与体验优化 - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

收尾样式统一：把 28 个 Vue/TS 文件中残留的 ~307 处硬编码 hex 颜色迁入 `utils/graphColors.ts`（ECharts 主题色新增子模块）和 `styles/design-tokens.css`（CSS var 体系）；用 Playwright 截图 diff 验证 2D/3D KA 节点颜色输出一致；NodeTooltip3D 中 3 处 Slate 系 hex 替换为 CSS var。**不涉及**架构重构（Phase 6 拆分 Home.vue）、不修改后端 schema、不动 graphColors.ts 中既有的 NODE_TYPE_COLORS / EDGE_TYPE_COLORS 体系。

前置阶段已实现（**不在本阶段重做**）：
- `utils/graphColors.ts` 已是唯一颜色源（4/6 准则 ✅）
- `composables/useGraphColors.ts` 已删除（合并到 graphColors.ts）
- GraphToolbar 受控化（showFilters 保留为 UI-local）
- 后端 6 个死端点已删除
- 仅 2 处合法 console.warn
- `styles/design-tokens.css` 已有 spacing/typography/radius/shadow/elevation 完整体系

本阶段 4 个真正灰色地带（仅实现决策，不重做）：
1. DataDashboard.vue 112 处 ECharts hex 迁移策略（批量 vs 分批）
2. graphColors.ts 与 design tokens 的边界（JS 字面量 vs CSS var 桥接）
3. 2D/3D KA 一致性的验证手段（Playwright 截图 diff vs 源码静态）
4. NodeTooltip3D.vue 中 Slate-200/400/500 残留处理（CSS var vs 新 TS 常量）

</domain>

<decisions>
## Implementation Decisions

### G1 DataDashboard.vue 112 处 ECharts hex 迁移（D-01）
- **D-01:** **批量扫除**——一次性聚合 112 处 hex 到 `graphColors.ts` 新增 `ECHARTS_PALETTE` 常量，按用途（series/gauge/grid/axis）分子表导出；DataDashboard.vue 改为 `import { ECHARTS_PALETTE } from '@/utils/graphColors'`。理由：112 处散布在多组件的 ECharts option 中，无业务逻辑差异，色值聚合后 grep-replace 即可
- **D-02:** **`ECHARTS_PALETTE` 与 NODE_TYPE_COLORS 语义隔离**——前者是图表主题色（与图谱节点无关），后者是节点色板。两个常量共存于 graphColors.ts，不互相替换
- **D-03:** **DataDashboard.vue 同步检查 `stores/quality.ts`**——STATE.md 提到的 28 个含硬编码文件清单中包含该 store，迁移时同步改
- **D-04:** **不再逐函数分批 PR**——逐 PR ROI 低、且因颜色聚合后才能正确导入 ECHARTS_PALETTE，强行分批会产生中间态（部分 hex 仍残留）

### G2 graphColors.ts 与 design tokens 桥接（D-05）
- **D-05:** **JS 端保留 hex 字面量，不引入 CSS var 桥接**——graphColors.ts 被 G6 / Three.js / ECharts 直接消费，需要 JS 字符串；引入 TS 读 CSS var 会带来运行时开销且复杂化。**双体系并存**：CSS var 用于 Vue 模板 `:style` / `<style>`；TS 字面量用于 canvas / ECharts / G6 配置
- **D-06:** **graphColors.ts 不改为 `getComputedStyle()` 读取**——避免 SSR 不一致 + 颜色变化需要重新加载；token 与色板本就语义独立
- **D-07:** **`design-tokens.css` 不新增 `--slate-*` 等图谱相关 token**——保持 design tokens 用于 Vue 模板 / 通用 UI；图谱专属颜色常量集中在 graphColors.ts

### G3 2D/3D KA 一致性验证（D-08）
- **D-08:** **Playwright 截图 diff 脚本**——新增 `tests/e2e/test_2d_3d_color_consistency.py`：起两个页面（Home.vue viewMode='2d' 与 viewMode='3d'），定位同一 KA 节点，截图后用 PIL 比对 dominant color 落在 ±5 RGB 范围内
- **D-09:** **复用现有 `tests/e2e/smoke_test.py` 启动器**——不新建独立测试入口，沿用 `--base-url` + `--all` 协议
- **D-10:** **不引入额外依赖（PIL/Pillow）**——若环境未安装，使用 stdlib `struct` + 简单字节比较；或写入 `requirements-dev.txt` 后 `poetry add`
- **D-11:** **接受 ±5 RGB 容差**——3D 渲染有抗锯齿/glow 效果，精确一致不可达；±5 是经验阈值

### G4 NodeTooltip3D.vue 残留处理（D-12）
- **D-12:** **`#e2e8f0`/`#64748b`/`#94a3b8` 替换为 `var(--slate-200/500/400)`**——直接 CSS var 引用，不新增 graphColors.ts SLATE 常量
- **D-13:** **前提是 `design-tokens.css` 中存在 `--slate-*`**——若缺失则新增到 design-tokens.css（属于 token 体系扩展）；不污染 graphColors.ts
- **D-14:** **保留 `TYPE_INFO[...].color + '22'` 透明度拼接模式**——`#e2e8f0 + '22'` 等 alpha 追加在 Vue `:style` 中是合法模式（CSS `color-mix` 浏览器支持尚未稳定）

### Claude's Discretion
- `ECHARTS_PALETTE` 子表命名（建议：`ECHARTS_SERIES` / `ECHARTS_GAUGE` / `ECHARTS_AXIS` / `ECHARTS_GRID`，具体子表 Claude 决定）
- 颜色分类标准（HEX 值相同但用法不同时如何处理，如 `#22d3ee` 在 ECharts 中是 series 但在 graphColors 中是 REQUIRES 边色）
- Playwright 脚本中「同一 KA 节点」的选择策略（随机第一个 vs 按 ID 显式指定）
- 截图采样区域大小（节点 bounding box vs 节点中心 10×10）
- DataDashboard.vue 内 25 个 hex 是否全部归类到 ECHARTS_PALETTE，还是部分归 graphColors.ts 现有 NODE_TYPE_COLORS
- NodeTooltip3D 中若 `design-tokens.css` 已存在 `--slate-*` 直接用；若不存在是否同步补全

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` — 项目定义、5大功能+2创新点
- `.planning/REQUIREMENTS.md` §Phase 5 — STYLE-01~04 (4), COLOR-01~04 (4), TOOLBAR-01~03 (3), SCHEMA-01~02 (2), CLEANUP-01~04 (4)
- `.planning/ROADMAP.md` §Phase 5 — 成功标准、关键文件清单
- `.planning/STATE.md` — 当前状态 + DEC-001~006 + P5 status 4/6 + DEC-010 颜色迁移

### 前序阶段决策
- `.planning/phases/03-frontend-closure/03-CONTEXT.md` — Phase 3 前端闭环决策 D-01~14（edrawer/toast/演化视图等）
- `.planning/phases/04-dataflow/04-CONTEXT.md` — Phase 4 数据流贯通决策 D-01~15（闭环验证/三方评估等）

### 颜色体系（直接消费）
- `frontend/src/utils/graphColors.ts` — 当前唯一颜色源（NODE_TYPE_COLORS / EDGE_TYPE_COLORS / TYPE_INFO / DOMAIN_COLORS / KA_FALLBACK_COLORS）
- `frontend/src/styles/design-tokens.css` — CSS var 体系（spacing/radius/shadow/typography/elevation），需确认是否有 `--slate-*` 系列
- `frontend/src/styles/animations.css`, `responsive.css` — 配套样式
- `frontend/src/utils/chartTheme.ts` — 现有 ECharts 主题，若已部分实现 ECHARTS_PALETTE 则参考

### 关键文件（STATE.md 列出 28 个含硬编码文件）
- `frontend/src/pages/DataDashboard.vue` (1216 行, 25 处 hex) — D-01 批量迁移目标
- `frontend/src/pages/Home.vue` (821 行) — KA_COLOR_MAP 构建入口
- `frontend/src/pages/PipelineAnalysis.vue` (6 处 hex) — design tokens 改造参考（D-07 不污染）
- `frontend/src/pages/MatchDiagnosis.vue` (9 处 hex)
- `frontend/src/pages/EvolutionDashboard.vue` (6 处 hex)
- `frontend/src/components/GraphToolbar.vue` (338 行, 已用 var(--*) fallback) — P5 已完成 ✅
- `frontend/src/components/NodeTooltip3D.vue` (3 处 hex 残留) — D-12 替换目标
- `frontend/src/components/Graph2D.vue`, `Graph3D.vue` — 已正确 import graphColors
- `frontend/src/stores/quality.ts` — D-03 同步迁移
- `frontend/src/composables/useGraphColors.ts` — 已删除 ✅
- `frontend/src/layouts/DashboardLayout.vue`, `App.vue` — 全局样式入口

### 后端（不在本阶段改）
- `backend/app/api/v1/graph.py` — 6 个死端点已删除 ✅
- `frontend/src/api/schema.ts` — SCHEMA-01~02 已就绪（STATE.md 4/6）

### 测试入口
- `tests/e2e/smoke_test.py` — D-09 复用启动器
- `tests/e2e/test_2d_3d_color_consistency.py` — D-08 新建 Playwright 截图 diff

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `graphColors.ts` 中 `NODE_TYPE_COLORS` / `EDGE_TYPE_COLORS` / `TYPE_INFO` / `KA_FALLBACK_COLORS` 已存在 — D-02 新增 `ECHARTS_PALETTE` 时复用同一文件、不拆分子目录
- `graphColors.ts` 中 `glowColor()` / `nodeColor()` / `edgeColor()` 辅助函数 — D-04 保持不动
- `design-tokens.css` 中 `--space-*` / `--radius-*` / `--shadow-*` / `--elevation-*` / `--text-*` 完整 token 体系 — D-12 复用 `--slate-*`（需先确认存在性）
- `tests/e2e/smoke_test.py` 启动器与 `--base-url` / `--all` 参数约定 — D-09 复用
- Vue `el-color` / Element Plus 主题系统 — 不在本阶段改（已通过 design tokens 间接覆盖）

### Established Patterns
- `import { ... } from '@/utils/graphColors'` — D-01 ECHARTS_PALETTE 沿用同一 import 路径
- `import '...css'` 在 main.ts / App.vue 全局引入 — design-tokens.css 已在 App.vue 引入（Phase 4.3 完成）
- `:style="{ background: typeInfo.color + '22' }"` 透明度拼接模式 — D-14 保留
- `var(--card)`, `var(--muted-foreground)` 等 Element Plus 默认 token — NodeTooltip3D 可直接复用，不需新增

### Integration Points
- `graphColors.ts` — D-01 新增 `ECHARTS_PALETTE` 常量，导出
- `DataDashboard.vue` — D-01 替换 25 处 hex 为 `ECHARTS_PALETTE.*`；D-03 同步改 quality store
- `NodeTooltip3D.vue` — D-12 替换 3 处 hex 为 `var(--slate-*)`
- `design-tokens.css` — D-13 若缺失 `--slate-*` 则新增（slate-200=`#e2e8f0`, slate-400=`#94a3b8`, slate-500=`#64748b`）
- `tests/e2e/test_2d_3d_color_consistency.py` — D-08 新建

</code_context>

<specifics>
## Specific Ideas

- DataDashboard 25 处 hex 中应包含 ECharts series color（最常见）、gauge progress color、grid line color、axis label color、tooltip background 等
- `design-tokens.css` 中应已存在 `--slate-*` 系列（Element Plus 主题 token 通常含完整 slate 阶梯），但需 Phase 5 planner 验证
- 2D/3D 一致性 diff 阈值 ±5 RGB 适用于抗锯齿/glow 渲染；若 3D glow 范围过大则考虑放宽到 ±10
- ECHARTS_PALETTE 子表建议：`ECHARTS_SERIES`（折线/柱状系列色）、`ECHARTS_GAUGE`（仪表盘）、`ECHARTS_AXIS`（轴线/标签）、`ECHARTS_GRID`（网格/分割线），但子表命名最终由 Claude 决定

</specifics>

<deferred>
## Deferred Ideas

- **graphColors.ts 改为读取 CSS var** — D-05 明确 JS 端保留字面量；CSS-var 桥接推 Phase 7+ 架构重构
- **Element Plus 主题全量定制** — 超出 Phase 5 范围；当前通过 design-tokens.css 间接覆盖已够用
- **颜色无障碍审计（WCAG 对比度）** — 超出 Phase 5 范围；可作 Phase 7+ 可访问性增强
- **design tokens 自动化生成（style-dictionary 等）** — 超出 Phase 5 范围；当前手维护已够用
- **Home.vue 拆分与样式解耦** — Phase 6 范围（DEC-006）
- **ECharts dark/light 主题切换** — 当前 dark-only，切换主题超出 Phase 5 范围

</deferred>

---

*Phase: 05-style-unify*
*Context gathered: 2026-07-07*