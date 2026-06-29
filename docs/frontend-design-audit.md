# StarMap 前端 UI/UX 重设计 — 设计审计报告
# Design Audit Report

## 项目现状分析

### 技术栈
- Vue 3.4 + TypeScript 5.4 + Vite 5.2
- Element Plus 2.6 (UI库)
- AntV G6 5.0 (知识图谱可视化)
- ECharts 5.5 + vue-echarts (图表)
- Pinia 2.1 (状态管理)
- vue-router 4.3 (路由)
- sass 1.72 (样式)

### 页面清单 (8个页面)
1. **Home.vue** (~1600行) — 全景图谱 (核心页面，G6图谱+KPI+搜索)
2. **PositionList.vue** (~230行) — 岗位列表 (卡片网格)
3. **PositionDetail.vue** — 岗位详情
4. **MatchDiagnosis.vue** (~757行) — 匹配诊断 (5步向导)
5. **EvolutionDashboard.vue** (~743行) — 演化看板 (CII时序+新兴技能)
6. **QualityDashboard.vue** (~627行) — 图谱质量 (KPI+图表+审核队列)
7. **ExtractJD.vue** (~308行) — JD抽取 (文本输入+结果)
8. **Admin.vue** (~525行) — 管理后台 (审核+数据源)

### 已完成的设计改进 (Prior Session)
- ✅ 设计Token系统 v3 (App.vue) — 完整的语义化token
- ✅ Obsidian暖色Stone调色板 (Dark Mode)
- ✅ 侧边栏重构 (MainLayout.vue) — 可折叠+分组+active indicator
- ✅ 硬编码hex颜色消除 (大部分页面)
- ✅ stat-card/page-header等工具类
- ✅ 玻璃态效果 (backdrop-filter: blur(16px))
- ✅ 自定义空状态 (无emoji)
- ✅ 过渡动画 (stagger-in, page-fade)

### AI味模式识别 (需改进)

#### 高优先级
1. **Home.vue 体量过大** — 1600行单文件，需拆分组件
   - 提取 DetailPanel.vue (右侧节点详情)
   - 提取 GraphSearchBar.vue (底部搜索)
   - 提取 KPIStrip.vue (顶部KPI指标)

2. **Element Plus 组件直接使用** — 缺乏自定义感
   - el-card shadow="hover" → 自定义card组件
   - el-table → 自定义table样式
   - el-descriptions → 更精致的详情展示
   - el-steps → 自定义步骤指示器
   - el-progress → 自定义进度条

3. **MatchDiagnosis 步骤向导** — 需要更精致的步骤卡片设计
   - 当前使用el-steps，缺乏视觉冲击力
   - 步骤间过渡缺少连贯性

4. **PositionSearch 组件** — 纯el-select，无自定义
   - 需要自定义下拉样式
   - 添加搜索结果预览卡片

#### 中优先级
5. **ResumeUpload 拖拽区域** — 可以更有设计感
   - 添加文件类型图标
   - 上传动画可以更流畅

6. **EvolutionDashboard 新兴技能网格** — 卡片设计可更精致
   - 添加趋势微图表 (sparkline)
   - 更精致的CII指标展示

7. **QualityDashboard KPI卡片** — 与Home页KPI风格需统一
   - 图标+数值+趋势的标准模式

8. **Admin 审核队列** — 表格过于朴素
   - 需要更精致的行样式
   - 操作按钮需要hover效果

#### 低优先级
9. **ExtractJD 页面** — 左右分栏可以更精致
   - 文本区域可以添加行号
   - 结果区域可以添加折叠动画

10. **深色模式一致性** — 需要检查所有ECharts图表
    - 确保chartColors()在dark mode下正确切换

## 设计参考体系

### shadcn-ui v4 设计语言
- SectionCards: Header/Title/Description/Footer 模式
- Sidebar: 固定+可折叠+active states
- 语义化色彩token (primary, secondary, muted, accent...)
- 精致的border-radius层级 (radius-xs → radius-2xl)
- 细腻的阴影层级 (shadow-xs → shadow-xl)

### Magic UI 设计模式
- Bento Grid 布局
- Grain 纹理质感
- Stagger 动画
- 渐变光晕效果

### FlyonUI 统计卡片模式
- label → value → description 层级
- 趋势箭头 + 百分比
- 图标背景色块

### Obsidian 产品设计哲学
- 暖色调 (Stone palette)
- 细滚动条 (5px)
- 微妙深度感
- 键盘优先操作感
- 精致的排版 (tight letter-spacing)

## 重设计策略

### 阶段1: 组件拆分 (Home.vue)
将1600行拆分为独立组件，提升可维护性

### 阶段2: Pencil Mockup
为关键页面创建高保真mockup，与设计团队评审

### 阶段3: 组件系统化
统一卡片、表格、输入框等基础组件的视觉风格

### 阶段4: 微交互打磨
添加细节动画、hover效果、状态转换

### 阶段5: 深色模式完善
确保所有图表和组件在dark mode下表现一致