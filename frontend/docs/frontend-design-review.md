# StarMap 前端 UI/UX 设计评审报告

**评审日期**: 2026-06-30
**评审范围**: 全部 14 个 Vue 组件/页面
**设计基准**: shadcn-ui 语义化 Token 体系 + Magic UI 微交互 + FlyonUI 统计卡片模式

---

## 1. 设计系统架构

### 1.1 Token 体系（App.vue）
| 维度 | 状态 | 说明 |
|------|------|------|
| 语义色 | 完备 | background/foreground/card/primary/secondary/muted/accent + 5 个语义色 |
| 中性色 | 优化 | 从 slate 迁移至 zinc 基调，降低饱和度，更专业 |
| 间距 | 14 级 | space-0 至 space-16，4px 递增 |
| 圆角 | 7 级 | radius-xs(0.25rem) 至 radius-full(9999px) |
| 阴影 | 6 层 | xs/sm/md/lg/xl + glow 变体 |
| 排版 | 8 级 | font-size-xs(0.6875rem) 至 font-size-4xl(2rem) |
| 动效 | 3 曲线 | ease-out/ease-in-out/ease-spring + 4 级时长 |
| Z 轴 | 7 层 | base/dropdown/sticky/overlay/modal/popover/tooltip |
| 暗色 | 完备 | 全量 Token 暗色映射，增强阴影深度 |
| 组件桥接 | 覆盖 | el-card/el-button/el-input/el-tag/el-table/el-step 全部覆盖 |

### 1.2 工具类
| 工具 | 来源 | 用途 |
|------|------|------|
| .glass | 自研 | 毛玻璃效果 (backdrop-filter) |
| .grain | Magic UI | 微噪点纹理，消除 AI 模板感 |
| .stagger | Magic UI | 子元素交错入场动画 |
| .border-glow | shadcn-ui | 悬停边框辉光 |
| .card-interactive | FlyonUI | 可交互卡片悬停/按压效果 |
| .hover-lift | 自研 | 悬停上浮 |
| .animate-fade-in | 自研 | 淡入上移入场 |
| .skeleton | shadcn-ui | 骨架屏加载态 |
| .section-header | FlyonUI | 区域标题布局 |
| .custom-empty | 自研 | 自定义空状态（替代 el-empty） |

### 1.3 图表主题桥接（chartTheme.ts）
- chartColors() — 运行时读取 CSS 变量，ECharts/G6 兼容
- tooltipStyle() / splitLineStyle() / axisLabelStyle() — 共享配置
- gaugeColor(value) — CII 仪表盘阈值着色
- 覆盖 24+ 处图表调用

---

## 2. 布局架构

### 2.1 MainLayout — 侧边栏导航
| 特性 | 实现 | 参考 |
|------|------|------|
| 固定侧边栏 | 260px，可折叠至 64px | shadcn-ui Sidebar |
| 分组导航 | 数据/工具/洞察/系统 4 组 | shadcn-ui SidebarGroup |
| 活跃指示器 | 左边缘 3px 圆角条 | shadcn-ui |
| 品牌标识 | SVG 星轨图标 + 辉光悬停 | 自研 |
| 移动端 | 玻璃顶栏 + 汉堡菜单 | 响应式断点 1024px |
| 面包屑 | 顶栏下方 | 标准模式 |

---

## 3. 页面逐项评审

### 3.1 全景图谱（Home.vue — 1487 行）
| 模块 | 评审 | 改进点 |
|------|------|--------|
| KPI 卡片 | 交错入场 + 趋势描述 + 渐变悬停 | — |
| 图谱容器 | 圆角 2xl + grain 纹理 + 浮动工具栏 | — |
| 搜索栏 | 玻璃效果 + focus glow | — |
| 详情面板 | hover-lift + 类型徽章 + 雷达图 | — |
| 空状态 | 自定义 SVG + 语义化文案 | — |
| 组件拆分 | 1487 行过大 | 建议提取 DetailPanel.vue / GraphSearchBar.vue |

### 3.2 匹配诊断（MatchDiagnosis.vue — 588 行）
| 模块 | 评审 | 改进点 |
|------|------|--------|
| 步骤卡片 | 顶部渐变条 + 2xl 圆角 | — |
| 报告摘要 | 渐变背景 + 渐变文字分数 | — |
| 差距表格 | Element Plus 表格 + Token 覆盖 | — |
| 空状态 | 上下文化文案 | — |

