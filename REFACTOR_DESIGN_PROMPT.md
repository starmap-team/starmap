# StarMap 全景图谱 2D/3D 模块 — 完整重构设计提示词

> **版本**: v3.0 (经 16 轮 grill 验证) | **日期**: 2026-07-02
> **范围**: `starmap/frontend/src/pages/Home.vue` 及其依赖的全部图谱组件、store、composable、后端 API
> **目标**: 将 1315 行的巨型页面拆分为职责单一的组件架构，消除重复状态，统一数据流，确保全功能可用

---

## 一、当前架构问题诊断

### 1.1 Home.vue 上帝页面（1316 行）

Home.vue 同时承担了 7 种职责：
- G6 2D 图谱初始化 & 渲染（3 层 x 3 布局 = 9 种渲染配置）
- 3D 图谱数据转换 & 事件桥接
- 面包屑导航逻辑
- 搜索结果路由（handleSearchSelect — 37 行 if-else 嵌套）
- 雷达图 ECharts 配置
- 演化边显示逻辑
- KPI 指标条 + 视图模式切换 UI

### 1.2 状态碎片化

| 状态 | 位置 | 问题 |
|------|------|------|
| `maxNodesLimit` | Home.vue ref + GraphToolbar ref | 双源，通过事件同步 |
| `proficiencyFilter` | Home.vue ref + GraphToolbar ref | 双源，通过事件同步 |
| `layoutMode` | Home.vue ref | 仅 2D 使用 |
| `viewMode` | Home.vue ref | 2D/3D 切换 |
| `showEvolution` | Home.vue ref | 演化开关 |
| `selectedNode` | Home.vue ref | 详情面板选中节点 |
| `autoRotate3D` | Home.vue ref | 3D 相机旋转 |

Home.vue 有 **9 个 ref** + 2 个 `let` 变量（G6Graph、graph），GraphToolbar 内部又维护 **2 个镜像 ref**（maxNodes、selectedProficiencies）。

### 1.3 渲染函数膨胀

`renderDomainLayer()` (82 行) + `renderPositionLayer()` (117 行) + `renderDetailLayer()` (111 行) = 310 行纯 G6 配置代码，散布着 `cv("--xxx")` CSS 变量调用和硬编码的样式值。

### 1.4 颜色系统分裂

| 文件 | 职责 | 行数 |
|------|------|------|
| `utils/graphColors.ts` | 3D 专用：`nodeColor`/`edgeColor`/`glowColor`/`SCENE_PALETTE`/`NODE_TYPE_COLORS`/`DOMAIN_COLORS` | 119 |
| `composables/useGraphColors.ts` | 2D 专用：`POSITION_COLOR`/`SKILL_COLOR`/`KA_COLOR_MAP` + G6 加载器 + CSS 变量解析 | 72 |
| `NodeTooltip3D.vue` 内联 | 第 3 套硬编码 7 条 `type→{label,color}` 映射 | ~10 |

**完全重复**：7 条节点类型→颜色映射存在于 3 个位置。`POSITION_COLOR`（`#3B82F6`）与 `NODE_TYPE_COLORS.Position`（`#3b82f6`）仅大小写不同。

### 1.5 后端 API — 6/9 端点是死代码

前端实际只调用 **3 个** graph 端点：

| 端点 | 前端调用 | 调用位置 |
|------|----------|----------|
| `GET /graph/overview` | ✅ | `stores/graph.ts` fetchOverview() |
| `GET /graph/position/{id}/skills` | ✅ | `stores/match.ts`, `MatchDiagnosis.vue`, `PositionDetail.vue` |
| `GET /graph/ka/{id}/positions` | ✅ | `stores/graph.ts` fetchKAPositions() |
| `GET /graph/query` | ❌ | 无人调用 |
| `GET /graph/panorama` | ❌ | 有 mock handler，无调用者 |
| `GET /graph/position/{name}` | ❌ | 不在 schema.ts 中 |
| `GET /graph/domain/{name}` | ❌ | 不在 schema.ts 中 |
| `GET /graph/domains` | ❌ | 不在 schema.ts 中 |
| `GET /graph/domain-switch/{name}` | ❌ | 不在 schema.ts 中 |

