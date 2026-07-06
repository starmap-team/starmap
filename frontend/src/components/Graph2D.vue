<script setup lang="ts">
/**
 * Graph2D — G6 v5 force-directed graph visualization (2D counterpart to Graph3D).
 *
 * Owns all G6 lifecycle: dynamic import, instance creation, three-layer rendering,
 * layout switching, node highlighting, and resize handling.
 *
 * UI state comes from props; graph data is read from the store.
 */

// 业务说明：引入 Vue 3 核心 API，用于组件生命周期管理、响应式状态及模板引用
import { ref, onMounted, onUnmounted, watch, nextTick, shallowRef } from 'vue'
// 业务说明：引入 Element Plus 消息提示组件，用于在图谱加载失败时向用户展示错误信息
import { ElMessage } from 'element-plus'
// 业务说明：引入图谱数据 Store，提供节点、边、领域、岗位等全局状态数据
import { useGraphStore } from '@/stores/graph'
// 业务说明：引入节点颜色映射常量，用于根据节点类型（领域/岗位/技能）分配可视化颜色
import { NODE_TYPE_COLORS, KA_FALLBACK_COLORS } from '@/utils/graphColors'

// ── Props (UI state owned by parent) ──
// 业务说明：定义组件对外暴露的属性接口，父组件通过 props 控制图谱的展示模式与筛选条件
const props = withDefaults(defineProps<{
  layoutMode?: 'force' | 'dagre' | 'radial'          // 业务说明：布局模式，支持力导向/层次/径向三种
  kaColorMap?: Map<string, string>                   // 业务说明：领域(KA)到颜色的映射表，保证同一领域在不同层级颜色一致
  showEvolution?: boolean                            // 业务说明：是否展示岗位演进关系（EVOLVES_TO 边）
  maxNodesLimit?: number                             // 业务说明：单屏最大渲染节点数，用于性能控制与大图截断
  proficiencyFilter?: string[]                        // 业务说明：技能熟练度筛选条件，如 ['精通','熟悉','了解']
}>(), {
  layoutMode: 'force',
  kaColorMap: () => new Map(),
  showEvolution: false,
  maxNodesLimit: 80,
  proficiencyFilter: () => ['精通', '熟悉', '了解'],
})

// ── Events ──
// 业务说明：定义组件可向上层抛出的事件，供父组件响应用户交互（如点击节点、画布、边等）
const emit = defineEmits<{
  nodeClick: [nodeId: string]                        // 业务说明：用户单击节点时触发，携带节点唯一标识
  nodeDblClick: [nodeId: string]                     // 业务说明：用户双击节点时触发，常用于下钻或打开详情
  canvasClick: []                                     // 业务说明：用户点击空白画布时触发，用于取消选中/高亮
  edgeClick: [edgeData: { source: string; target: string; type: string; properties: any }]
                                                    // 业务说明：用户点击演进边时触发，携带边的完整业务数据
}>()

// ── Store (read-only data access) ──
// 业务说明：获取图谱全局状态管理器，本组件以只读方式访问节点、边、领域、岗位等数据
const graphStore = useGraphStore()

// ── G6 dynamic loader ──
// 技术说明：缓存 G6 Graph 类，避免重复动态导入，减少网络请求与初始化耗时
let _G6GraphClass: any = null

// 技术说明：按需异步加载 @antv/g6 库，返回 Graph 构造函数；首次调用时执行导入并缓存
async function loadG6Graph(): Promise<any> {
  if (!_G6GraphClass) {
    const g6 = await import('@antv/g6')
    _G6GraphClass = g6.Graph
  }
  return _G6GraphClass
}

// ── CSS variable cache ──
// 技术说明：缓存 CSS 自定义属性值，避免每次渲染都重复调用 getComputedStyle，提升性能
const _cvCache = new Map<string, string>()

// 技术说明：根据 CSS 变量名获取当前主题下的实际颜色值，优先读取缓存
function cv(name: string): string {
  let value = _cvCache.get(name)
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    _cvCache.set(name, value)
  }
  return value
}

// ── Template refs & G6 instance ──
// 技术说明：模板引用，指向承载 G6 画布的真实 DOM 容器节点
const containerRef = ref<HTMLElement | null>(null)
// 技术说明：使用 shallowRef 持有 G6 实例，避免 Vue 对 G6 内部庞大对象进行深度响应式代理，降低内存与性能开销
const graph = shallowRef<any>(null)