### 3.3 演化看板（EvolutionDashboard.vue — 456 行）
| 模块 | 评审 | 改进点 |
|------|------|--------|
| CII 仪表盘 | 实时徽章 + 卡片头布局 | — |
| 新兴技能 | 左侧绿色条 + 悬停上浮 | — |
| 对比模块 | VS 标识 + 选择器 | — |
| 空状态 | 自定义 SVG + 语义化文案 | — |

### 3.4 图谱质量（QualityDashboard.vue — 540 行）
| 模块 | 评审 | 改进点 |
|------|------|--------|
| KPI 卡片 | 渐变悬停 + 数字等宽 | — |
| 图表区域 | chartTheme 统一 | — |
| 空状态 | 自定义 SVG + 区分数据源/图表 | — |

### 3.5 其他页面
| 页面 | 状态 | 说明 |
|------|------|------|
| Admin.vue | 完成 | 管理后台，表单+表格为主 |
| ExtractJD.vue | 完成 | 输入/输出双栏，空状态已优化 |
| PositionList.vue | 完成 | 列表+筛选，自定义空状态+引导按钮 |
| PositionDetail.vue | 完成 | 详情展示，Token 化完成 |

### 3.6 组件
| 组件 | 状态 | 说明 |
|------|------|------|
| GraphToolbar | 完成 | 毛玻璃 + 圆角 xl + 按压缩放 |
| ResumeUpload | 完成 | 渐变悬停上传区 + 圆角 2xl |
| SkillRadar | 完成 | 粗标题 + 自定义空状态 |
| PositionSearch | 完成 | Token 化完成 |

---

## 4. 杜绝 AI 味检查清单

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Emoji | 0 个 | 全部替换为 SVG 图标 |
| 通用空状态 | 已消除 | 10 个 el-empty 已替换为自定义 SVG + 上下文化文案 |
| 硬编码十六进制 | 仅 Token 定义 | 组件样式中 0 个硬编码色值 |
| CSS 变量引用 | 713 处 | 全量 Token 化 |
| 内联样式 | 10 处 | 均为动态 :style 绑定（可接受） |
| 微噪点纹理 | .grain 类 | 图谱容器应用 |
| 交错入场 | .stagger 类 | KPI 卡片应用 |
| 弹性动效 | ease-spring | 按钮/卡片交互 |
| 排版紧致 | tracking-tight | 标题统一 -0.025em |
| 数字等宽 | tabular-nums | 数据值统一 |

---

## 5. 设计参考来源

| 来源 | 引用内容 | 应用位置 |
|------|----------|----------|
| shadcn-ui | 语义化 Token 体系、Sidebar 布局、Card 模式 | App.vue、MainLayout、全局 |
| Magic UI | Bento Grid、grain 纹理、stagger 动画 | App.vue 工具类、KPI 卡片 |
| FlyonUI | Stat 卡片模式（标题-值-描述）、进度条 | Home.vue KPI、QualityDashboard |
| Element Plus | 组件库基座，Token 覆盖 | 全局组件 |

---

## 6. 遗留项与建议

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 中 | Home.vue 拆分 | 1487 行，建议提取 DetailPanel.vue + GraphSearchBar.vue |
| 中 | Pencil 高保真稿 | MCP 不可用，待恢复后制作 Home/MatchDiagnosis 原型 |
| 低 | 页面过渡动画 | page-slide 变体已创建，需 router meta 配置 |
| 低 | 图表 legend 文字色 | ECharts legend 应使用 chartColors().muted |
| 低 | Home.vue KA_FALLBACK_COLORS | 14 色硬编码数组，可替换为 chartColors().chart 扩展 |

---

## 7. 构建状态

| 检查 | 结果 |
|------|------|
| vue-tsc --noEmit | 0 错误 |
| vite build | 11.9s |
| 文件数 | 14 个 .vue 文件 |
| 总行数 | 5,660 行 |
| Token 引用 | 713 处 |
| Emoji | 0 |
| 硬编码色值 | 仅 Token 定义 |