# StarMap 前端设计重构 — 完整提示词文档

> 基于对 17 个页面、55 个组件、3 个样式文件、2 个工具库的深度审计，以及 Element Plus / ECharts / Vue 3 最佳实践调研。

---

## 一、现状诊断：核心问题清单

### 1.1 设计系统基础断裂（P0 — 必须立即修复）

| 问题 | 影响 | 涉及文件 |
|------|------|----------|
| **`design-tokens.css` 未被导入** | 定义的 104 个 CSS 变量全部为死代码 | `design-tokens.css` 无 import 引用 |
| **`responsive.css` 未被导入** | 5 档响应式系统完全失效 | `responsive.css` 无 import 引用 |
| **`--dash-*` 系列变量运行时为空** | DashboardLayout / DataDashboard / DashboardSkeleton 引用的 `--dash-surface`, `--dash-accent-*`, `--dash-text-*` 全部 resolve 为空值，视觉降级 | 3 个文件引用了不存在的 token |
| **App.vue 与 design-tokens.css 重复定义** | `--leading-tight/normal/relaxed` 三变量重复；`fade-in-up` vs `fadeInUp` 参数不一致 | `App.vue` + `animations.css` |
| **`--dash-connected` / `--dash-disconnected` 定义但从未使用** | 死代码 | `design-tokens.css` |

### 1.2 AI 味视觉问题（P0 — 必须消除）

#### 严重级别（Science-Fiction HUD 风格，必须消除）

| 页面/组件 | AI 味表现 | 具体代码 |
|-----------|-----------|----------|
| **DataDashboard.vue** | KPI 卡片双重辉光 (outer + inset box-shadow)、径向辉光背景、图标发光 (drop-shadow)、数值发光 (text-shadow)、渐变底部线、流水线图标发光 | `box-shadow: 0 0 20px var(--kpi-glow), inset 0 0 20px var(--kpi-glow)`, `radial-gradient`, `filter: drop-shadow(0 0 6px)`, `text-shadow: 0 0 12px` |
| **Login.vue** | 毛玻璃 (backdrop-filter blur + rgba)、3D 背景装饰、9 个硬编码 rgba 颜色、emoji 标题 | `backdrop-filter: blur(20px)`, `rgba(255,255,255,0.08)`, `⭐` |
| **NodeTooltip3D.vue** | 霓虹辉光线、毛玻璃背景、环境光晕 | `tt-glow-line` gradient, `backdrop-filter: blur(16px) saturate(1.5)`, `box-shadow: 0 0 20px` |
| **SkillMatchAnimation.vue** | DOM 粒子爆发动画、图标弹跳、渐变进度条 | `sm-particle` DOM elements, `@keyframes particleFly`, `@keyframes iconPop` |
| **CountUpNumber.vue** | 数字闪动发光 | `text-shadow: 0 0 12px currentColor` in `countFlash` |

#### 中等级别（过度装饰）

| 页面/组件 | AI 味表现 |
|-----------|-----------|
| **HomeGraphSection.vue** | 3D 透视倾斜 (`perspective: 1200px; rotateX(1deg)`)、暗角覆盖、点阵图案、`grain` 噪点 |
| **GraphToolbar.vue** | 毛玻璃 `backdrop-filter: blur(16px) saturate(1.8)` |
| **GraphSearchBar.vue** | `glass` + `border-glow` 类 |
| **PipelineStageCard.vue** | 失败状态脉冲红光 `failed-pulse` animation |
| **LoopTimeline.vue** | 状态圆环柔光 `box-shadow: 0 0 0 4px color-mix(...)` |
| **LoopStepGraph.vue** | 图例点霓虹光、庆祝环动画 |
| **GapAnalysisReport / LoopStepMatch** | 渐变文字 `-webkit-background-clip: text` |
| **PipelineAnalysis.vue** | 5 个 emoji 作标题图标 (`🎯📋📚📖🚀`) |
| **EvolutionDashboard.vue** | 标签脉冲动画、2 个硬编码 rgba |

### 1.3 Emoji 充当图标（P1 — 必须替换）

