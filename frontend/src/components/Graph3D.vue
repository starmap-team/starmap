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
import {
  nodeColor,
  edgeColor,
  withAlpha,
  SCENE_PALETTE,
  toThreeHex,
} from '@/utils/graphColors'
import NodeTooltip3D from './NodeTooltip3D.vue'
import { Loading } from '@element-plus/icons-vue'

// ── Types ──
interface GraphNode3D {
  id: string
  labels?: string[]
  color?: string            // Precomputed by parent (Home.vue) for consistent 2D/3D coloring
  properties: {
    name: string
    category?: string
    proficiency?: string
    position_count?: number
    skill_count?: number
    weight?: number
    [key: string]: any
  }
  // Populated by 3d-force-graph after layout
  x?: number
  y?: number
  z?: number
}

interface GraphLink3D {
  source: string | GraphNode3D
  target: string | GraphNode3D
  type?: string
  properties?: { weight?: number }
}

export type CameraPreset = 'overview' | 'domain' | 'position'

// ── Props ──
const props = withDefaults(defineProps<{
  nodes: GraphNode3D[]
  links: GraphLink3D[]
  width?: number
  height?: number
}>(), {
  width: 800,
  height: 600,
})

const emit = defineEmits<{
  nodeClick: [nodeId: string]
  nodeDblClick: [nodeId: string]
}>()