// ── Exposed methods ──
// 业务说明：对外暴露的缩放方法，父组件可通过 ref 调用以控制画布缩放级别
function zoomBy(factor: number) {
  graph.value?.zoomBy(factor)
}
// 业务说明：对外暴露的自适应视图方法，使全部节点自适应填充可视区域
function fitView() {
  graph.value?.fitView()
}
// 业务说明：高亮指定节点及其一度邻居，其余节点淡化处理，帮助用户聚焦关键信息
function highlightNode(nodeId: string) {
  if (!graph.value) return
  // 技术说明：收集目标节点及其直接关联节点的 ID 集合，用于后续批量样式更新
  const relatedIds = new Set<string>([nodeId])
  for (const e of graphStore.visibleEdges) {
    if (e.source_id === nodeId) relatedIds.add(e.target_id)
    if (e.target_id === nodeId) relatedIds.add(e.source_id)
  }
  // 技术说明：遍历所有可见节点，根据是否为目标节点或邻居动态设置透明度、线宽与阴影
  const updateNodes = graphStore.visibleNodes.map(n => {
    const isRelated = relatedIds.has(n.id)
    const isCenter = n.id === nodeId
    return {
      id: n.id,
      style: {
        fillOpacity: isCenter ? 1 : isRelated ? 0.85 : 0.12,
        lineWidth: isCenter ? 4 : isRelated ? 2 : 0.5,
        shadowColor: isCenter ? cv('--primary') : 'transparent',
        shadowBlur: isCenter ? 24 : 0,
      },
    }
  })
  graph.value.updateNodeData(updateNodes)
  graph.value.draw()
}
// 业务说明：清除高亮状态，恢复到当前图层的默认渲染样式
function clearHighlight() {
  renderCurrentLayer()
}

// 技术说明：将 zoomBy、fitView、highlightNode、clearHighlight 暴露给父组件，支持命令式调用
defineExpose({ zoomBy, fitView, highlightNode, clearHighlight })

// ── G6 initialization ──
// 业务说明：初始化 G6 图实例，配置画布尺寸、布局、节点/边默认样式、交互行为及插件
async function initGraph() {
  if (!containerRef.value) return
  // 技术说明：若已存在旧实例，先销毁释放内存，避免内存泄漏与事件重复绑定
  if (graph.value) { graph.value.destroy(); graph.value = null }
  const container = containerRef.value
  // 技术说明：读取容器实际宽高作为画布尺寸，若未渲染则使用兜底值 800×600
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  try {
    const GraphClass = await loadG6Graph()
    // 业务说明：创建 G6 图实例，配置力导向布局、节点/边样式、画布拖拽缩放、悬停高亮、缩略图及悬浮提示
    graph.value = new GraphClass({
      container,
      width,
      height,
      // 业务说明：默认使用力导向布局，开启防重叠，节点大小 40，间距 20，关闭初始动画以减少闪烁
      layout: { type: 'force', preventOverlap: true, nodeSize: 40, nodeSpacing: 20, animate: false },
      // 业务说明：节点默认样式配置，包括标签颜色、字号、位置、字体及垂直偏移
      node: {
        style: {
          labelFill: cv('--foreground'),
          labelFontSize: 12,
          labelPlacement: 'bottom' as const,
          labelOffsetY: 8,
          labelFontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
      },
      // 业务说明：边默认样式配置，包括描边颜色、线宽、透明度及末端箭头
      edge: {
        style: {
          stroke: cv('--border'),
          lineWidth: 1.5,
          opacity: 0.5,
          endArrow: true,
        },
      },
      // 业务说明：配置交互行为：画布拖拽、滚轮缩放、节点拖拽、悬停高亮一度邻居（双向）
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', { type: 'hover-activate', degree: 1, direction: 'both' }],
      // 业务说明：配置插件：缩略图(minimap)与悬浮提示框(tooltip)，提示框样式跟随当前主题
      plugins: ['minimap', { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { background: cv('--card'), borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '10px 14px', fontSize: '12px', border: '1px solid ' + cv('--border'), color: cv('--foreground') } }],
    })

    // 业务说明：监听节点单击事件，向上层抛出 nodeClick 事件，供父组件处理节点选中/下钻
    graph.value.on('node:click', (event: any) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeClick', nodeId)
    })

    // 业务说明：监听节点双击事件，向上层抛出 nodeDblClick 事件，常用于打开节点详情面板
    graph.value.on('node:dblclick', (event: any) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeDblClick', nodeId)
    })

    // 业务说明：监听画布单击事件，向上层抛出 canvasClick 事件，用于取消当前选中状态
    graph.value.on('canvas:click', () => {
      emit('canvasClick')
    })

    // 业务说明：监听边单击事件，仅处理演进边（ID 以 evo- 开头），解析源目标并抛出 edgeClick 事件
    graph.value.on('edge:click', (event: any) => {
      const edgeId = event.target?.id
      if (edgeId && edgeId.startsWith('evo-')) {
        // 技术说明：从边 ID 中解析 source 与 target：格式为 evo-{src}-{tgt}
        const parts = edgeId.replace('evo-', '').split('-')
        // 业务说明：在 Store 中查找匹配的演进边，提取完整业务数据后向上层抛出
        const evEdge = graphStore.evolutionEdges.find(e => edgeId === `evo-${e.source_id}-${e.target_id}`)
        if (evEdge) {
          emit('edgeClick', { source: evEdge.source_id, target: evEdge.target_id, type: evEdge.type, properties: evEdge.properties })
        }
      }
    })

    renderCurrentLayer()
  } catch (err) {
    console.error('[Graph2D] Failed to initialize graph:', err)
    ElMessage.error('图谱加载失败，请确认后端服务已启动')
  }
}