| 位置 | Emoji | 替换方案 |
|------|-------|----------|
| Login.vue | `⭐` | 删除，用文字品牌 |
| LoopDemo.vue | `🔄` | `RefreshRight` (EP) |
| DataDashboard.vue | `📊🧭📈📡🛰️` | `PieChart`, `Compass`, `TrendCharts`, `Connection`, `Aim` (EP) |
| PipelineAnalysis.vue | `🎯📋📚📖🚀` | `Aim`, `Document`, `Reading`, `Collection`, `Promotion` (EP) |
| LoopStepSkills.vue | `🆕✅` | `Plus`, `Select` (EP) |
| LoopTimeline.vue | `📝🔍🔗📊🗺️` | `Edit`, `Search`, `Connection`, `DataAnalysis`, `MapLocation` (EP) |

### 1.4 硬编码颜色绕过设计系统（P1）

**14 个组件、30+ 个硬编码 hex/rgba 值**，完全不随主题切换：

| 组件 | 硬编码色值 |
|------|-----------|
| AdminFlow / MatchFlow | `#3b82f6`, `#8b5cf6`, `#06b6d4`, `#f59e0b`, `#10b981`, `#ec4899` |
| AdminOverview | `#f59e0b`, `#3b82f6`, `#10b981`, `#6366f1` |
| Graph3D | `#0a0e1a`, `#94a3b8`, `#64748b`, `#e2e8f0`, `#f59e0b`, `rgba(100,116,139,0.2)` |
| NodeTooltip3D | `rgba(10,14,26,0.92)`, `#e2e8f0`, `#94a3b8`, `#cbd5e1` |
| Login.vue | 9 个 rgba 白色透明值 |
| MatchTrustGuide | `#94a3b8`, `#10b981`, `#3b82f6`, `#f59e0b`, `#ef4444` |
| CareerPathGraph | `#dcfce7`, `#fef3c7`, `#fee2e2`, `#dbeafe` |
| ErrorBoundary | `#dc2626`, `#0a0a0b`, `#6b7280`, `#ffffff`, `#4f46e5` |

### 1.5 重复造轮子（P1）

| 现有组件 | 应使用的 Element Plus 组件 |
|----------|--------------------------|
| `DashboardSkeleton.vue` | `el-skeleton` + `el-skeleton-item` |
| `SkeletonCard.vue` | `el-skeleton` |
| `ErrorBoundary.vue` 按钮 | `el-button` |
| `EmptyState.vue` | `el-empty` |
| `LoadingPulse.vue` | `el-skeleton` 或 `v-loading` |
| `HomeKpiBar.vue` ≈ `HomeKpiStrip.vue` | **合并为一个组件** |

### 1.6 重复代码模式（P2）

| 模式 | 重复页面数 | 应提取 |
|------|-----------|--------|
| KPI 卡片 (`.kpi-card` + `::before` glow + hover lift) | 3 页 (DataSources, PipelineMonitor, QualityDashboard) | `<KpiCard>` 通用组件 |
| 业务说明横幅 (`.business-banner` / `.tab-description`) | 5 页 | `<BusinessBanner>` 通用组件 |
| `max-width` 页面容器 | 4 种不同值 (960/1000/1100/1200px) | 统一为 `--layout-content-max` token |
| 渐变顶栏 (`linear-gradient(90deg, var(--primary), var(--chart-2))`) | 5+ 组件 | CSS 工具类或 slot 化的 `<SectionCard>` |

### 1.7 Magic Numbers（P2）

- **100+ 个**不同硬编码像素值分布在 17 个页面中
- 无 design token 覆盖的维度：KPI 数值字号、面板标题字号、状态点尺寸、卡片内边距、事件流间距

---

## 二、设计系统重构方案

### 2.1 Token 架构：三层体系

```
Layer 1: 原始色板 (:root)        → Layer 2: 语义别名 (:root)       → Layer 3: 暗色覆盖 (html.dark)
─────────────────────────────      ─────────────────────────────      ──────────────────────────
--color-blue-500: #409eff          --el-color-primary: #409eff       --surface-base: #141414
--color-green-500: #67c23a         --color-success: #67c23a          --surface-raised: #1d1e1f
--chart-1: #6366f1                 --surface-base: #ffffff           --content-primary: #e5eaf3
                                   --content-primary: #303133        --border-default: #4c4d4f
                                   --border-default: #dcdfe6         --shadow-sm: 0 1px 2px rgba(0,0,0,0.3)
```

