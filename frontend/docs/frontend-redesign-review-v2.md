# StarMap 前端 UI/UX 重构评审报告 v2

**评审日期**: 2026-06-30
**评审范围**: 7 页面 + 4 组件 + 1 布局 + 全局设计系统
**参考体系**: shadcn-ui (布局语义) + Magic UI (微动效) + FlyonUI (数据卡片)

---

## 1. 重构总览

### 1.1 已完成改动

| 模块 | 文件 | 改动类型 | 关键变更 |
|------|------|---------|---------|
| 布局 | `MainLayout.vue` | 架构重构 | 折叠按钮移至 header、暗色 sidebar、route watcher、折叠态 CSS |
| 首页 | `Home.vue` | 视觉优化 | KPI grid 布局、面板 sticky header、搜索栏 focus 效果、shadow 升级 |
| 匹配 | `MatchDiagnosis.vue` | 微调 | step-card shadow 升级 |
| 演化 | `EvolutionDashboard.vue` | 保持 | 已有视觉模式一致 |
| 质量 | `QualityDashboard.vue` | 保持 | 已有视觉模式一致 |
| 岗位列表 | `PositionList.vue` | 修复 | 标题权重、hover 距离、硬编码间距 |
| 岗位详情 | `PositionDetail.vue` | 增强 | 标题权重、section title 大写、卡片容器 |
| JD 抽取 | `ExtractJD.vue` | 优化 | 标题样式、section title 层级 |
| 管理 | `Admin.vue` | 优化 | 标题权重、间距 token 化 |
| 图谱工具栏 | `GraphToolbar.vue` | 微调 | 按钮尺寸、间距 |
| 技能雷达 | `SkillRadar.vue` | 微调 | 标题字号 |
| 简历上传 | `ResumeUpload.vue` | 微调 | 上传区 padding、文字大小 |
| 岗位搜索 | `PositionSearch.vue` | 保持 | 已有样式一致 |
| 全局 | `App.vue` | 增强 | card/button/table 统一覆盖 |

### 1.2 设计系统增强

**App.vue 新增全局覆盖**:
- `.el-card`: 统一 `radius-xl`、`shadow-xs`、hover `shadow-sm`
- `.el-button`: 统一 `font-weight: 500`、`letter-spacing`、`transition`
- `.el-table`: 统一 `radius-lg`、`overflow: hidden`

---

## 2. 反 AI 味检查清单

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Emoji | 0 个 | 全部使用 SVG 图标 |
| 通用空状态 | 已消除 | 自定义 SVG + 上下文化文案 |
| 硬编码色值 | 仅 Token 定义 | 组件样式中 0 个硬编码色 |
| CSS 变量引用 | 全量 Token 化 | 713+ 处引用 |
| 微噪点纹理 | .grain 类 | 图谱容器应用 |
| 交错入场 | .stagger 类 | KPI 卡片应用 |
| 弹性动效 | ease-spring | 按钮/卡片交互 |
| 排版紧凑 | tracking-tight | 标题统一 -0.025em |
| 数字等宽 | tabular-nums | 数据值统一 |
| 渐变克制 | 仅匹配分数 | 不做满屏渐变 |

---

## 3. 构建验证

| 检查 | 结果 |
|------|------|
| ESLint | 0 errors, 0 warnings |
| vue-tsc --noEmit | 0 errors |
| Vite build | 18.69s 成功 |
| 文件数 | 14 个 .vue 文件 |
| 总行数 | ~5,600 行 |

---

## 4. 遗留项

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 中 | Home.vue 拆分 | 1603 行，建议提取 DetailPanel.vue |
| 中 | Pencil 高保真原型 | MCP transport 不可用，待恢复后制作 |
| 低 | 页面过渡动画 | page-slide 变体已创建，需 router meta 配置 |
| 低 | 图表 legend 文字色 | ECharts legend 应使用 chartColors().muted |

---

## 5. 设计参考来源

| 来源 | 引用内容 | 应用位置 |
|------|----------|----------|
| shadcn-ui | 语义化 Token 体系、Sidebar 布局、Card 模式 | App.vue、MainLayout、全局 |
| Magic UI | Bento Grid、grain 纹理、stagger 动画 | App.vue 工具类、KPI 卡片 |
| FlyonUI | Stat 卡片模式（标题+值+描述）、进度条 | Home.vue KPI、QualityDashboard |
| Element Plus | 组件库基础，Token 覆盖 | 全局组件 |