**6 个死端点**携带约 300 行重复代码：重复的 Pydantic models、重复的 `MATCH (p:Position) RETURN p` 全表扫描（4 处）、`DOMAIN_MAP` 与 `_classify_tech_stack` 双重分类系统、`get_domain_subgraph` 的 N+1 关键词循环（每请求最多 9 条 Cypher）。

---

## 二、重构目标架构（经 16 轮验证）

### 2.1 组件树

```
Home.vue (~350 行 — 状态管理 + 事件桥接 + 内联模板)
├── <Graph2D v-if="viewMode === '2d'" />    (~450 行，新建 — G6 封装)
├── <Graph3D v-if="viewMode === '3d'" />    (~630 行，已有 — 小改)
├── <GraphToolbar />                         (~270 行，已有 — 改受控)
├── <DetailPanel />                          (~380 行，已有 — 不变)
├── <GraphSearchBar />                       (~190 行，已有 — 不变)
├── KPI Strip (内联模板，~65 行)
└── Graph Controls (内联模板，~78 行)
```

### 2.2 不创建任何新 composable

原始设计计划 6 个 composable，经验证全部砍掉：

| 原始计划 | 决定 | 理由 |
|----------|------|------|
| `useGraphRenderer` | ❌ 砍掉 | G6 逻辑归 Graph2D.vue（与 Graph3D.vue 对等） |
| `useViewMode` | ❌ 砍掉 | 2 个 ref + 3 个单行函数，只 1 个调用者 |
| `usePositionRadar` | ❌ 砍掉 | ~40 行 computed，只 1 个调用者 |
| `useSearchNavigation` | ❌ 砍掉 | ~50 行函数，只 1 个调用者 |
| `useGraphColors` | ❌ 砍掉 | 颜色统一到纯模块；`loadG6Graph`+`cv` 移入 Graph2D |
| `KPIStrip.vue` | ❌ 砍掉 | 纯模板无脚本逻辑，内联更简单 |
| `GraphControls.vue` | ❌ 砍掉 | 纯模板无脚本逻辑，内联更简单 |
| `GraphCanvas.vue` | ❌ 砍掉 | 不需要额外容器层 |

### 2.3 状态归属

**原则：store 管数据，页面管 UI 状态，组件只渲染。**

| 状态 | 归属 | 理由 |
|------|------|------|
| `currentLayer`, `expandedKAId`, `expandedPositionId` | store | 三层导航核心业务状态 |
| `overviewMode` | store | 控制后端查询参数 |
| `allNodes`, `allEdges`, `visibleNodes`, `visibleEdges` | store | 图数据 |
| `evolutionEdges` | store | 边数据 |
| `layoutMode` | Home.vue ref | 2D-only UI 配置 |
| `viewMode` | Home.vue ref | 2D/3D 切换 |
| `showEvolution` | Home.vue ref | UI toggle，只影响渲染不改变数据 |
| `selectedNode` | Home.vue ref | 页面级 UI 状态，非跨页面共享 |
| `autoRotate3D` | Home.vue ref | 3D 相机 UI 状态 |
| `maxNodesLimit` | Home.vue ref → Graph2D prop | 2D-only 渲染裁剪 |
| `proficiencyFilter` | Home.vue ref → Graph2D prop | 2D-only 渲染过滤 |

**关键决策：不向 store 迁移任何 UI 状态。** 原始计划的 4 个迁移全部否决：
- `selectedNode` 是页面级 UI 状态，不是跨页面业务数据
- `maxNodesLimit`/`proficiencyFilter` 是 2D-only 渲染配置，3D 不需要
- `showEvolution` 是 UI toggle，不影响 store 的 visibleEdges

---

## 三、详细重构提示词

### 3.1 Phase 1: 后端死代码清理（独立，可与前端并行）