**关键原则**：
- 组件只引用 Layer 2 语义 token，绝不直接使用 Layer 1 原始值
- Dark 模式只覆盖 Layer 2，Layer 1 不变
- 消费 Element Plus 的 `--el-*` 变量，而非自建 `--dash-*` 命名空间

### 2.2 消除 `--dash-*` 命名空间

当前 `--dash-accent-5` ~ `--dash-accent-40` 和 `--dash-text-04` ~ `--dash-text-85` 是用 `color-mix()` 从 `--chart-1` 和 `--foreground` 派生的。这些应直接使用 Element Plus 已有的变量：

| 当前 `--dash-*` | 替换为 | 说明 |
|------------------|--------|------|
| `--dash-surface` | `var(--el-bg-color-overlay)` | 暗色下自动为 `#1d1e1f` |
| `--dash-accent-10` | `var(--el-color-primary-light-9)` | 暗色下自动变深 |
| `--dash-text-85` | `var(--el-text-color-primary)` | 暗色下自动变亮 |
| `--dash-text-50` | `var(--el-text-color-secondary)` | 暗色下自动变亮 |
| `--dash-text-30` | `var(--el-text-color-placeholder)` | 暗色下自动适配 |
| `--dash-accent-5` | `var(--el-fill-color-lighter)` | 暗色下自动适配 |

### 2.3 ECharts 主题切换方案

**当前问题**：`chartTheme.ts` 用 `MutationObserver` 监听 `html` class 变化来清缓存，但这只能更新颜色值，无法改变 ECharts 实例的 `backgroundColor` 和调色板。

**推荐方案**：使用 vue-echarts 的 `THEME_KEY` provide/inject：

```ts
// composables/useTheme.ts
import { provide, ref, watch } from 'vue'
import { THEME_KEY } from 'vue-echarts'
import { useDark } from '@vueuse/core'

const isDark = useDark()
const chartTheme = ref(isDark.value ? 'dark' : '')
watch(isDark, (dark) => { chartTheme.value = dark ? 'dark' : '' })
provide(THEME_KEY, chartTheme)
```

注册自定义 ECharts 主题对齐 Element Plus 暗色调色板：
```ts
import * as echarts from 'echarts'
echarts.registerTheme('el-dark', { /* 基于 --el-color-* dark 值 */ })
```

### 2.4 暗色模式规范（NN/g 研究结论）

1. **禁止纯黑 `#000000` 作背景** → 使用 `#141414`（Element Plus 默认）
2. **暗色下降低饱和度** → Element Plus dark CSS vars 已处理
3. **Elevation = 更亮的面** → `#1d1e1f` > `#141414` > `#0a0a0a`
4. **最小对比度 4.5:1** → Element Plus dark tokens 已满足

---

## 三、AI 味消除 — 逐项替换清单

### 3.1 KPI 卡片：从科幻 HUD 到专业数据卡

```css
/* ═══ 删除 ═══ */
.kpi-card:hover {
  box-shadow: 0 0 20px var(--kpi-glow), inset 0 0 20px var(--kpi-glow);  /* 双重辉光 */
  transform: translateY(-2px);                                               /* 悬浮 */
}
.kpi-glow-bg { /* 整个元素删除 */ }
.kpi-border-bottom { /* 整个元素删除 */ }
.kpi-icon { filter: drop-shadow(0 0 6px var(--kpi-glow)); }                /* 图标发光 */
.kpi-value { text-shadow: 0 0 12px var(--kpi-glow); }                      /* 文字发光 */

/* ═══ 替换为 ═══ */
.kpi-card {
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.kpi-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--el-border-color);
}
.kpi-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  letter-spacing: -0.5px;
}
```

### 3.2 通用替换规则

