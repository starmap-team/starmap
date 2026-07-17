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
import type { Graph, G6GraphClass, G6ElementEvent, EvolutionEdgeClickPayload } from '@/types/g6'
// 业务说明：引入图层渲染 composables
import { renderDomainLayer, type DomainLayerDeps } from '@/composables/useDomainLayer'
import { renderPositionLayer, type PositionLayerDeps } from '@/composables/usePositionLayer'
import { renderDetailLayer, type DetailLayerDeps } from '@/composables/useDetailLayer'

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
  edgeClick: [edgeData: EvolutionEdgeClickPayload]
                                                    // 业务说明：用户点击演进边时触发，携带边的完整业务数据
}>()

// ── Store (read-only data access) ──
// 业务说明：获取图谱全局状态管理器，本组件以只读方式访问节点、边、领域、岗位等数据
const graphStore = useGraphStore()

// ── G6 dynamic loader ──
// 技术说明：缓存 G6 Graph 类，避免重复动态导入，减少网络请求与初始化耗时
let _G6GraphClass: G6GraphClass | null = null

// 技术说明：按需异步加载 @antv/g6 库，返回 Graph 构造函数；首次调用时执行导入并缓存
async function loadG6Graph(): Promise<G6GraphClass> {
  if (!_G6GraphClass) {
    const g6 = await import('@antv/g6')
    _G6GraphClass = g6.Graph
  }
  return _G6GraphClass
}

// ── CSS variable reader (shared from chartTheme) ──
import { cv, g6TooltipStyle } from '@/utils/chartTheme'

// ── Template refs & G6 instance ──
// 技术说明：模板引用，指向承载 G6 画布的真实 DOM 容器节点
const containerRef = ref<HTMLElement | null>(null)
// 技术说明：使用 shallowRef 持有 G6 实例，避免 Vue 对 G6 内部庞大对象进行深度响应式代理，降低内存与性能开销
const graph = shallowRef<Graph | null>(null)

// ── Layer dependency accessors (lazy-read current props/store state) ──
const domainDeps: DomainLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  layoutMode: () => props.layoutMode,
}
const positionDeps: PositionLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  showEvolution: () => props.showEvolution,
  maxNodesLimit: () => props.maxNodesLimit,
}
const detailDeps: DetailLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  maxNodesLimit: () => props.maxNodesLimit,
  proficiencyFilter: () => props.proficiencyFilter,
}

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
      plugins: ['minimap', { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { ...g6TooltipStyle(), borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '10px 14px' } }],
    })

    // 业务说明：监听节点单击事件，向上层抛出 nodeClick 事件，供父组件处理节点选中/下钻
    graph.value.on('node:click', (event: G6ElementEvent) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeClick', nodeId)
    })

    // 业务说明：监听节点双击事件，向上层抛出 nodeDblClick 事件，常用于打开节点详情面板
    graph.value.on('node:dblclick', (event: G6ElementEvent) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeDblClick', nodeId)
    })

    // 业务说明：监听画布单击事件，向上层抛出 canvasClick 事件，用于取消当前选中状态
    graph.value.on('canvas:click', () => {
      emit('canvasClick')
    })

    // 业务说明：监听边单击事件，仅处理演进边（ID 以 evo- 开头），解析源目标并抛出 edgeClick 事件
    graph.value.on('edge:click', (event: G6ElementEvent) => {
      const edgeId = event.target?.id
      if (edgeId && edgeId.startsWith('evo-')) {
        // 业务说明：在 Store 中查找匹配的演进边，提取完整业务数据后向上层抛出
        const evEdge = graphStore.evolutionEdges.find(e => edgeId === `evo-${e.source_id}-${e.target_id}`)
        if (evEdge) {
          emit('edgeClick', { source: evEdge.source_id, target: evEdge.target_id, type: evEdge.type, properties: evEdge.properties })
        }
      }
    })

    renderCurrentLayer()
  } catch (err) {
    if (import.meta.env.DEV) console.error('[Graph2D] Failed to initialize graph:', err)
    ElMessage.error('图谱加载失败，请确认后端服务已启动')
  }
}

// ── Render dispatch ──
// 业务说明：根据当前 Store 中的图层层级（domain/position/detail），分发到对应的渲染函数
let _renderTimer: ReturnType<typeof setTimeout> | null = null
function renderCurrentLayer() {
  if (!graph.value) return
  if (_renderTimer) clearTimeout(_renderTimer)
  _renderTimer = setTimeout(() => {
    _renderTimer = null
    if (graphStore.currentLayer === 'domain') {
      renderDomainLayer(domainDeps)
    } else if (graphStore.currentLayer === 'position') {
      renderPositionLayer(positionDeps)
    } else {
      renderDetailLayer(detailDeps)
    }
  }, 50)
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