```
重构目标: starmap/backend/app/api/v1/graph.py + graph_service.py

当前: 9 个端点，6 个无人调用

删除 6 个死端点（graph.py）:
  1. GET /graph/query              → graph_query()
  2. GET /graph/panorama           → get_graph_panorama()
  3. GET /graph/position/{position_name}  → get_position_graph()
  4. GET /graph/domain/{domain_name}      → get_domain_detail()
  5. GET /graph/domains            → get_domains()
  6. GET /graph/domain-switch/{domain_name}  → get_domain_subgraph()

删除对应 Pydantic models（graph.py）:
  - GraphQueryResponse      (≡ GraphPanoramaResponse，完全重复)
  - GraphPanoramaResponse
  - PositionSkillGraphResponse  (与 PositionSkillDetailResponse 语义重复)
  - DomainDetailResponse
  - DomainListResponse
  - DomainSubgraphResponse
  - DomainItem              (≈ DomainOverviewItem)

删除对应 service 函数（graph_service.py）:
  - fetch_panorama()        (仅 /panorama 调用)
  - run_readonly_query()    (仅 /query 调用)
  - _resolve_position_name() (仅 /position/{name} 调用)

删除常量（graph.py）:
  - DOMAIN_MAP              (仅 /domains 和 /domain-switch 使用)

删除前端 mock（handlers.ts）:
  - http.get('/api/v1/graph/panorama', ...) handler

保留 3 个活端点:
  - GET /graph/overview
  - GET /graph/position/{position_id}/skills
  - GET /graph/ka/{ka_id}/positions

验收:
- ruff check app/ 通过
- pytest 通过
- npm run gen:api 后 schema.ts 无断裂
```

### 3.2 Phase 2: 颜色系统统一

```
重构目标: utils/graphColors.ts + composables/useGraphColors.ts + NodeTooltip3D.vue

当前: 3 套颜色源（graphColors.ts / useGraphColors.ts / NodeTooltip3D 内联）
目标: 1 个纯模块 utils/graphColors.ts

─ utils/graphColors.ts（重写，~130 行）─

保留并吸收:
  # 从原 graphColors.ts 保留:
  - DOMAIN_COLORS          (14 色 string[])
  - NODE_TYPE_COLORS       (7 条 Record<string, string>)
  - EDGE_TYPE_COLORS       (6 条 Record<string, string>)
  - SCENE_PALETTE          (scene 配色对象)
  - nodeColor()            — 但删除 categoryOrId 参数，KA 着色由外部预计算
  - edgeColor()
  - glowColor()
  - withAlpha()
  - toThreeHex()

  # 从 useGraphColors.ts 吸收（改为纯常量）:
  - KA_FALLBACK_COLORS     (14 色 string[]，不再依赖 chartColors())
  # 删除: POSITION_COLOR / SKILL_COLOR / SKILL_BONUS_COLOR
  #   — 消费者统一用 NODE_TYPE_COLORS.Position / .Skill / .Tool

  # 从 NodeTooltip3D.vue 提取:
  - TYPE_LABELS            (Record<string, string>: KnowledgeArea→领域, Position→岗位, ...)
  - TYPE_INFO              (Record<string, { label: string; color: string }>)

导出:
  export { DOMAIN_COLORS, NODE_TYPE_COLORS, EDGE_TYPE_COLORS, SCENE_PALETTE,
           KA_FALLBACK_COLORS, TYPE_LABELS, TYPE_INFO,
           nodeColor, edgeColor, glowColor, withAlpha, toThreeHex }

─ 删除 composables/useGraphColors.ts ─
  逻辑分散到:
  - 纯颜色常量/函数 → utils/graphColors.ts
  - loadG6Graph() + cv() + clearCvCache() → Graph2D.vue 内部
  - KA_COLOR_MAP computed → Home.vue 内部构建（从 store.domains + KA_FALLBACK_COLORS）

─ NodeTooltip3D.vue 修改 ─
  删除: 内联 typeInfo computed 中的硬编码颜色映射
  替换: import { TYPE_INFO } from '@/utils/graphColors'
  computed: const typeInfo = computed(() => TYPE_INFO[props.node.type] ?? { label: props.node.type, color: '#64748b' })

─ Graph3D.vue 修改 ─
  删除: import { nodeColor, edgeColor, glowColor, ... } from '@/utils/graphColors'
  理由: Home.vue 在构建 graph3DNodes 时预计算颜色写入 node.color
  Graph3D 读 node.color 着色，不再需要颜色函数

验收:
- vue-tsc --noEmit 零新增错误
- eslint 零错误
- 2D/3D KA 节点颜色一致
```