| AI 味代码 | 替换为 |
|-----------|--------|
| `box-shadow: 0 0 Npx color` (辉光) | `box-shadow: var(--shadow-sm)` |
| `backdrop-filter: blur(Npx)` (毛玻璃) | `background: var(--el-bg-color-overlay)` |
| `-webkit-background-clip: text` (渐变文字) | `color: var(--el-text-color-primary)` |
| `text-shadow: 0 0 Npx` (文字发光) | 删除 |
| `filter: drop-shadow(0 0 Npx)` (图标发光) | 删除 |
| `transform: translateY(-Npx)` (悬浮) | 删除或改为 `box-shadow` 提升 |
| `radial-gradient(circle, ...)` 辉光背景 | 删除 |
| `linear-gradient(90deg, transparent, color, transparent)` 底线 | 删除或改为 `border-bottom: 2px solid` |
| `animation: pulse-glow Ns infinite` (持续脉冲) | `transition: all 0.2s ease`（仅在状态变更时触发） |
| `::before { opacity: 0→1 on hover }` 渐变覆盖 | 删除 |
| `color-mix(in srgb, var(--primary) 4%, transparent)` 覆盖 | `background: var(--el-fill-color-light)` |
| `color + '18'` JS 十六进制透明度 hack | `color: var(--el-color-primary-light-9)` |

### 3.3 动画规范

| 保留 | 删除 | 原因 |
|------|------|------|
| `fadeInUp` | `celebratePulse` | 庆祝动画无业务意义 |
| `skeletonShimmer` | `particleBurst` | DOM 粒子过度动画 |
| `dash-typing-pulse` | `pulseGlow` | 文字发光无信息量 |
| `progressFill` | `failed-pulse` | 持续红光脉冲→改为静态红色边框 |
| 页面过渡 | `loopCelebrate` | 庆祝环动画→改为 `el-result` |
| `highlightFlash` (数据更新闪烁) | `iconPop` | 弹跳动画→改为 `transition` |

---

## 四、组件重构清单

### 4.1 需新建的通用组件

| 组件 | 取代 | 关键设计规范 |
|------|------|-------------|
| `<KpiCard>` | 3 页重复的 KPI 卡片代码 | 使用 `el-card`，无辉光，无悬浮，数据密度优先 |
| `<BusinessBanner>` | 5 页重复的业务说明区 | 使用 `el-alert` + slot，统一 `.banner-meta` 样式 |
| `<SectionCard>` | 渐变顶栏 + 面板卡片 | 使用 `el-card`，标题用 `el-text`，无渐变装饰线 |
| `<StatusDot>` | 各处脉冲/发光状态点 | 纯色 `border-radius: 50%`，状态变更用 `transition` |

### 4.2 需合并的组件

| 保留 | 删除 | 说明 |
|------|------|------|
| `HomeKpiStrip.vue` | `HomeKpiBar.vue` | 功能完全重复，合并为 `HomeKpiStrip.vue` |

### 4.3 需用 Element Plus 替换的组件

| 现有 | 替换方案 | 迁移要点 |
|------|----------|----------|
| `DashboardSkeleton.vue` | `el-skeleton` + `el-skeleton-item` | 用 `#template` slot 匹配真实布局结构 |
| `SkeletonCard.vue` | `el-skeleton` | 同上 |
| `EmptyState.vue` | `el-empty` + `description` slot | 迁移 `icon` prop → `image` slot |
| `ErrorBoundary.vue` 按钮 | `el-button type="primary"` | 删除自定义按钮 CSS |
| `LoadingPulse.vue` | `el-skeleton :rows="3" animated` | 或使用 `v-loading` |

### 4.4 Emoji → Element Plus Icon 映射表