// ── Refs ──
const containerRef = ref<HTMLElement | null>(null)
const webglSupported = ref(true)
const fps = ref(0)
const autoRotate = ref(false)
const isReady = ref(false)
const tooltipNode = ref<{
  id: string; name: string; type: string;
  position_count?: number; skill_count?: number;
  proficiency?: string; category?: string
} | null>(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
const tooltipVisible = ref(false)

// Graph instance (shallow to avoid Vue reactivity overhead)
const graphInstance = shallowRef<any>(null)

// ── Node helpers ──
function getNodeLabel(node: GraphNode3D): string {
  return node.labels?.[0] ?? 'Unknown'
}

function getNodeRadius(node: GraphNode3D): number {
  const label = getNodeLabel(node)
  switch (label) {
    case 'KnowledgeArea': {
      const skills = node.properties.skill_count ?? 1
      return 6 + Math.sqrt(skills) * 2.5
    }
    case 'Position':
      return 3.5 + (node.properties.weight ?? 0.5) * 3
    case 'Skill':
      return 2 + (node.properties.weight ?? 0.5) * 2
    default:
      return 2.5
  }
}

// ── Initialize 3D graph (async, dynamic import) ──
async function initGraph() {
  if (!containerRef.value || !webglSupported.value) return

  // Dynamic import to keep 3d-force-graph out of the main bundle
  const ForceGraphModule = await import('3d-force-graph')
  const ForceGraph3D = ForceGraphModule.default
  // Attach THREE to window for nodeThreeObject custom rendering
  if (!(window as any).__THREE) {
    const THREE_MOD = await import('three')
    ;(window as any).__THREE = THREE_MOD
  }

  const container = containerRef.value
  const w = container.clientWidth || props.width
  const h = container.clientHeight || props.height

  // ── Force engine tuning（节点多时增大排斥力防止黏连） ──
  const nodeCount = props.nodes.length
  const chargeStrength = nodeCount > 200 ? -80 : nodeCount > 100 ? -60 : -40
  const linkDist = nodeCount > 100 ? 60 : 40
  const linkStrength = nodeCount > 100 ? 0.3 : 0.5

  const graph = new ForceGraph3D(container)
    .width(w)
    .height(h)
    .backgroundColor(SCENE_PALETTE.background)
    .showNavInfo(false)

    // ── Node configuration ──
    .nodeVal((node: any) => getNodeRadius(node))
    .nodeColor((node: any) => {
      // Use precomputed color (from Home.vue) or fall back to type color
      return node.color ?? nodeColor(getNodeLabel(node))
    })
    .nodeResolution(16)  // Sphere segments (smoother spheres)
    .nodeOpacity(0.92)

    // ── Node label (3D text sprite) ──
    .nodeLabel((node: any) => {
      return `<div style="
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
        font-size: 12px; font-weight: 600; color: #e2e8f0;
        background: rgba(10,14,26,0.85); padding: 4px 10px;
        border-radius: 8px; border: 1px solid rgba(100,116,139,0.3);
        backdrop-filter: blur(8px); white-space: nowrap;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      ">${node.properties.name}</div>`
    })

    // ── Edge configuration ──
    .linkColor((link: any) => {
      return withAlpha(edgeColor(link.type ?? 'DEFAULT'), 0.35)
    })
    .linkWidth((link: any) => {
      const w = link.properties?.weight ?? 0.5
      return 0.5 + w * 1.5
    })
    .linkOpacity(0.3)
    .linkDirectionalArrowLength(3.5)
    .linkDirectionalArrowRelPos(1)
    .linkCurvature(0.1)

    // ── Force charge & link tuning ──
    .d3Force('charge', () => chargeStrength)
    .d3Force('link', () => linkDist)
    .d3AlphaDecay(nodeCount > 300 ? 0.05 : 0.02)
    .d3VelocityDecay(nodeCount > 300 ? 0.4 : 0.3)
    .warmupTicks(nodeCount > 300 ? 30 : 50)
    .cooldownTicks(nodeCount > 300 ? 100 : 200)

  // 额外调优：link 距离和强度 + center 引力
  try {
    const linkForce = (graph as any).d3Force('link')
    if (linkForce) { linkForce.distance(linkDist); linkForce.strength(linkStrength) }
    const center = (graph as any).d3Force('center')
    if (center) center.strength(0.15)
  } catch (_) {
    // d3Force may not be available in all versions
  }

  // ── Interactions ──
  graph.onNodeHover((node: any, _prevNode: any) => {
    if (node) {
      const typed = node as GraphNode3D
      const label = getNodeLabel(typed)
      tooltipNode.value = {
        id: typed.id,
        name: typed.properties.name,
        type: label,
        position_count: typed.properties.position_count,
        skill_count: typed.properties.skill_count,
        proficiency: typed.properties.proficiency,
        category: typed.properties.category,
      }
      tooltipVisible.value = true
    } else {
      tooltipVisible.value = false
      tooltipNode.value = null
    }
  })

  // Track mouse for tooltip positioning
  container.addEventListener('mousemove', (e: MouseEvent) => {
    tooltipX.value = e.clientX
    tooltipY.value = e.clientY
  })

  // Double-click detection via onNodeClick + timestamp
  let lastClickTime = 0
  let lastClickId = ''

  graph.onNodeClick((node: any) => {
    const now = Date.now()
    if (node.id === lastClickId && now - lastClickTime < 300) {
      // Double-click: emit nodeDblClick for drill-down
      emit('nodeDblClick', node.id)
      lastClickTime = 0
      lastClickId = ''
    } else {
      // Single click
      lastClickTime = now
      lastClickId = node.id
      emit('nodeClick', node.id)
    }
  })

  graphInstance.value = graph

  // Set graph data
  graph.graphData({ nodes: props.nodes, links: props.links })

  // Setup glow post-processing for domain nodes
  setupGlowEffect(graph)

  isReady.value = true
}

// ── Glow effect for large nodes (domain spheres) ──
function setupGlowEffect(graph: any) {
  // Custom node rendering with glow for KnowledgeArea nodes
  graph.nodeThreeObject((node: GraphNode3D) => {
    const label = getNodeLabel(node)
    const radius = getNodeRadius(node)
    const color = toThreeHex(node.color ?? nodeColor(label))

    // Dynamic import three lazily
    // We use the THREE namespace that 3d-force-graph already has internally
    const THREE = (window as any).__THREE
    if (!THREE) {
      // Fallback: no custom object, use default sphere
      return null
    }

    // Create sphere with custom material
    const geometry = new THREE.SphereGeometry(radius, 24, 24)

    if (label === 'KnowledgeArea') {
      // Glowing domain sphere
      const material = new THREE.MeshPhongMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.4,
        transparent: true,
        opacity: 0.92,
        shininess: 80,
      })
      const mesh = new THREE.Mesh(geometry, material)

      // Add glow sprite
      const spriteMaterial = new THREE.SpriteMaterial({
        map: createGlowTexture(color, THREE),
        transparent: true,
        opacity: 0.3,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
      const sprite = new THREE.Sprite(spriteMaterial)
      sprite.scale.set(radius * 4, radius * 4, 1)
      mesh.add(sprite)

      return mesh
    }

    if (label === 'Position') {
      // Solid blue sphere with subtle emissive
      const material = new THREE.MeshPhongMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.2,
        transparent: true,
        opacity: 0.88,
        shininess: 60,
      })
      return new THREE.Mesh(geometry, material)
    }

    if (label === 'Skill') {
      // Smaller, slightly emissive sphere
      const material = new THREE.MeshPhongMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.15,
        transparent: true,
        opacity: 0.85,
        shininess: 40,
      })
      return new THREE.Mesh(geometry, material)
    }

    return null // Use default for other types
  })
}