### 3.3 Phase 3: GraphToolbar 改为受控组件

```
重构目标: starmap/frontend/src/components/GraphToolbar.vue

当前: 内部维护 maxNodes ref + selectedProficiencies ref（与 Home.vue 双源）
目标: 纯受控组件，无内部状态 ref

变更:

1. 删除内部 ref:
   - 删除: const maxNodes = ref(80)
   - 删除: const selectedProficiencies = ref<string[]>([...])
   - 保留: const showFilters = ref(false)  ← 这是纯 UI 折叠状态，合理

2. 新增 props:
   props: {
     nodeCount: number          (已有)
     layoutMode: string         (已有)
     is3D?: boolean             (已有)
     autoRotate?: boolean       (已有)
     maxNodes: number           (新增)
     selectedProficiencies: string[]  (新增)
   }

3. 模板改为读 props:
   - el-slider :model-value="props.maxNodes" @change="(v) => emit('maxNodesChange', v)"
   - prof-chip :class="{ 'prof-chip--active': props.selectedProficiencies.includes(level) }"
   - @click="emit('proficiencyFilter', toggleLevel(props.selectedProficiencies, level))"

4. 删除 onMaxNodesChange / toggleProficiency 函数
   - 改为纯 emit，计算逻辑移到 Home.vue 或用工具函数

验收:
- GraphToolbar 内部无 maxNodes / selectedProficiencies ref
- 数据流单向: Home.vue → props → GraphToolbar → emit → Home.vue
```

### 3.4 Phase 4: 新建 Graph2D.vue

```
重构目标: 新建 starmap/frontend/src/components/Graph2D.vue
源代码: Home.vue 第 22-28, 33, 254-716 行的 G6 相关逻辑

这是本次重构最大的新文件。从 Home.vue 平移约 410 行 G6 逻辑。

─ Props（10 个）─
interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  currentLayer: ViewLayer
  overviewMode: OverviewMode
  layoutMode: 'force' | 'dagre' | 'radial'
  kaColorMap: Map<string, string>
  showEvolution: boolean
  evolutionEdges: GraphEdge[]
  maxNodesLimit: number
  proficiencyFilter: string[]
}

─ Events（3 个）─
defineEmits<{
  nodeClick: [nodeId: string]
  nodeDblClick: [nodeId: string]
  canvasClick: []
}>()

─ Exposed（4 个方法）─
defineExpose<{
  zoomBy: (factor: number) => void
  fitView: () => void
  highlightNode: (nodeId: string) => void
  clearHighlight: () => void
}>

─ 内部结构 ─

1. G6 加载器（从 useGraphColors.ts 移入）:
   - loadG6Graph()      — 动态 import @antv/g6，singleton 缓存
   - cv(name)           — CSS 变量解析，带缓存
   - clearCvCache()     — 清除缓存

2. 生命周期:
   onMounted: 调用 loadG6Graph() → 创建 Graph 实例 → 注册事件 → emit('ready' 不需要)
   onUnmounted: graph.destroy()

3. 三层渲染函数（从 Home.vue 平移，三个独立函数）:
   - renderDomainLayer()   (~82 行) — KA 岛屿节点 + 域间连接边
   - renderPositionLayer() (~117 行) — Position 节点 + KA 包含边 + REQUIRES 边 + 演化边
   - renderDetailLayer()   (~111 行) — Skill 节点 + Position 节点 + REQUIRES 边

   颜色来源:
   - KA 节点: props.kaColorMap.get(kaId) ?? KA_FALLBACK_COLORS[index]
   - Position 节点: NODE_TYPE_COLORS.Position
   - Skill 节点: NODE_TYPE_COLORS.Skill
   - 其他 cv("--xxx") CSS 变量调用保留

   裁剪:
   - renderPositionLayer/renderDetailLayer 中 nodes.slice(0, props.maxNodesLimit)
   - renderDetailLayer 中按 props.proficiencyFilter 过滤 Skill 节点

   演化边:
   - renderPositionLayer 中 if (props.showEvolution) 加入 props.evolutionEdges

4. 布局配置常量:
   const LAYOUT_CONFIGS = {
     force: { type: 'force', preventOverlap: true, ... },
     dagre: { type: 'dagre', rankdir: 'TB', ... },
     radial: { type: 'radial', unitRadius: 160, ... },
   }

5. watch 自动重渲染（方案 B — props 驱动）:
   watch(() => props.currentLayer, renderCurrentLayer)
   watch(() => props.overviewMode, renderCurrentLayer)
   watch(() => props.nodes, renderCurrentLayer)
   watch(() => props.edges, renderCurrentLayer)
   watch(() => props.layoutMode, () => { graph.setLayout(LAYOUT_CONFIGS[props.layoutMode]); graph.render() })
   watch(() => props.showEvolution, renderCurrentLayer)
   watch(() => props.maxNodesLimit, renderCurrentLayer)
   watch(() => props.proficiencyFilter, renderCurrentLayer)

   renderCurrentLayer():
     if (currentLayer === 'domain') renderDomainLayer()
     else if (currentLayer === 'position') renderPositionLayer()
     else renderDetailLayer()

6. 事件处理:
   graph.on('node:click', (e) => emit('nodeClick', e.target.id))
   graph.on('node:dblclick', (e) => emit('nodeDblClick', e.target.id))
   graph.on('canvas:click', () => emit('canvasClick'))

7. Exposed 方法:
   zoomBy(factor) { graph.zoomBy(factor) }
   fitView() { graph.fitView() }
   highlightNode(nodeId) { /* 当前 Home.vue highlightNode 逻辑平移 */ }
   clearHighlight() { renderCurrentLayer() }

验收:
- Graph2D.vue 不 import useGraphStore
- 三层渲染、三种布局、节点高亮、双击钻取、演化边全部可用
- vue-tsc + eslint 通过
```