// ── Render dispatch ──
// 业务说明：根据当前 Store 中的图层层级（domain/position/detail），分发到对应的渲染函数
let _renderTimer: any = null
function renderCurrentLayer() {
  if (!graph.value) return
  if (_renderTimer) clearTimeout(_renderTimer)
  _renderTimer = setTimeout(() => {
    _renderTimer = null
    if (graphStore.currentLayer === 'domain') {
      renderDomainLayer()
    } else if (graphStore.currentLayer === 'position') {
      renderPositionLayer()
    } else {
      renderDetailLayer()
    }
  }, 50)
}

// ── Layer 1: Domain (KA islands) ──
// 业务说明：渲染第一层「领域概览」图层，展示所有知识领域(KA)节点及其关联，节点大小反映技能数量
function renderDomainLayer() {
  if (!graph.value) return
  // 业务说明：计算所有领域中最大的技能数量，用于后续节点大小的归一化映射
  const maxSkill = Math.max(...graphStore.domains.map(d => d.skill_count), 1)
  // 技术说明：节点尺寸映射范围：最小 50px，最大 100px，基于技能数量线性插值
  const minSize = 50, maxSize = 100

  // 业务说明：过滤掉无岗位且无技能的空领域节点，避免渲染无业务意义的孤立节点
  const visibleFiltered = graphStore.visibleNodes.filter(n => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    return domain && (domain.position_count > 0 || domain.skill_count > 0)
  })

  // 业务说明：将领域数据映射为 G6 节点对象，设置大小、颜色、标签、阴影等视觉属性
  const graphNodes = visibleFiltered.map((n, i) => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    const skillCount = domain?.skill_count ?? 0
    const posCount = domain?.position_count ?? 0
    // 业务说明：重要性评分 = 技能数 + 岗位数×2，岗位权重更高
    const importance = skillCount + posCount * 2
    // 业务说明：节点大小基于技能数量在 [minSize, maxSize] 范围内线性映射
    const size = minSize + (skillCount / maxSkill) * (maxSize - minSize)
    // 业务说明：颜色优先使用父组件传入的 kaColorMap，未命中则使用兜底调色板循环分配
    const color = props.kaColorMap.get(n.id) ?? KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length]
    return {
      id: n.id,
      style: {
        size,
        fill: color,
        fillOpacity: 0.9,
        stroke: color,
        // 业务说明：重要性高的领域使用更粗的描边，增强视觉层级
        lineWidth: importance > 100 ? 3 : 2,
        // 业务说明：标签展示领域名称及岗位/技能数量，换行显示
        labelText: n.properties.name + '\n' + posCount + '岗 ' + skillCount + '技',
        labelFill: cv('--primary-foreground'),
        // 业务说明：重要性高的领域使用更大字号，突出核心领域
        labelFontSize: importance > 100 ? 15 : 13,
        labelFontWeight: 'bold' as const,
        labelPlacement: 'center' as const,
        shadowColor: 'rgba(0,0,0,0.2)',
        // 业务说明：重要性高的领域投射更大阴影，营造视觉深度
        shadowBlur: importance > 100 ? 20 : 12,
        cursor: 'pointer' as const,
      },
    }
  })

  // 业务说明：将领域间关联边映射为 G6 边对象，使用虚线、低透明度表现弱关联
  const graphEdges = graphStore.visibleEdges.map(e => ({
    id: `${e.source_id}-${e.target_id}-${e.type}`,
    source: e.source_id,
    target: e.target_id,
    style: {
      stroke: cv('--muted-foreground'),
      lineWidth: 1.5,
      opacity: 0.3,
      lineDash: [6, 4],
      endArrow: false,
    },
  }))

  // 技术说明：向 G6 注入节点与边数据
  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  // 技术说明：设置初始入场动画状态：节点透明度 0、缩放 0.3，为后续动画做准备（当前已注释掉动画完成逻辑）
  const entranceNodes = graphNodes.map((n: any) => ({
    id: n.id,
    style: { fillOpacity: 0, scale: 0.3 },
  }))
  graph.value.updateNodeData(entranceNodes)

  // 业务说明：根据概览模式与布局模式选择不同的布局算法
  const isLevel = graphStore.overviewMode === 'level'
  const isTechStack = graphStore.overviewMode === 'tech_stack'
  if (props.layoutMode === 'dagre' || isLevel) {
    // 业务说明：层级概览或手动选择 dagre 时，使用层次布局，自上而下排列，节点/层间距根据模式调整
    graph.value.setLayout({ type: 'dagre', rankdir: 'TB', nodesep: isLevel ? 140 : 80, ranksep: isLevel ? 160 : 100, preventOverlap: true, nodeSize: 80, controlPoints: true })
  } else if (isTechStack) {
    // 业务说明：技术栈模式使用力导向布局并开启聚类，使相关领域自然聚集成群落
    graph.value.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: false, clustering: true, clusterNodeStrength: 0.5, strength: 0.4, coulombDisScale: 0.005, gravity: 8, maxSpeed: 200, maxIteration: 100 })
  } else {
    // 业务说明：默认力导向布局，通过 coulombDisScale、gravity、strength 等参数调节斥力与引力平衡
    graph.value.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: false, strength: 0.4, coulombDisScale: 0.005, gravity: 10, maxSpeed: 200, maxIteration: 100 })
  }
  graph.value.render()
  // 技术说明：以下 setTimeout 动画逻辑已移除，避免视觉抖动；保留注释供后续参考
  // Removed setTimeout to prevent visual jitter
  // graph.value?.fitView()
  // if (graph.value) {
  //   const finalNodes = graphNodes.map((n: any) => ({
  //     id: n.id,
  //     style: { fillOpacity: 0.85, scale: 1 },
  //   }))
  //   graph.value.updateNodeData(finalNodes)
  //   graph.value.draw()
  // }
  // }, 100)
}