// ── Glow texture cache (key = hexColor) ──
const _glowCache = new Map<number, any>()

/** 释放 glow 纹理缓存（组件卸载时调用）。 */
function disposeGlowCache() {
  _glowCache.clear()
}

// ── Glow texture generator (canvas-based, with cache) ──
function createGlowTexture(hexColor: number, THREE: any): any {
  const cached = _glowCache.get(hexColor)
  if (cached) return cached

  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!

  // Extract RGB from hex
  const r = (hexColor >> 16) & 0xff
  const g = (hexColor >> 8) & 0xff
  const b = hexColor & 0xff

  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.6)`)
  gradient.addColorStop(0.3, `rgba(${r}, ${g}, ${b}, 0.25)`)
  gradient.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, 0.08)`)
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)

  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  _glowCache.set(hexColor, texture)
  return texture
}

// ── Camera presets ──
function setCameraPreset(preset: CameraPreset) {
  const graph = graphInstance.value
  if (!graph) return

  // Stop auto-rotate during transition
  const controls = graph.controls()
  if (controls) {
    controls.autoRotate = false
  }

  const dist = { x: 0, y: 0, z: 0 }
  let distance = 0

  switch (preset) {
    case 'overview':
      // Pull camera far back for panoramic view
      distance = Math.max(300, props.nodes.length * 2.5)
      dist.x = distance * 0.6
      dist.y = distance * 0.5
      dist.z = distance * 0.7
      break

    case 'domain':
      // Closer, angled view focusing on domain clusters
      distance = Math.max(150, props.nodes.length * 1.2)
      dist.x = distance * 0.4
      dist.y = distance * 0.6
      dist.z = distance * 0.5
      break

    case 'position':
      // Tight view for position-skill networks
      distance = Math.max(100, props.nodes.length * 0.8)
      dist.x = distance * 0.3
      dist.y = distance * 0.3
      dist.z = distance * 0.8
      break
  }

  // Animate camera position
  graph.cameraPosition(
    { x: dist.x, y: dist.y, z: dist.z },
    { x: 0, y: 0, z: 0 },  // lookAt center
    1500  // transition duration ms
  )

  // Restore auto-rotate after transition
  if (autoRotate.value) {
    setTimeout(() => {
      if (controls) controls.autoRotate = true
    }, 1600)
  }
}

// ── Reset camera to initial position ──
function resetCamera() {
  const graph = graphInstance.value
  if (!graph) return
  const dist = Math.max(250, props.nodes.length * 2)
  graph.cameraPosition(
    { x: dist * 0.5, y: dist * 0.4, z: dist * 0.6 },
    { x: 0, y: 0, z: 0 },
    1200
  )
}