### 3.5 Phase 5: Graph3D.vue 颜色预计算适配

```
重构目标: starmap/frontend/src/components/Graph3D.vue

当前: import { nodeColor, edgeColor, glowColor, ... } from '@/utils/graphColors'
目标: 读 node.color 着色，不 import 颜色函数

变更:

1. 删除 import:
   - import { nodeColor, edgeColor, glowColor, withAlpha, SCENE_PALETTE, toThreeHex }
   - 保留: import { SCENE_PALETTE, toThreeHex, withAlpha }  ← 这些仍需要（场景配置/格式转换）

2. 节点着色改为读 node 对象的 color 字段:
   getNodeColor(node) {
     return node.color ?? '#64748b'   // 预计算颜色，fallback 灰色
   }

3. glowColor 函数保留（它是纯函数，不依赖 nodeColor）

验收:
- 3D KA 节点颜色与 2D 一致（因为 Home.vue 用同一份 kaColorMap 预计算）
- 3D 渲染正常，无色差回归
```

### 3.6 Phase 6: Home.vue 精简

```
重构目标: starmap/frontend/src/pages/Home.vue
当前: 1316 行 → 目标: ~350 行（script ~150 + template ~100 + style ~100）

─ 删除（移入 Graph2D.vue）─
  - G6Graph let 变量 + ensureG6Loaded()
  - graph let 变量
  - initGraph()         (65 行)
  - renderCurrentLayer() (10 行)
  - renderDomainLayer()  (82 行)
  - renderPositionLayer() (117 行)
  - renderDetailLayer()  (111 行)
  - highlightNode()      (23 行)
  - clearHighlight()     (3 行)
  - resetHighlight()     (3 行)
  - handleResize()       (4 行)
  - loadG6Graph / cv import

─ 保留（页面级逻辑）─
  - viewMode, autoRotate3D, layoutMode, showEvolution ref
  - selectedNode ref
  - maxNodesLimit, proficiencyFilter ref
  - breadcrumb computed (~10 行)
  - positionRadarOption computed (~33 行)
  - graph3DNodes, graph3DLinks computed（预计算颜色写入 node.color）
  - handleSearchSelect 函数 (~37 行)
  - findKAForPosition 函数 (~7 行)
  - on3DNodeClick, on3DDblClick 函数
  - onCameraPreset, onResetCamera, onToggleAutoRotate 函数
  - toggleLayout, toggleEvolution, onMaxNodesChange, onProficiencyFilter 函数
  - closeDetail 函数
  - onOverviewModeChange 函数

─ 新增 ─
  - kaColorMap computed（从 store.domains + KA_FALLBACK_COLORS 构建）
  - graph2DRef ref（模板引用 Graph2D）

─ 模板变更 ─
  删除:
    <div v-show="viewMode === '2d'" ref="graphRef" class="graph-canvas" />
    <div v-if="viewMode === '3d' && !graph3DReady" class="graph-3d-skeleton">...</div>

  新增:
    <Graph2D
      v-if="viewMode === '2d'"
      ref="graph2DRef"
      :nodes="graphStore.visibleNodes"
      :edges="graphStore.visibleEdges"
      :current-layer="graphStore.currentLayer"
      :overview-mode="graphStore.overviewMode"
      :layout-mode="layoutMode"
      :ka-color-map="kaColorMap"
      :show-evolution="showEvolution"
      :evolution-edges="graphStore.evolutionEdges"
      :max-nodes-limit="maxNodesLimit"
      :proficiency-filter="proficiencyFilter"
      @node-click="handleNodeClick"
      @node-dbl-click="onDblClick"
      @canvas-click="onCanvasClick"
    />

  保留:
    <Graph3D
      v-if="viewMode === '3d'"
      ref="graph3DRef"
      :nodes="graph3DNodes"
      :links="graph3DLinks"
      @node-click="on3DNodeClick"
      @node-dbl-click="on3DDblClick"
    />

  GraphToolbar 改为受控:
    <GraphToolbar
      :node-count="graphStore.visibleNodes.length"
      :layout-mode="layoutMode"
      :is3-d="viewMode === '3d'"
      :auto-rotate="autoRotate3D"
      :max-nodes="maxNodesLimit"
      :selected-proficiencies="proficiencyFilter"
      @zoom-in="graph2DRef?.zoomBy(1.2)"
      @zoom-out="graph2DRef?.zoomBy(0.8)"
      @zoom-fit="graph2DRef?.fitView()"
      @toggle-layout="toggleLayout"
      @reset-highlight="graph2DRef?.clearHighlight()"
      @max-nodes-change="onMaxNodesChange"
      @proficiency-filter="onProficiencyFilter"
      @camera-preset="onCameraPreset"
      @reset-camera="onResetCamera"
      @toggle-auto-rotate="onToggleAutoRotate"
    />

─ 生命周期变更 ─
  删除: initGraph() 调用（Graph2D 自己在 onMounted 初始化）
  删除: graph.destroy() 调用（Graph2D 自己在 onUnmounted 销毁）
  删除: window.addEventListener('resize', handleResize)（Graph2D 自己监听）
  删除: graph3DReady hack + setTimeout(1500)（v-if 两边对等，不需要）
  删除: viewMode watcher 中的 graph3DReady 逻辑

  保留:
  onMounted(async () => {
    await graphStore.fetchOverview()
  })

─ graph3DNodes 预计算颜色 ─
  const graph3DNodes = computed(() => {
    return graphStore.visibleNodes.map(n => {
      let color = NODE_TYPE_COLORS[n.labels[0]] ?? '#64748b'
      if (n.labels[0] === 'KnowledgeArea') {
        color = kaColorMap.value.get(n.id) ?? KA_FALLBACK_COLORS[0]
      }
      return { ...n, color }
    })
  })

验收:
- Home.vue ≤ 350 行
- 无 G6 import
- 无 graph3DReady / setTimeout hack
- 2D/3D 全功能
```