// ── Layer 2: Position (KA + its positions) ──
// 业务说明：渲染第二层「岗位分布」图层，以当前展开的领域(KA)为中心，辐射展示其下属岗位节点
function renderPositionLayer() {
  if (!graph.value) return
  // 业务说明：获取当前展开的领域 ID 及其主题色，用于中心节点与关联边的统一配色
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (props.kaColorMap.get(kaId) ?? cv('--chart-3')) : cv('--chart-3')
  // 业务说明：从 Store 中获取该领域下的所有岗位列表
  const positions = graphStore.positionsByKA.get(kaId ?? '') ?? []
  // 业务说明：计算岗位下最大技能需求量，用于后续岗位节点大小的归一化
  const maxSkillCount = Math.max(...positions.map(p => {
    let count = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') count++ }
    return count
  }), 1)

  const graphNodes: any[] = []
  const graphEdges: any[] = []

  // 业务说明：构建中心领域节点，尺寸较小（60px），半透明填充，作为 radial 布局的焦点
  if (kaId) {
    graphNodes.push({
      id: kaId,
      style: {
        size: 60,
        fill: kaColor,
        fillOpacity: 0.7,
        stroke: kaColor,
        lineWidth: 3,
        labelText: graphStore.expandedKAName,
        labelFill: cv('--primary-foreground'),
        labelFontSize: 13,
        labelFontWeight: 'bold' as const,
        labelPlacement: 'center' as const,
        shadowColor: kaColor,
        shadowBlur: 24,
        shadowOffsetY: 3,
      },
    })
  }

  // 业务说明：应用 maxNodesLimit 限制岗位节点数量，保留核心岗位（技能需求多的优先）
  const maxPositionNodes = Math.max(props.maxNodesLimit - 1, 5)
  // 业务说明：按岗位所需技能数量降序排序，确保高价值岗位优先渲染
  const sortedPositions = [...positions].sort((a, b) => {
    let aCount = 0, bCount = 0
    for (const e of graphStore.allEdges) {
      if (e.source_id === a.id && e.type === 'REQUIRES') aCount++
      if (e.source_id === b.id && e.type === 'REQUIRES') bCount++
    }
    return bCount - aCount
  })
  const limitedPositions = sortedPositions.slice(0, maxPositionNodes)

  // 业务说明：构建岗位节点，大小基于技能需求量在 [28px, 44px] 范围内映射，使用固定岗位色
  const posColor = NODE_TYPE_COLORS.Position
  for (const p of limitedPositions) {
    let skillCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') skillCount++ }
    const size = 28 + (skillCount / maxSkillCount) * 16

    graphNodes.push({
      id: p.id,
      style: {
        size,
        fill: posColor,
        fillOpacity: 0.85,
        stroke: cv('--primary-hover'),
        lineWidth: 1.5,
        labelText: p.properties.name,
        labelFill: cv('--foreground'),
        labelFontSize: 11,
        labelFontWeight: 'normal' as const,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 6,
      },
    })

    // 业务说明：构建领域到岗位的包含关系边（CONTAINS），使用虚线、低透明度表现层级从属
    if (kaId) {
      graphEdges.push({
        id: `${kaId}-${p.id}-CONTAINS`,
        source: kaId,
        target: p.id,
        style: {
          stroke: kaColor,
          lineWidth: 1,
          opacity: 0.2,
          lineDash: [6, 4],
          endArrow: false,
        },
      })
    }
  }

  // 业务说明：当 showEvolution 为 true 时，渲染岗位间的演进关系边（EVOLVES_TO），颜色随趋势变化
  if (props.showEvolution) {
    // 业务说明：定义趋势到颜色的映射：上升-绿色、稳定-灰色、下降-红色
    const trendColors: Record<string, string> = {
      rising: cv('--success'),
      stable: cv('--muted-foreground'),
      declining: cv('--destructive'),
    }
    for (const ev of graphStore.evolutionEdges) {
      // 业务说明：在已截断的岗位列表中查找演进边的源节点与目标节点，仅渲染两端均存在的边
      const src = limitedPositions.find(p => p.id === ev.source_id || p.properties.name === ev.source_id)
      const tgt = limitedPositions.find(p => p.id === ev.target_id || p.properties.name === ev.target_id)
      if (src && tgt) {
        const trend = ev.properties.trend ?? 'stable'
        const color = trendColors[trend] ?? cv('--muted-foreground')
        graphEdges.push({
          id: `evo-${src.id}-${tgt.id}`,
          source: src.id,
          target: tgt.id,
          style: {
            stroke: color,
            // 业务说明：边粗细基于相似度权重映射，权重越高线条越粗
            lineWidth: 2 + (ev.properties.weight ?? 0.5) * 3,
            opacity: 0.85,
            lineDash: [12, 6],
            endArrow: true,
            endArrowSize: 8,
            // 业务说明：边标签展示趋势箭头与相似度百分比，如 "↑ 85%"
            labelText: `${trend === 'rising' ? '↑' : trend === 'declining' ? '↓' : '→'} ${Math.round((ev.properties.similarity ?? 0) * 100)}%`,
            labelFill: color,
            labelFontSize: 9,
            labelFontWeight: 'bold' as const,
            labelOffsetY: -6,
            labelPlacement: 'top' as const,
          },
        })
      }
    }
  }

  // 技术说明：注入节点与边数据，使用 radial 布局以领域节点为中心辐射排列岗位
  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  graph.value.setLayout({ type: 'radial', unitRadius: 160, preventOverlap: true, nodeSize: 48, focusNode: kaId || undefined, animate: false })
  graph.value.render()
  // 技术说明：延迟 300ms 后自适应视图，确保 radial 布局计算完成后再调整视口
  setTimeout(() => graph.value?.fitView(), 300)
}