// ── Toggle auto-rotate ──
function toggleAutoRotate() {
  autoRotate.value = !autoRotate.value
  const graph = graphInstance.value
  if (!graph) return
  const controls = graph.controls()
  if (controls) {
    controls.autoRotate = autoRotate.value
    controls.autoRotateSpeed = 0.8
  }
}

// ── FPS monitoring ──
let fpsFrames = 0
let fpsLastTime = performance.now()
let fpsRafId = 0

function measureFPS() {
  fpsFrames++
  const now = performance.now()
  if (now - fpsLastTime >= 1000) {
    fps.value = fpsFrames
    fpsFrames = 0
    fpsLastTime = now
  }
  fpsRafId = requestAnimationFrame(measureFPS)
}

// ── Update data when props change ──
watch(() => [props.nodes, props.links], () => {
  const graph = graphInstance.value
  if (!graph) return
  graph.graphData({ nodes: props.nodes, links: props.links })
}, { deep: false })

// ── Resize handling ──
function handleResize() {
  const graph = graphInstance.value
  if (!graph || !containerRef.value) return
  const w = containerRef.value.clientWidth
  const h = containerRef.value.clientHeight
  graph.width(w).height(h)
}

// ── Lifecycle ──
onMounted(async () => {
  await nextTick()
  try {
    await initGraph()
  } catch {
    // ponytail: 3d-force-graph / Three.js will throw if WebGL unavailable
    webglSupported.value = false
    return
  }
  measureFPS()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  cancelAnimationFrame(fpsRafId)
  disposeGlowCache()
  if (graphInstance.value) {
    graphInstance.value._destructor?.()
    graphInstance.value = null
  }
})

// ── Expose methods for parent ──
defineExpose({
  setCameraPreset,
  resetCamera,
  toggleAutoRotate,
  autoRotate,
  fps,
})
</script>

<template>
  <div class="graph3d-wrapper">
    <!-- WebGL not supported fallback -->
    <div
      v-if="!webglSupported"
      class="webgl-fallback"
    >
      <div class="fallback-icon">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        >
          <path d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p class="fallback-title">
        WebGL 不可用
      </p>
      <p class="fallback-text">
        您的浏览器或设备不支持 WebGL 3D 渲染。<br>请使用最新版 Chrome / Edge / Firefox 浏览器，或切换到 2D 视图。
      </p>
    </div>

    <!-- 3D Graph container -->
    <div
      v-show="webglSupported"
      ref="containerRef"
      class="graph3d-container"
    />

    <!-- Loading indicator during force simulation warmup -->
    <div
      v-if="webglSupported && !isReady"
      class="graph3d-loading"
    >
      <el-icon
        class="is-loading"
        :size="24"
      >
        <Loading />
      </el-icon>
      <span>力导向布局计算中...</span>
    </div>

    <!-- FPS counter overlay -->
    <div
      v-if="webglSupported && isReady"
      class="fps-counter"
    >
      {{ fps }} FPS
    </div>

    <!-- Node tooltip -->
    <NodeTooltip3D
      :node="tooltipNode"
      :x="tooltipX"
      :y="tooltipY"
      :visible="tooltipVisible"
    />
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
  background: #0a0e1a;
}

.graph3d-container {
  width: 100%;
  height: 100%;
  min-height: 520px;
}

.graph3d-container :deep(canvas) {
  border-radius: inherit;
}

/* Loading indicator */
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
  color: #94a3b8;
  font-size: 14px;
  z-index: 10;
}

/* FPS counter */
.fps-counter {
  position: absolute;
  bottom: 12px;
  right: 14px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
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

/* WebGL fallback */
.webgl-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 520px;
  gap: 12px;
  color: #64748b;
  text-align: center;
  padding: 40px;
}

.fallback-icon {
  color: #f59e0b;
  opacity: 0.7;
}

.fallback-title {
  font-size: 18px;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0;
}

.fallback-text {
  font-size: 13px;
  line-height: 1.6;
  color: #94a3b8;
  margin: 0;
  max-width: 360px;
}
</style>