---

## 四、重构顺序 & 依赖关系

```
Phase 1 (后端死代码) ─────── 独立，可与前端并行
Phase 2 (颜色统一) ─────────┐
Phase 3 (GraphToolbar 受控)─┤
Phase 4 (Graph2D.vue) ──────┼──→ Phase 6 (Home.vue 精简)
Phase 5 (Graph3D 颜色适配)──┘
```

执行顺序: 2 → 3 → 4 → 5 → 6
后端: 1 可在任意时刻插入
每个 Phase 完成后:
```bash
cd starmap/frontend && npx vue-tsc --noEmit && npx eslint src/ --max-warnings=0
cd starmap/backend  && python -m ruff check app/ && python -m pytest tests/ -x
```

git commit 粒度 = 1 Phase

---

## 五、验收清单

| # | 检查项 | 标准 |
|---|--------|------|
| 1 | Home.vue 行数 | ≤ 350 行（含 template + style） |
| 2 | 无重复状态 | 同一数据只有 1 份 ref（store 管数据 / Home 管UI / Graph2D 管渲染） |
| 3 | GraphToolbar 受控 | 内部无 maxNodes/selectedProficiencies ref |
| 4 | 无新 composable | 不存在 useGraphRenderer/useViewMode/usePositionRadar/useSearchNavigation/useGraphColors |
| 5 | 颜色统一 | 仅 utils/graphColors.ts 一个颜色源；NodeTooltip3D import TYPE_INFO |
| 6 | 2D/3D v-if 对等 | 两边都用 v-if，无 graph3DReady hack |
| 7 | 2D 图谱全功能 | 三层导航、三种布局、节点高亮、双击钻取、演化边、节点裁剪、熟练度过滤 |
| 8 | 3D 图谱全功能 | 节点渲染、hover tooltip、单击选中、双击钻取、相机预设、自动旋转 |
| 9 | 2D/3D KA 颜色一致 | 同一 KA 在 2D 和 3D 中颜色相同 |
| 10 | 搜索可用 | 搜索岗位/技能/领域 → 自动导航到对应层级 |
| 11 | 详情面板 | 选中节点显示属性、雷达图、相似岗位 |
| 12 | 后端端点 | 9 → 3，删除 6 个死端点 + 对应 models + service 函数 |
| 13 | 类型检查 | vue-tsc --noEmit 零新增错误 |
| 14 | Lint | eslint + ruff check 零错误 |

