# Phase 5: 样式统一与体验优化 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 05-style-unify
**Areas discussed:** DataDashboard 112 处迁移顺序, graphColors.ts 与 design tokens 桥接, 2D/3D KA 一致性验证手段, NodeTooltip3D 残留处理

---

## Area 1: DataDashboard.vue 112 处 hex 迁移顺序

| Option | Description | Selected |
|--------|-------------|----------|
| 批量迁移 | 一次性聚合 112 处 hex 到 ECHARTS_PALETTE | ✓ |
| 分批迁移 | 按 chart/卡片/状态分组分批 PR | |

**User's choice:** 批量迁移（4 个候选 area 都选了，未单独再问）
**Notes:** STATE.md 显示 112 处散布在 28 文件，主要集中在 DataDashboard.vue（25 hex）。颜色聚合后才能正确导入 ECHARTS_PALETTE，分批会产生中间态。

## Area 2: DataDashboard 中 ECharts 颜色归宿

| Option | Description | Selected |
|--------|-------------|----------|
| 新增 ECHARTS_PALETTE 到 graphColors.ts | 图表主题色与图谱节点色语义隔离 | ✓ |
| 全迁到 design tokens | TS 端需同步读 CSS | |
| 仅 Vue 模板 hex → var(--*) | 最少改动 | |

**User's choice:** 新增 ECHARTS_PALETTE 到 graphColors.ts（推荐）
**Notes:** 图表色板 vs 节点色板是两套语义独立的体系；ECHARTS_PALETTE 与 NODE_TYPE_COLORS 共存。

## Area 3: graphColors.ts 与 design tokens 桥接

| Option | Description | Selected |
|--------|-------------|----------|
| JS 端保留 hex 字面量 | 双体系并存：CSS var 用于 Vue 模板，TS 字面量用于 canvas/ECharts | ✓ |
| TS 读 CSS var | 引入 getComputedStyle，运行时开销 | |
| 全改 CSS var | graphColors.ts 不可能纯 CSS | |

**User's choice:** JS 端保留 hex 字面量（默认推荐）
**Notes:** G6/Three.js/ECharts 直接消费 JS 字符串，引入 CSS var 桥接会复杂化。

## Area 4: 2D/3D KA 一致性验证

| Option | Description | Selected |
|--------|-------------|----------|
| Playwright 截图 diff 脚本 | tests/e2e/test_2d_3d_color_consistency.py，±5 RGB 容差 | ✓ |
| 源码静态检查调色板引用 | 快但不可证明 canvas 输出 | |
| 不验证 | 入口统一即视为一致 | |

**User's choice:** Playwright 截图 diff 脚本（推荐）
**Notes:** ±5 RGB 容差应对抗锯齿/glow；复用现有 smoke_test.py 启动器。

## Area 5: NodeTooltip3D 中 Slate 系 hex 处理

| Option | Description | Selected |
|--------|-------------|----------|
| 仅换 var(--slate-200/400/500) | 纯 Vue 模板、CSS 解析 | ✓ |
| 在 graphColors.ts 加 SLATE 常量 | 允许 JS 动态控制 | |
| 合并到现有 DEFAULT 色系 | 需要 6 个变量 | |

**User's choice:** 仅换 var(--slate-200/400/500)（推荐）
**Notes:** 前提是 design-tokens.css 中已存在 --slate-*；若缺失则 Phase 5 planner 同步补全。

---

## Claude's Discretion

- ECHARTS_PALETTE 子表命名（建议 ECHARTS_SERIES/GAUGE/AXIS/GRID）
- 颜色分类标准（HEX 值相同但用法不同时如何处理）
- Playwright 脚本中「同一 KA 节点」的选择策略
- 截图采样区域大小
- DataDashboard.vue 内 25 hex 是否全部归类到 ECHARTS_PALETTE 还是部分归 NODE_TYPE_COLORS
- NodeTooltip3D 中若 --slate-* 不存在是否同步补全

## Deferred Ideas

- graphColors.ts 改为读取 CSS var → Phase 7+
- Element Plus 主题全量定制 → Phase 7+
- 颜色无障碍审计（WCAG 对比度）→ Phase 7+ 可访问性
- design tokens 自动化生成（style-dictionary 等）→ Phase 7+
- Home.vue 拆分与样式解耦 → Phase 6（DEC-006）
- ECharts dark/light 主题切换 → Phase 7+