// ── Layer 3: Detail (Position + its Skills) ──
// 业务说明：渲染第三层「技能详情」图层，以当前展开的岗位为中心，辐射展示其所需技能节点
function renderDetailLayer() {
  if (!graph.value) return
  const posId = graphStore.expandedPositionId
  if (!posId) return

  const graphNodes: any[] = []
  const graphEdges: any[] = []
  // 业务说明：获取当前岗位所属领域 ID 及颜色，用于构建领域背景节点与配色统一
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (props.kaColorMap.get(kaId) ?? cv('--chart-3')) : cv('--chart-3')

  // 业务说明：构建领域背景节点，尺寸较小（36px）、低透明度，作为上下文参照
  if (kaId) {
    graphNodes.push({
      id: kaId,
      style: {
        size: 36,
        fill: kaColor,
        fillOpacity: 0.35,
        stroke: kaColor,
        lineWidth: 1,
        labelText: graphStore.expandedKAName,
        labelFill: cv('--muted-foreground'),
        labelFontSize: 10,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 4,
      },
    })
  }

  // 业务说明：构建中心岗位节点，尺寸 50px，使用岗位固定色，高透明度与阴影突出中心地位
  const posNode = graphStore.nodeMap.get(posId)
  graphNodes.push({
    id: posId,
    style: {
      size: 50,
      fill: NODE_TYPE_COLORS.Position,
      fillOpacity: 0.9,
      stroke: cv('--primary-hover'),
      lineWidth: 3,
      labelText: posNode?.properties.name ?? '岗位',
      labelFill: cv('--primary-foreground'),
      labelFontSize: 13,
      labelFontWeight: 'bold' as const,
      labelPlacement: 'center' as const,
      shadowColor: 'rgba(59,130,246,0.3)',
      shadowBlur: 12,
    },
  })

  // 业务说明：获取当前岗位的所有技能关联边，并按熟练度筛选条件过滤
  const allPosEdges = graphStore.visibleEdges.filter(e => e.source_id === posId)

  // 业务说明：判断是否存在非全选的熟练度筛选，若筛选条件不足 3 项则认为有激活过滤
  const hasActiveFilter = props.proficiencyFilter.length < 3
  const filteredEdges = hasActiveFilter
    ? allPosEdges.filter(e => {
        const skillNode = graphStore.nodeMap.get(e.target_id)
        if (!skillNode) return false
        // 业务说明：优先读取技能节点属性中的 proficiency，其次读取边属性中的 level
        const prof = skillNode.properties.proficiency || (e.properties as any)?.level || ''
        return prof ? props.proficiencyFilter.includes(prof) : true
      })
    : allPosEdges

  // 业务说明：应用 maxNodesLimit 截断技能节点数量，优先保留权重高的技能（核心技能优先展示）
  const maxSkillNodes = Math.max(props.maxNodesLimit - 3, 5)
  const sortedEdges = [...filteredEdges].sort((a, b) => (b.properties?.weight ?? 0.5) - (a.properties?.weight ?? 0.5))
  const posEdges = sortedEdges.slice(0, maxSkillNodes)
  const maxWeight = Math.max(...posEdges.map(e => e.properties?.weight ?? 0.5), 0.1)

  // 业务说明：遍历筛选后的技能边，构建技能节点与岗位到技能的 REQUIRES 边
  for (const e of posEdges) {
    const skillNode = graphStore.nodeMap.get(e.target_id)
    if (!skillNode) continue
    const weight = e.properties?.weight ?? 0.5
    // 业务说明：权重 ≥ 0.6 判定为必需技能，使用技能主色；否则判定为工具/辅助技能，使用辅助色
    const isRequired = weight >= 0.6
    const size = 14 + (weight / maxWeight) * 14
    const skillColor = isRequired ? NODE_TYPE_COLORS.Skill : NODE_TYPE_COLORS.Tool

    graphNodes.push({
      id: e.target_id,
      style: {
        size,
        fill: skillColor,
        fillOpacity: 0.8,
        // 业务说明：必需技能使用成功色描边，辅助技能使用警告色描边，形成视觉区分
        stroke: isRequired ? cv('--success') : cv('--warning'),
        lineWidth: 1,
        labelText: skillNode.properties.name,
        labelFill: cv('--foreground'),
        labelFontSize: 10,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 4,
      },
    })

    // 业务说明：构建岗位到技能的 REQUIRES 边，必需技能使用实线+无箭头，辅助技能使用虚线+箭头
    graphEdges.push({
      id: `${posId}-${e.target_id}-REQUIRES`,
      source: posId,
      target: e.target_id,
      style: {
        stroke: skillColor,
        lineWidth: isRequired ? 2 : 1.5,
        opacity: 0.6,
        lineDash: isRequired ? [] : [5, 3],
        endArrow: !isRequired,
      },
    })
  }

  // 技术说明：注入节点与边数据，使用 radial 布局以岗位节点为中心辐射排列技能
  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  graph.value.setLayout({ type: 'radial', unitRadius: 140, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: false })
  graph.value.render()
  // 技术说明：延迟 300ms 自适应视图，确保 radial 布局稳定后再调整视口
  setTimeout(() => graph.value?.fitView(), 300)
}

