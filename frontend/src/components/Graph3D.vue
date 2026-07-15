<script setup lang="ts">
/**
 * Graph3D — 3D force-directed graph visualization using 3d-force-graph
 * The visual centrepiece of StarMap's panoramic knowledge graph.
 *
 * - Dynamic import of 3d-force-graph (code-split)
 * - WebGL detection with graceful 2D fallback
 * - Node sizing/colors by type (domain=large glowing sphere, position=medium, skill=small)
 * - Semi-transparent gradient edges
 * - Camera presets, auto-rotate, FPS counter
 * - Hover tooltip via NodeTooltip3D
 */
import { ref, onMounted, onUnmounted, watch, nextTick, shallowRef } from 'vue'
import { nodeColor, edgeColor, withAlpha, SCENE_PALETTE } from '@/utils/graphColors'
import NodeTooltip3D from './NodeTooltip3D.vue'
import { Loading } from '@element-plus/icons-vue'
import {
  type GraphNode3D,
  getNodeLabel,
  getNodeRadius,
  NODE_COLLISION_PADDING,
  buildNodeThreeObject,
} from '@/composables/useNodeThreeObject'
import { type GraphLink3D, evolutionColor, composeEvolutionLinks } from '@/composables/useEvolutionEdges'
import { calcForceConfig, applyForceConfig } from '@/composables/useForceConfig'
import { disposeGlowCache } from '@/composables/useGlowTexture'
import { disposeTextCache } from '@/composables/useTextSprite'
import { useCameraPresets, type CameraPreset } from '@/composables/useCameraPresets'

// ── Security ──
function escapeHtml(s: string): string {
  const d = document.createElement('div')
  d.textContent = s
  return d.innerHTML
}

// ── Props ──
const props = withDefaults(defineProps<{
  nodes: GraphNode3D[]
  links: GraphLink3D[]
  width?: number
  height?: number
  currentLayer?: 'domain' | 'position' | 'detail'
  showEvolution?: boolean
  evolutionPaths?: GraphLink3D[]
  currentDomainId?: string | null
}>(), {
  width: 800,
  height: 600,
  currentLayer: 'domain',
  showEvolution: false,
  evolutionPaths: () => [],
  currentDomainId: null,
})

const emit = defineEmits<{
  nodeClick: [nodeId: string]
  nodeDblClick: [nodeId: string]
  evolutionEdgeClick: [edge: GraphLink3D]
  autoRotateChange: [value: boolean]
}>()