```ts
// 替换映射（用于全局搜索替换）
const EMOJI_TO_ICON: Record<string, { icon: string; lib: 'ep' | 'custom' }> = {
  '📊': { icon: 'PieChart', lib: 'ep' },
  '🧭': { icon: 'Compass', lib: 'ep' },
  '📈': { icon: 'TrendCharts', lib: 'ep' },
  '📡': { icon: 'Connection', lib: 'ep' },
  '🛰️': { icon: 'Aim', lib: 'ep' },
  '🎯': { icon: 'Aim', lib: 'ep' },
  '📋': { icon: 'Document', lib: 'ep' },
  '📚': { icon: 'Reading', lib: 'ep' },
  '📖': { icon: 'Collection', lib: 'ep' },
  '🚀': { icon: 'Promotion', lib: 'ep' },
  '⭐': { icon: 'Star', lib: 'ep' },
  '🔄': { icon: 'RefreshRight', lib: 'ep' },
  '🆕': { icon: 'Plus', lib: 'ep' },
  '✅': { icon: 'Select', lib: 'ep' },
  '📝': { icon: 'Edit', lib: 'ep' },
  '🔍': { icon: 'Search', lib: 'ep' },
  '🔗': { icon: 'Connection', lib: 'ep' },
  '🗺️': { icon: 'MapLocation', lib: 'ep' },
}
```

---

## 五、外部资源与依赖规划

### 5.1 需新增的依赖

| 包 | 用途 | 版本建议 |
|----|------|----------|
| `@vueuse/core` | `useDark` / `useToggle` 暗色模式切换 | `^12.0.0` |

### 5.2 已有依赖的充分利用

| 包 | 当前使用方式 | 应改进为 |
|----|-------------|----------|
| `element-plus@2.14.2` | 未导入 dark CSS vars | `import 'element-plus/theme-chalk/dark/css-vars.css'` |
| `@element-plus/icons-vue@2.3.2` | 部分使用，混杂 emoji | 全部替换 emoji → EP icon (294 图标可用) |
| `vue-echarts@6.7.3` | 未使用 THEME_KEY provide | 用 `THEME_KEY` + reactive ref 实现主题切换 |
| `echarts@6.1.0` | 用 chartTheme.ts MutationObserver | 注册自定义 `el-dark` 主题 + THEME_KEY |

### 5.3 Element Plus 暗色变量速查（项目已有 2.14.2）

```css
/* 背景 */
--el-bg-color           /* #ffffff → #141414 */
--el-bg-color-page      /* #f2f3f5 → #0a0a0a */
--el-bg-color-overlay   /* #ffffff → #1d1e1f */

/* 文字 */
--el-text-color-primary   /* #303133 → #e5eaf3 */
--el-text-color-regular   /* #606266 → #cfd3dc */
--el-text-color-secondary /* #909399 → #a3a6ad */
--el-text-color-placeholder /* #a8abb2 → #8d9095 */

/* 边框 */
--el-border-color         /* #dcdfe6 → #4c4d4f */
--el-border-color-lighter /* #ebeef5 → #363637 */

/* 填充 */
--el-fill-color           /* #f0f2f5 → #303030 */
--el-fill-color-lighter   /* #fafafa → #1d1d1d */

/* 主色阶 (success/warning/danger/info 同理) */
--el-color-primary-light-3  /* #79bbff → #3375b9 */
--el-color-primary-light-5  /* #a0cfff → #2a598a */
--el-color-primary-light-9  /* #ecf5ff → #18222b */
```

---

## 六、实施计划

### Phase 1: 设计系统基础修复 (2-3h)

1. **导入 `design-tokens.css`**：在 `App.vue` 中 `import '@/styles/design-tokens.css'`
2. **导入 `responsive.css`**：在 `App.vue` 中 `import '@/styles/responsive.css'`
3. **导入 Element Plus dark CSS**：`import 'element-plus/theme-chalk/dark/css-vars.css'`
4. **添加 `@vueuse/core`**：`npm install @vueuse/core`
5. **创建 `composables/useTheme.ts`**：整合 `useDark` + ECharts `THEME_KEY`
6. **消除 `--dash-*` token**：替换为 `--el-*` 对应变量
7. **注册 ECharts 自定义主题**：`el-dark` 主题对齐 Element Plus 暗色调色板
8. **删除 App.vue 与 animations.css 重复的动画定义**

### Phase 2: AI 味全局消除 (3-4h)