// ── Resize handler ──
// 技术说明：监听窗口尺寸变化，动态调整 G6 画布大小，保证响应式适配
function handleResize() {
  if (!graph.value || !containerRef.value) return
  graph.value.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight)
}

// ── Watch: store changes → re-render ──
// 业务说明：监听当前图层变化，当用户切换领域/岗位/详情视图时重新渲染对应图层
watch(() => graphStore.currentLayer, () => {
  renderCurrentLayer()
})

// 业务说明：监听概览模式变化（如按层级/技术栈切换），重新渲染以应用不同布局算法
watch(() => graphStore.overviewMode, () => {
  renderCurrentLayer()
})

// 业务说明：监听可见节点数据变化（如后端数据拉取完成后），触发重新渲染
watch(() => graphStore.visibleNodes, () => {
  renderCurrentLayer()
})

// ── Watch: prop changes → re-render ──
// 业务说明：监听布局模式 prop 变化，用户切换力导向/层次/径向布局时即时重绘
watch(() => props.layoutMode, () => {
  renderCurrentLayer()
})

// 业务说明：监听演进关系显示开关变化，控制岗位间 EVOLVES_TO 边的显隐
watch(() => props.showEvolution, () => {
  renderCurrentLayer()
})

// 业务说明：监听最大节点数限制变化，当用户调整渲染上限时重新截断并渲染节点
watch(() => props.maxNodesLimit, () => {
  renderCurrentLayer()
})

// 业务说明：监听熟练度筛选条件变化，重新过滤技能节点并渲染详情图层
watch(() => props.proficiencyFilter, () => {
  renderCurrentLayer()
}, { deep: true })

// ── Lifecycle ──
// 技术说明：组件挂载后等待 DOM 就绪，再初始化 G6 实例并绑定 resize 事件监听器
onMounted(async () => {
  await nextTick()
  await initGraph()
  window.addEventListener('resize', handleResize)
})

// 技术说明：组件卸载时移除 resize 监听器并销毁 G6 实例，释放内存与事件绑定，防止内存泄漏
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (graph.value) { graph.value.destroy(); graph.value = null }
})
</script>

<template>
  <!-- 业务说明：G6 2D 图谱画布的容器节点，G6 会在该容器内自动创建 Canvas/SVG 渲染层 -->
  <div
    ref="containerRef"
    class="graph-2d-canvas"
  />
</template>

<style scoped>
/* 技术说明：画布容器占满父元素全部宽高，确保 G6 实例能自适应容器尺寸 */
.graph-2d-canvas {
  width: 100%;
  height: 100%;
}
</style>
