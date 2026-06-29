# StarMap 前端 UI/UX 重构评审报告 v3

**评审日期**: 2026-06-29
**评审范围**: 7 页面 + 6 组件 + 1 布局 + 全局设计系统 + Pencil 高保真线框图
**参考体系**: shadcn-ui (布局语义) + Magic UI (微动效) + FlyonUI (数据卡片)

---

## 1. 重构总览

### 1.1 v3 新增改动

| 模块 | 文件 | 改动类型 | 关键变更 |
|------|------|---------|---------|
| 首页 | `Home.vue` | 架构拆分 | 1519→1106行，提取DetailPanel+GraphSearchBar组件 |
| 详情面板 | `DetailPanel.vue` ✨新增 | 组件提取 | 312行独立组件，响应式适配，scoped CSS |
| 搜索栏 | `GraphSearchBar.vue` ✨新增 | 组件提取 | 172行独立组件，键盘导航，glass效果 |
| 全局 | `App.vue` | Token增强 | surface layers、focus ring、glass、skeleton、hover-lift、accent-bar |
| 匹配诊断 | `MatchDiagnosis.vue` | 视觉增强 | grain纹理、accent bar、step-actions border-top |
| 线框图 | `StarMap.pen` | Pencil原型 | Home Redesign v8: 1440x900完整布局线框 |

### 1.2 设计系统增强 (App.vue)

**新增 Token 类别**:
- `--surface-0/1/2/3`: 深度层级表面色
- `--surface-raised/sunken/overlay`: 语义表面
- `--content-gap/section-gap/page-padding-*`: 语义间距
- `--card-padding/card-gap`: 卡片系统间距
- `--focus-ring`: 统一焦点环
- `--transition-fast/normal/slow`: 预设过渡

**新增工具类**:
- `.glass`: 毛玻璃效果 (backdrop-filter: blur 12px)
- `.skeleton`: 骨架屏脉冲动画
- `.hover-lift`: 悬浮上升效果
- `.accent-bar`: 渐变强调条
- `.accent-bar`: 渐变强调条
- `::selection`: 选区高亮
- `*:focus-visible`: 统一焦点环

**新增过渡动画**:
- `page-slide-left`: 水平滑入过渡变体

---

## 2. 反 AI 味检查清单

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Emoji | 0 个 | 全部使用 SVG 图标 |
| 通用空状态 | 已消除 | 自定义 SVG + 上下文化文案 |
| 硬编码色值 | 仅 Token 定义 | 组件样式中 0 个硬编码色 |
| CSS 变量引用 | 全量 Token 化 | 713+ 处引用 |
| 微噪点纹理 | .grain 类 | 图谱容器 + 匹配诊断应用 |
| 交错入场 | .stagger 类 | KPI 卡片应用 |
| 弹性动效 | ease-spring | 按钮/卡片交互 |
| 排版紧凑 | tracking-tight | 标题统一 -0.025em |
| 数字等宽 | tabular-nums | 数据值统一 |
| 渐变克制 | 仅匹配分数 | 不做满屏渐变 |
| 毛玻璃 | .glass 类 | 搜索栏/下拉菜单 |
| 焦点环 | focus-visible | 统一 ring 样式 |
| 选区高亮 | ::selection | primary 20% 透明 |
| 骨架屏 | .skeleton | 数据加载态 |

---

## 3. 组件架构

### 3.1 组件提取成果

```
Before: Home.vue (1519 lines) — 包含搜索、详情面板、雷达图
After:  Home.vue (1106 lines) — 纯图谱逻辑 + KPI
        DetailPanel.vue (312 lines) — 右侧详情面板
        GraphSearchBar.vue (172 lines) — 底部搜索栏
```

### 3.2 完整组件清单

| 组件 | 行数 | 职责 |
|------|------|------|
| `MainLayout.vue` | 550 | 侧边栏 + 面包屑 + 路由视图 |
| `DetailPanel.vue` | 312 | 节点详情面板 + 雷达图 + 属性列表 |
| `GraphSearchBar.vue` | 172 | 全局搜索 + 键盘导航 + glass效果 |
| `GraphToolbar.vue` | ~80 | 图谱控制工具栏 |
| `SkillRadar.vue` | ~60 | 技能雷达图封装 |
| `ResumeUpload.vue` | ~80 | 简历上传区 |
| `PositionSearch.vue` | ~60 | 岗位搜索选择 |

---

## 4. Pencil 高保真线框图

### 4.1 Home Redesign v8

- **文件**: `StarMap.pen`
- **节点ID**: `y9TEwM`
- **尺寸**: 1440 x 900
- **结构**: Sidebar (260px) + Main Content
- **元素**:
  - 侧边栏: 品牌区 + 4组导航 + 暗色切换
  - 头部: 面包屑导航
  - KPI条: 4张统计卡片 (岗位/技能/领域/信任度)
  - 图谱区: 模拟力导向图 (5个节点+边)
  - 详情面板: 类型徽章 + 标题 + 雷达占位 + 属性 + 相似岗位
  - 搜索栏: glass效果搜索框

### 4.2 Pencil MCP 直连方案

MCP Transport 不可用，采用 stdio 直连方案:
```
PencilClient → spawn(mcp-server-windows-x64.exe) → JSON-RPC over stdin/stdout
```

---

## 5. 构建验证

| 检查 | 结果 |
|------|------|
| ESLint | 0 errors, 0 warnings |
| vue-tsc --noEmit | 0 errors |
| Vite build | 25.19s 成功 |
| 文件数 | 16 个 .vue 文件 |
| 总行数 | ~5,400 行 |

---

## 6. 遗留项

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 中 | 线框图细化 | 需为其他6个页面制作Pencil线框图 |
| 低 | 图表legend文字色 | ECharts legend 应使用 chartColors().muted |
| 低 | 代码分割 | Home.vue chunk 1443KB，建议 dynamic import G6 |

---

## 7. 设计参考来源

- **shadcn-ui**: Sidebar composition, Card patterns, semantic tokens, focus-visible
- **Magic UI**: grain texture, stagger animations, AnimatedGradientText, glass morphism
- **FlyonUI**: Stat cards (title+value+description), progress bars, accent bars