// ── Refs ──
const containerRef = ref<HTMLElement | null>(null)
const webglSupported = ref(true)
const fps = ref(0)
const isReady = ref(false)
const tooltipNode = ref<{
  id: string; name: string; type: string;
  position_count?: number; skill_count?: number;
  proficiency?: string; category?: string
} | null>(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
const tooltipVisible = ref(false)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const graphInstance = shallowRef<any>(null)

// ── Camera presets composable ──
const { autoRotate, setCameraPreset, resetCamera, toggleAutoRotate, clearAutoRotateTimer } = useCameraPresets(
  graphInstance,
  () => props.nodes,
)

// ── Mouse move handler (component-scoped for cleanup) ──
let _mouseMoveHandler: ((e: MouseEvent) => void) | null = null

async function initGraph() {
  if (!containerRef.value || !webglSupported.value) return

  // 销毁旧实例，防止回调丢失或重复绑定
  if (graphInstance.value) {
    graphInstance.value._destructor?.()
    graphInstance.value = null
  }

  if (props.nodes.length === 0) { isReady.value = false; return }

  // Dynamic import to keep 3d-force-graph out of the main bundle
  const ForceGraphModule = await import('3d-force-graph')
  const ForceGraph3D = ForceGraphModule.default
  // Attach THREE to window for nodeThreeObject custom rendering
  if (!(window as unknown as Record<string, unknown>).__THREE) {
    const THREE_MOD = await import('three')
    ;(window as unknown as Record<string, unknown>).__THREE = THREE_MOD
  }

  const container = containerRef.value
  const w = container.clientWidth || props.width
  const h = container.clientHeight || props.height
  const nodeCount = props.nodes.length
  const cfg = calcForceConfig(nodeCount)

  const graph = new ForceGraph3D(container)
    .width(w).height(h)
    .backgroundColor(SCENE_PALETTE.background)
    .showNavInfo(false)
    // ── Node configuration ──
    .nodeVal((node) => getNodeRadius(node as GraphNode3D))
    .nodeColor((node) => {
      const n = node as GraphNode3D
      return n.color ?? nodeColor(getNodeLabel(n))
    })
    .nodeResolution(16)
    .nodeOpacity(0.75)
    .nodeThreeObject(buildNodeThreeObject)
    // ── Node label (3D text sprite) ──
    // Disable 3d-force-graph's default HTML tooltip — textSprite (via
    // buildNodeThreeObject) already provides a persistent 3D label above
    // each node, and NodeTooltip3D handles hover details.
    .nodeLabel(() => '')
    // ── Edge configuration ──
    .linkColor((link) => {
      const l = link as GraphLink3D
      if (l.type === 'EVOLVES_TO') return evolutionColor(l)
      return withAlpha(edgeColor(l.type ?? 'DEFAULT'), 0.35)
    })
    .linkWidth((link) => {
      const l = link as GraphLink3D
      if (l.type === 'EVOLVES_TO') {
        const trust = l.properties?.similarity ?? l.properties?.weight ?? 0.5
        return 0.6 + trust * 1.2
      }
      const w = l.properties?.weight ?? 0.5
      return 0.5 + w * 1.5
    })
    .linkOpacity(0.4)
    .linkDirectionalArrowLength(3.5)
    .linkDirectionalArrowRelPos(1)
    .linkCurvature(0.1)
    // ── Force tuning ──
    .d3AlphaDecay(cfg.alphaDecay)
    .d3VelocityDecay(cfg.velocityDecay)
    .warmupTicks(cfg.warmupTicks)
    .cooldownTicks(cfg.cooldownTicks)

  // Apply charge/link/center/collision forces
  applyForceConfig(graph, nodeCount, NODE_COLLISION_PADDING, getNodeRadius, true)

  // ── Interactions ──
  // Track previously hovered node to restore its textSprite visibility
  let _prevHoveredNode: GraphNode3D | null = null

  function _setTextSpriteVisible(nodeObj: GraphNode3D, visible: boolean) {
    // nodeObj.__threeObj is the Three.js Object3D created by buildNodeThreeObject
    // textSprite is the last Sprite child added in buildNodeThreeObject
    const threeObj = (nodeObj as unknown as { __threeObj?: import('three').Object3D }).__threeObj
    if (!threeObj) return
    threeObj.traverse((child) => {
      // Sprites added by createTextSprite carry a userData flag
      if (child.type === 'Sprite' && child.userData.isTextSprite) {
        child.visible = visible
      }
    })
  }

  graph.onNodeHover((node) => {
    // Restore previous node's textSprite
    if (_prevHoveredNode) {
      _setTextSpriteVisible(_prevHoveredNode, true)
      _prevHoveredNode = null
    }
    if (node) {
      const typed = node as GraphNode3D
      // Hide textSprite on hover — NodeTooltip3D already shows the name
      _setTextSpriteVisible(typed, false)
      _prevHoveredNode = typed
      tooltipNode.value = {
        id: String(typed.id), name: typed.properties.name, type: getNodeLabel(typed),
        position_count: typed.properties.position_count, skill_count: typed.properties.skill_count,
        proficiency: typed.properties.proficiency, category: typed.properties.category,
      }
      tooltipVisible.value = true
    } else {
      tooltipVisible.value = false
      tooltipNode.value = null
    }
  })

  _mouseMoveHandler = (e: MouseEvent) => { tooltipX.value = e.clientX; tooltipY.value = e.clientY }
  container.addEventListener('mousemove', _mouseMoveHandler)

  // Double-click detection via onNodeClick + timestamp
  let lastClickTime = 0
  let lastClickId = ''
  graph.onNodeClick((node) => {
    const now = Date.now()
    const nodeId = String(node.id)
    if (nodeId === lastClickId && now - lastClickTime < 300) {
      emit('nodeDblClick', nodeId)
      lastClickTime = 0; lastClickId = ''
    } else {
      lastClickTime = now; lastClickId = nodeId
      emit('nodeClick', nodeId)
    }
  })

  graph.onLinkClick((link) => {
    if ((link as GraphLink3D).type === 'EVOLVES_TO') emit('evolutionEdgeClick', link as GraphLink3D)
  })

  // 力模拟稳定后自动适配相机，确保用户看到全局
  graph.onEngineStop(() => {
    _engineStopHandled = true
    const presetMap: Record<string, CameraPreset> = { domain: 'overview', position: 'domain', detail: 'position' }
    setCameraPreset(presetMap[props.currentLayer] ?? 'overview')
  })

  graphInstance.value = graph
  graph.graphData({ nodes: props.nodes, links: props.links })
  isReady.value = true
}

// ── FPS monitoring ──
let fpsFrames = 0
let fpsLastTime = performance.now()
let fpsRafId = 0
function measureFPS() {
  fpsFrames++
  const now = performance.now()
  if (now - fpsLastTime >= 1000) { fps.value = fpsFrames; fpsFrames = 0; fpsLastTime = now }
  fpsRafId = requestAnimationFrame(measureFPS)
}

// 标志位：onEngineStop 触发后置 true，避免 watch setTimeout 重复定位相机
let _engineStopHandled = false

// ── Update data when props change ──
// 单一 watch 合并数据+层级变化，避免两个 watch 同时触发 setCameraPreset 导致双重渲染
watch(() => [props.nodes, props.links, props.showEvolution, props.evolutionPaths, props.currentDomainId, props.currentLayer] as const, ([_n, _l, _evo, _evoP, _domId, newLayer], _old) => {
  const graph = graphInstance.value
  if (!graph) { if (props.nodes.length > 0) initGraph(); return }

  const nodeCount = props.nodes.length
  const composedLinks = composeEvolutionLinks(props.links, props.evolutionPaths, props.nodes, props.showEvolution)

  // 保存旧节点的位置映射，用于为相同 ID 的新节点提供初始位置
  const oldNodes: GraphNode3D[] = graph.graphData().nodes
  const posMap = new Map<string, { x: number; y: number; z: number }>()
  for (const n of oldNodes) {
    if (n.x !== undefined && n.y !== undefined && n.z !== undefined) {
      posMap.set(String(n.id), { x: n.x, y: n.y, z: n.z })
    }
  }
  // 为新数据中没有位置信息的节点，从旧位置映射中继承位置
  for (const n of props.nodes) {
    if (n.x === undefined || n.y === undefined || n.z === undefined) {
      const oldPos = posMap.get(String(n.id))
      if (oldPos) {
        n.x = oldPos.x
        n.y = oldPos.y
        n.z = oldPos.z
      }
    }
  }

  graph.graphData({ nodes: props.nodes, links: composedLinks })
  graph.nodeThreeObject(buildNodeThreeObject)
  applyForceConfig(graph, nodeCount, NODE_COLLISION_PADDING, getNodeRadius, false)

  // 重置标志位，让 onEngineStop 接管相机定位
  _engineStopHandled = false
  // 轻量 reheat：只给少量 alpha 让新节点微调，不会导致全局抽动
  graph.d3ReheatSimulation()
  // 快速冷却，避免已稳定节点剧烈跳动
  graph.d3AlphaDecay(0.1)

  // 兜底：如果 onEngineStop 未触发（极短冷却），setTimeout 仍可定位相机
  const cfg = calcForceConfig(nodeCount)
  const settleMs = Math.min(cfg.warmupTicks * 16 + 200, 800)
  setTimeout(() => {
    if (!_engineStopHandled && graphInstance.value) {
      const presetMap: Record<string, CameraPreset> = { domain: 'overview', position: 'domain', detail: 'position' }
      setCameraPreset(presetMap[newLayer] ?? 'overview')
    }
  }, settleMs)
}, { deep: false })

// ── Watch: layer changes → auto-adjust camera ──
// 已合并到上方主 watch 中，不再需要独立 watch

// ── Resize handling ──
function handleResize() {
  const graph = graphInstance.value
  if (!graph || !containerRef.value) return
  graph.width(containerRef.value.clientWidth).height(containerRef.value.clientHeight)
}

// ── Lifecycle ──
onMounted(async () => {
  await nextTick()
  try { await initGraph() } catch { webglSupported.value = false; return }
  measureFPS()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  cancelAnimationFrame(fpsRafId)
  clearAutoRotateTimer()
  if (containerRef.value && _mouseMoveHandler) containerRef.value.removeEventListener('mousemove', _mouseMoveHandler)
  disposeGlowCache()
  disposeTextCache()
  if (graphInstance.value) { graphInstance.value._destructor?.(); graphInstance.value = null }
})

// ── Expose methods for parent ──
// 新增 autoRotateChange 事件，用于同步 autoRotate 状态到父组件
// 注意：这里不能重复 defineEmits，因为上面已经定义了 emit
// 包装 toggleAutoRotate，在切换后 emit 事件
function _toggleAutoRotate() {
  toggleAutoRotate()
  emit('autoRotateChange', autoRotate.value)
}

defineExpose({ setCameraPreset, resetCamera, toggleAutoRotate: _toggleAutoRotate, autoRotate, fps })
</script>

<template>
  <div class="graph3d-wrapper">
    <!-- WebGL not supported fallback -->
    <div v-if="!webglSupported" class="webgl-fallback">
      <div class="fallback-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p class="fallback-title">WebGL 不可用</p>
      <p class="fallback-text">您的浏览器或设备不支持 WebGL 3D 渲染。<br>请使用最新版 Chrome / Edge / Firefox 浏览器，或切换到 2D 视图。</p>
    </div>

    <!-- 3D Graph container -->
    <div v-show="webglSupported" ref="containerRef" class="graph3d-container" />

    <!-- Loading indicator during force simulation warmup -->
    <div v-if="webglSupported && !isReady" class="graph3d-loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>力导向布局计算中...</span>
    </div>

    <!-- FPS counter overlay -->
    <div v-if="webglSupported && isReady" class="fps-counter">{{ fps }} FPS</div>

    <!-- Node tooltip -->
    <NodeTooltip3D :node="tooltipNode" :x="tooltipX" :y="tooltipY" :visible="tooltipVisible" />
  </div>
</template>

<style scoped>
.graph3d-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 520px;
  overflow: hidden;
  border-radius: inherit;
  background: var(--scene-bg, #0a0e1a);
}
.graph3d-container {
  width: 100%;
  height: 100%;
  min-height: 520px;
}
.graph3d-container :deep(canvas) {
  border-radius: inherit;
}
.graph3d-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(10, 14, 26, 0.6);
  backdrop-filter: blur(4px);
  color: var(--muted-foreground, #94a3b8);
  font-size: 14px;
  z-index: 10;
}
.fps-counter {
  position: absolute;
  bottom: 12px;
  right: 14px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground, #94a3b8);
  background: rgba(10, 14, 26, 0.7);
  backdrop-filter: blur(8px);
  padding: 3px 10px;
  border-radius: 8px;
  border: 1px solid rgba(100, 116, 139, 0.2);
  pointer-events: none;
  z-index: 5;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}
.webgl-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 520px;
  gap: 12px;
  color: var(--muted-foreground, #64748b);
  text-align: center;
  padding: 40px;
}
.fallback-icon { color: var(--warning, #f59e0b); opacity: 0.7; }
.fallback-title { font-size: 18px; font-weight: 700; color: var(--foreground, #e2e8f0); margin: 0; }
.fallback-text { font-size: 13px; line-height: 1.6; color: var(--muted-foreground, #94a3b8); margin: 0; max-width: 360px; }
</style>