1. **DataDashboard.vue**：删除所有辉光/发光/渐变装饰，替换为专业数据卡样式
2. **Login.vue**：删除毛玻璃、硬编码 rgba、emoji，用 `el-card` + design tokens
3. **NodeTooltip3D.vue**：删除辉光线、毛玻璃，用 `--el-bg-color-overlay` + 边框
4. **SkillMatchAnimation.vue**：删除粒子爆发、弹跳，改为平滑 `transition`
5. **CountUpNumber.vue**：删除 `text-shadow` 发光
6. **Graph3D / GraphToolbar / GraphSearchBar**：删除 `backdrop-filter` 毛玻璃，用实色背景
7. **所有渐变文字**：替换为 `color: var(--el-text-color-primary)`
8. **所有持续脉冲动画**：替换为状态变更 `transition`

### Phase 3: 组件统一重构 (3-4h)

1. **创建 `<KpiCard>` 通用组件**：合并 3 页 KPI 卡片代码
2. **创建 `<BusinessBanner>` 通用组件**：合并 5 页业务说明区
3. **创建 `<SectionCard>` 通用组件**：统一面板卡片样式
4. **替换 DashboardSkeleton / SkeletonCard** → `el-skeleton`
5. **替换 EmptyState** → `el-empty`
6. **替换 ErrorBoundary 按钮** → `el-button`
7. **合并 HomeKpiBar + HomeKpiStrip** → `HomeKpiStrip`
8. **所有 Emoji 替换为 Element Plus Icon**

### Phase 4: 硬编码颜色 & Magic Number 清理 (2-3h)

1. **14 个组件的 30+ 硬编码颜色** → 全部替换为 design tokens
2. **`+ '18'` 十六进制透明度 hack** → `var(--el-color-*-light-9)`
3. **所有 `max-width` 魔法数字** → 统一为 `var(--layout-content-max)`
4. **所有 KPI/面板字号/间距** → 映射到 typography + spacing token
5. **所有 `style="height: Npx"` 内联样式** → CSS 类 + token

### Phase 5: 验证 (1-2h)

1. `vue-tsc --noEmit` 零错误
2. `vite build` 成功
3. Playwright 截图对比：暗色/亮色模式下所有页面
4. 对比检查：所有 AI 味已消除
5. 对比检查：所有 Emoji 已替换
6. 对比检查：零硬编码颜色
7. 响应式验证：1920 / 1440 / 1024 / 768 断点

---

## 七、设计风格目标

### 当前风格（AI 生成感强）

```
辉光卡片 + 霓虹色 + 毛玻璃 + 渐变文字 + 粒子动画 + emoji 图标 + 硬编码颜色
= "科幻仪表盘" / "赛博朋克 HUD"
```

### 目标风格（专业数据产品）

```
实色卡片 + Element Plus 语义色 + 清晰边框 + 纯色文字 + 状态变更过渡 + 图标库 + design tokens
= "企业级数据平台"（参考 Ant Design Pro / Element Plus Admin / Grafana）
```

### 关键视觉原则

1. **数据密度 > 装饰密度**：每个像素都应承载信息，不是装饰
2. **Elevation 用阴影，不用辉光**：`box-shadow: var(--shadow-sm)` 而非 `0 0 20px glow`
3. **颜色表达语义，不是情绪**：`--el-color-primary` (操作)、`--el-color-success` (正向)、`--el-color-danger` (警告)——不用于"好看"
4. **动画服务于反馈，不是装饰**：`transition: all 0.2s ease`（状态变更）而非 `animation: pulse 2s infinite`（持续脉冲）
5. **暗色模式是功能需求，不是美学选择**：必须遵循 `--el-bg-color` → `--el-text-color-primary` 对比度体系

---

## 八、参考资源

- [Element Plus Dark Mode](https://element-plus.org/en-US/guide/dark-mode.html)
- [vue-echarts Theme](https://github.com/ecomfe/vue-echarts#theme)
- [Ant Design 数据展示规范](https://ant-design.antgroup.com/docs/spec/data-display-en)
- [Material Design Dark Theme Elevation](https://m3.material.io/styles/color/dark-theme/overview)
- [NN/g Dark Mode Research](https://www.nngroup.com/articles/dark-mode/)
- [VueUse useDark](https://vueuse.org/core/usedark/)