---

## 六、风险 & 回退策略

| 风险 | 影响 | 缓解 |
|------|------|------|
| G6 v5 API 在 Graph2D.vue 中行为不同 | 2D 图谱不渲染 | Phase 4 前后对比截图；G6 逻辑是平移不是重写 |
| Graph2D watch props 性能 | 频繁重渲染 | watch 加 { deep: false }；nodes/edges 引用变化才触发 |
| 3D 颜色预计算后 NodeTooltip3D 色差 | tooltip 颜色不匹配 | NodeTooltip3D 统一用 TYPE_INFO，与 NODE_TYPE_COLORS 同源 |
| 后端删端点后 schema.ts 过期 | 类型错误 | Phase 1 后立即 npm run gen:api |
| v-if 销毁 3D 后切回需重建 | 1.5s 初始化延迟 | 可接受 — 用户不频繁切换；Graph3D emit ready 替代 hack |

每个 Phase 独立可回退：git revert 即可。

---

## 七、grill 决策记录（16 轮）

| # | 问题 | 决定 |
|---|------|------|
| 1 | useGraphRenderer vs Graph2D.vue | 砍 useGraphRenderer，逻辑归 Graph2D.vue |
| 2 | v-show vs v-if 生命周期 | 两边都用 v-if，消灭 graph3DReady hack |
| 3 | selectedNode 归属 | 留页面级，不进 store |
| 4 | maxNodesLimit/proficiencyFilter 归属 | 留 Graph2D props，不进 store |
| 5 | showEvolution 归属 | 留页面级，不进 store |
| 6 | useViewMode composable | 砍掉，逻辑留 Home.vue |
| 7 | usePositionRadar/useSearchNavigation | 砍掉，逻辑留 Home.vue |
| 8 | KPIStrip/GraphControls 拆分 | 砍掉，内联模板 |
| 9 | GraphToolbar 状态镜像 | 改为受控组件，删除内部 ref |
| 10 | 颜色系统拆分 | 纯模块 graphColors.ts + kaColorMap 单 prop |
| 11 | 后端 API 精简程度 | 9→3，删除 6 个死端点 |
| 12 | Graph2D 通信方式 | props 驱动 watch 自动重渲染（方案 B） |
| 13 | Graph2D 三层渲染组织 | 三个独立函数平移（方案 A） |
| 14 | 颜色统一具体方案 | graphColors.ts 纯模块，useGraphColors.ts 删除 |
| 15 | 3D KA 着色 | 预计算到 node.color，Graph3D 不需要颜色函数 |
| 16 | 最终架构确认 | ✅ 确认 |
