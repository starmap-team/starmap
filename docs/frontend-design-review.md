# StarMap 前端 UI/UX 设计评审报告

## 设计体系概述

### 设计原则
- **消除 AI 模板感**: 无 emoji、自定义 SVG 图标、紧凑字间距 (-0.01em)
- **语义化设计令牌**: 参照 shadcn-ui 架构，399 个 var() 引用
- **深色模式兼容**: 所有图表/图谱通过 cv() 和 chartColors() 运行时解析 CSS 变量
- **毛玻璃导航**: glassmorphism sticky nav (backdrop-filter: blur(12px))

### 色彩系统
| 令牌 | 亮色模式 | 暗色模式 | 用途 |
|------|---------|---------|------|
| --primary | #4F46E5 (Indigo) | #818CF8 | 主操作、导航激活 |
| --foreground | #0F172A (Slate 900) | #E2E8F0 | 正文文字 |
| --muted-foreground | #64748B | #94A3B8 | 次要文字 |
| --border | #E2E8F0 | #1E293B | 边框、分隔线 |
| --success | #10B981 | #34D399 | 成功、上升趋势 |
| --warning | #F59E0B | #FBBF24 | 警告、CII 偏高 |
| --destructive | #EF4444 | #F87171 | 错误、下降趋势 |

### 排版系统
- 字体栈: Inter → PingFang SC → Microsoft YaHei → 系统字体
- 字号阶梯: xs(12px) / sm(13px) / base(14px) / lg(16px) / xl(18px) / 2xl(20px) / 3xl(24px)
- 字间距: body -0.01em, headings -0.02em, labels +0.05em (uppercase)

### 间距系统
- 4px 递进: space-1(4px) → space-2(8px) → space-3(12px) → space-4(16px) → space-5(20px) → space-6(24px)
- 圆角: radius-sm(3.75px) / radius-md(5px) / radius-lg(6.25px) / radius-xl(8.75px)

## 页面级评审

### 1. 全景图谱 (Home.vue)
- **KPI 指标卡**: 带语义色图标，hover 浮起效果
- **图谱控制栏**: 面包屑导航 + 视图模式切换 + 图例 + 演化边开关
- **浮动工具栏**: 毛玻璃背景，放大/缩小/居中/布局切换
- **右侧详情面板**: 节点类型徽章、技能雷达图、属性列表、相似岗位
- **底部搜索栏**: 毛玻璃背景，实时搜索下拉，键盘导航
- **暗色模式**: 所有 G6 节点颜色通过 cv() 运行时解析

### 2. 匹配诊断 (MatchDiagnosis.vue)
- **步骤引导**: 4 步流程 (录入 → 选岗 → 雷达对比 → 差距报告)
- **报告摘要**: 渐变顶部装饰条 + 大号匹配分数
- **差距表格**: 必备/加分标签 + 差距程度 + 学习路径

### 3. 演化看板 (EvolutionDashboard.vue)
- **CII 仪表盘**: 动态阈值着色 (绿/黄/红)
- **新兴技能卡**: hover 浮起 + 成功色边框
- **趋势曲线**: 多技能 CII 时序对比
- **技能对比**: 双技能 VS 对比图

### 4. 图谱质量 (QualityDashboard.vue)
- **4 指标卡**: 总节点/信任度/幻觉率/待审核
- **信任度直方图**: 6 段渐变色柱状图
- **幻觉率趋势**: 面积图 + 10% 预警线
- **数据源饼图**: 环形图展示来源分布

### 5. JD 抽取 (ExtractJD.vue)
- **双栏布局**: 左侧输入 + 右侧结果
- **进度指示**: 模拟 AI 分析进度条
- **结果展示**: 描述列表 + 技能标签 + 标准化表格

### 6. 岗位列表 (PositionList.vue)
- **行业筛选**: 标签式筛选器
- **卡片网格**: 响应式 4 列布局

## 技术实现质量

### 设计令牌覆盖率
- 399 个 var() 引用覆盖所有颜色、间距、字号、圆角、阴影
- 24 个 chartColors() 调用确保图表主题一致
- 21 个 cv() 调用确保 Canvas 渲染暗色模式兼容

### 代码质量
- 内联样式: 10 个 (从 73 个减少 86%)
- 硬编码颜色: 0 个 (非 App.vue 定义文件)
- Emoji: 0 个
- TypeScript: 零错误
- 构建时间: ~12s

### 待改进项
- Home.vue 组件拆分 (1573 行 → GraphToolbar/DetailPanel/SearchBar)
- Pencil 高保真原型 (MCP 当前不可用)
- ECharts tooltip 暗色模式样式统一
- 剩余 10 个内联样式 (均为可接受的动态绑定)