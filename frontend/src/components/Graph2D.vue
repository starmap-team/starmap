<script setup lang="ts">
/**
 * Graph2D — G6 v5 force-directed graph visualization (2D counterpart to Graph3D).
 *
 * Owns all G6 lifecycle: dynamic import, instance creation, three-layer rendering,
 * layout switching, node highlighting, and resize handling.
 *
 * UI state comes from props; graph data is read from the store.
 */
import { ref, onMounted, onUnmounted, watch, nextTick, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { useGraphStore } from '@/stores/graph'
import { NODE_TYPE_COLORS, KA_FALLBACK_COLORS } from '@/utils/graphColors'

// ── Props (UI state owned by parent) ──
const props = withDefaults(defineProps<{
  layoutMode?: 'force' | 'dagre' | 'radial'
  kaColorMap?: Map<string, string>
  showEvolution?: boolean
  maxNodesLimit?: number
  proficiencyFilter?: string[]
}>(), {
  layoutMode: 'force',
  kaColorMap: () => new Map(),
  showEvolution: false,
  maxNodesLimit: 80,
  proficiencyFilter: () => ['精通', '熟悉', '了解'],
})

// ── Events ──
const emit = defineEmits<{
  nodeClick: [nodeId: string]
  nodeDblClick: [nodeId: string]
  canvasClick: []
}>()

// ── Store (read-only data access) ──
const graphStore = useGraphStore()

// ── G6 dynamic loader (moved from useGraphColors.ts) ──
let _G6GraphClass: any = null

async function loadG6Graph(): Promise<any> {
  if (!_G6GraphClass) {
    const g6 = await import('@antv/g6')
    _G6GraphClass = g6.Graph
  }
  return _G6GraphClass
}

// ── CSS variable cache (moved from useGraphColors.ts) ──
const _cvCache = new Map<string, string>()

function cv(name: string): string {
  let value = _cvCache.get(name)
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    _cvCache.set(name, value)
  }
  return value
}

// ── Template refs & G6 instance ──
const containerRef = ref<HTMLElement | null>(null)
const graph = shallowRef<any>(null)

// ── Exposed methods ──
function zoomBy(factor: number) {
  graph.value?.zoomBy(factor)
}
function fitView() {
  graph.value?.fitView()
}
function highlightNode(nodeId: string) {
  if (!graph.value) return
  const relatedIds = new Set<string>([nodeId])
  for (const e of graphStore.visibleEdges) {
    if (e.source_id === nodeId) relatedIds.add(e.target_id)
    if (e.target_id === nodeId) relatedIds.add(e.source_id)
  }
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
function clearHighlight() {
  renderCurrentLayer()
}

defineExpose({ zoomBy, fitView, highlightNode, clearHighlight })

// ── G6 initialization ──
async function initGraph() {
  if (!containerRef.value) return
  if (graph.value) { graph.value.destroy(); graph.value = null }
  const container = containerRef.value
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  try {
    const GraphClass = await loadG6Graph()
    graph.value = new GraphClass({
      container,
      width,
      height,
      layout: { type: 'force', preventOverlap: true, nodeSize: 40, nodeSpacing: 20, animate: true },
      node: {
        style: {
          labelFill: cv('--foreground'),
          labelFontSize: 12,
          labelPlacement: 'bottom' as const,
          labelOffsetY: 8,
          labelFontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
      },
      edge: {
        style: {
          stroke: cv('--border'),
          lineWidth: 1.5,
          opacity: 0.5,
          endArrow: true,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', { type: 'hover-activate', degree: 1, direction: 'both' }],
      plugins: ['minimap', { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { background: cv('--card'), borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '10px 14px', fontSize: '12px', border: '1px solid ' + cv('--border'), color: cv('--foreground') } }],
    })

    graph.value.on('node:click', (event: any) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeClick', nodeId)
    })

    graph.value.on('node:dblclick', (event: any) => {
      const nodeId = event.target?.id
      if (nodeId) emit('nodeDblClick', nodeId)
    })

    graph.value.on('canvas:click', () => {
      emit('canvasClick')
    })

    renderCurrentLayer()
  } catch (err) {
    console.error('[Graph2D] Failed to initialize graph:', err)
    ElMessage.error('图谱加载失败，请确认后端服务已启动')
  }
}

// ── Render dispatch ──
function renderCurrentLayer() {
  if (!graph.value) return
  if (graphStore.currentLayer === 'domain') {
    renderDomainLayer()
  } else if (graphStore.currentLayer === 'position') {
    renderPositionLayer()
  } else {
    renderDetailLayer()
  }
}

// ── Layer 1: Domain (KA islands) ──
function renderDomainLayer() {
  if (!graph.value) return
  const maxSkill = Math.max(...graphStore.domains.map(d => d.skill_count), 1)
  const minSize = 50, maxSize = 100

  const visibleFiltered = graphStore.visibleNodes.filter(n => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    return domain && (domain.position_count > 0 || domain.skill_count > 0)
  })

  const graphNodes = visibleFiltered.map((n, i) => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    const skillCount = domain?.skill_count ?? 0
    const posCount = domain?.position_count ?? 0
    const importance = skillCount + posCount * 2
    const size = minSize + (skillCount / maxSkill) * (maxSize - minSize)
    const color = props.kaColorMap.get(n.id) ?? KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length]
    return {
      id: n.id,
      style: {
        size,
        fill: color,
        fillOpacity: 0.9,
        stroke: color,
        lineWidth: importance > 100 ? 3 : 2,
        labelText: n.properties.name + '\n' + posCount + '岗 ' + skillCount + '技',
        labelFill: cv('--primary-foreground'),
        labelFontSize: importance > 100 ? 15 : 13,
        labelFontWeight: 'bold' as const,
        labelPlacement: 'center' as const,
        shadowColor: 'rgba(0,0,0,0.2)',
        shadowBlur: importance > 100 ? 20 : 12,
        cursor: 'pointer' as const,
      },
    }
  })

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

  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  const entranceNodes = graphNodes.map((n: any) => ({
    id: n.id,
    style: { fillOpacity: 0, scale: 0.3 },
  }))
  graph.value.updateNodeData(entranceNodes)

  const isLevel = graphStore.overviewMode === 'level'
  const isTechStack = graphStore.overviewMode === 'tech_stack'
  if (props.layoutMode === 'dagre' || isLevel) {
    graph.value.setLayout({ type: 'dagre', rankdir: 'TB', nodesep: isLevel ? 140 : 80, ranksep: isLevel ? 160 : 100, preventOverlap: true, nodeSize: 80, controlPoints: true })
  } else if (isTechStack) {
    graph.value.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: true, clustering: true, clusterNodeStrength: 0.5, strength: 0.4, coulombDisScale: 0.005, gravity: 8, maxSpeed: 200, maxIteration: 100 })
  } else {
    graph.value.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: true, strength: 0.4, coulombDisScale: 0.005, gravity: 10, maxSpeed: 200, maxIteration: 100 })
  }
  graph.value.render()
  setTimeout(() => {
    graph.value?.fitView()
    if (graph.value) {
      const finalNodes = graphNodes.map((n: any) => ({
        id: n.id,
        style: { fillOpacity: 0.85, scale: 1 },
      }))
      graph.value.updateNodeData(finalNodes)
      graph.value.draw()
    }
  }, 100)
}

// ── Layer 2: Position (KA + its positions) ──
function renderPositionLayer() {
  if (!graph.value) return
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (props.kaColorMap.get(kaId) ?? cv('--chart-3')) : cv('--chart-3')
  const positions = graphStore.positionsByKA.get(kaId ?? '') ?? []
  const maxSkillCount = Math.max(...positions.map(p => {
    let count = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') count++ }
    return count
  }), 1)

  const graphNodes: any[] = []
  const graphEdges: any[] = []

  // KA node (center, smaller)
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

  // Apply maxNodesLimit to positions
  const maxPositionNodes = Math.max(props.maxNodesLimit - 1, 5)
  const sortedPositions = [...positions].sort((a, b) => {
    let aCount = 0, bCount = 0
    for (const e of graphStore.allEdges) {
      if (e.source_id === a.id && e.type === 'REQUIRES') aCount++
      if (e.source_id === b.id && e.type === 'REQUIRES') bCount++
    }
    return bCount - aCount
  })
  const limitedPositions = sortedPositions.slice(0, maxPositionNodes)

  // Position nodes
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

    // KA → Position edge
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

  // EVOLVES_TO evolution edges
  if (props.showEvolution) {
    for (const ev of graphStore.evolutionEdges) {
      const src = limitedPositions.find(p => p.id === ev.source_id || p.properties.name === ev.source_id)
      const tgt = limitedPositions.find(p => p.id === ev.target_id || p.properties.name === ev.target_id)
      if (src && tgt) {
        graphEdges.push({
          id: `evo-${src.id}-${tgt.id}`,
          source: src.id,
          target: tgt.id,
          style: {
            stroke: cv('--destructive'),
            lineWidth: 2 + (ev.properties.weight ?? 0.5) * 3,
            opacity: 0.8,
            lineDash: [12, 6],
            endArrow: true,
            endArrowSize: 8,
          },
        })
      }
    }
  }

  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  graph.value.setLayout({ type: 'radial', unitRadius: 160, preventOverlap: true, nodeSize: 48, focusNode: kaId || undefined, animate: true })
  graph.value.render()
  setTimeout(() => graph.value?.fitView(), 300)
}

// ── Layer 3: Detail (Position + its Skills) ──
function renderDetailLayer() {
  if (!graph.value) return
  const posId = graphStore.expandedPositionId
  if (!posId) return

  const graphNodes: any[] = []
  const graphEdges: any[] = []
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (props.kaColorMap.get(kaId) ?? cv('--chart-3')) : cv('--chart-3')

  // KA node (distant, smaller)
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

  // Position node (center)
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

  // Skill nodes — apply maxNodesLimit + proficiency filter
  const allPosEdges = graphStore.visibleEdges.filter(e => e.source_id === posId)

  const hasActiveFilter = props.proficiencyFilter.length < 3
  const filteredEdges = hasActiveFilter
    ? allPosEdges.filter(e => {
        const skillNode = graphStore.nodeMap.get(e.target_id)
        if (!skillNode) return false
        const prof = skillNode.properties.proficiency || (e.properties as any)?.level || ''
        return prof ? props.proficiencyFilter.includes(prof) : true
      })
    : allPosEdges

  const maxSkillNodes = Math.max(props.maxNodesLimit - 3, 5)
  const sortedEdges = [...filteredEdges].sort((a, b) => (b.properties?.weight ?? 0.5) - (a.properties?.weight ?? 0.5))
  const posEdges = sortedEdges.slice(0, maxSkillNodes)
  const maxWeight = Math.max(...posEdges.map(e => e.properties?.weight ?? 0.5), 0.1)

  for (const e of posEdges) {
    const skillNode = graphStore.nodeMap.get(e.target_id)
    if (!skillNode) continue
    const weight = e.properties?.weight ?? 0.5
    const isRequired = weight >= 0.6
    const size = 14 + (weight / maxWeight) * 14
    const skillColor = isRequired ? NODE_TYPE_COLORS.Skill : NODE_TYPE_COLORS.Tool

    graphNodes.push({
      id: e.target_id,
      style: {
        size,
        fill: skillColor,
        fillOpacity: 0.8,
        stroke: isRequired ? cv('--success') : cv('--warning'),
        lineWidth: 1,
        labelText: skillNode.properties.name,
        labelFill: cv('--foreground'),
        labelFontSize: 10,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 4,
      },
    })

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

  graph.value.setData({ nodes: graphNodes, edges: graphEdges })
  graph.value.setLayout({ type: 'radial', unitRadius: 140, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: true })
  graph.value.render()
  setTimeout(() => graph.value?.fitView(), 300)
}

// ── Resize handler ──
function handleResize() {
  if (!graph.value || !containerRef.value) return
  graph.value.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight)
}

// ── Watch: store changes → re-render ──
watch(() => graphStore.currentLayer, () => {
  renderCurrentLayer()
})

watch(() => graphStore.overviewMode, () => {
  renderCurrentLayer()
})

// Re-render when underlying data changes (after fetchOverview/fetchKAPositions complete)
watch(() => graphStore.visibleNodes, () => {
  renderCurrentLayer()
})

// ── Watch: prop changes → re-render ──
watch(() => props.layoutMode, () => {
  renderCurrentLayer()
})

watch(() => props.showEvolution, () => {
  renderCurrentLayer()
})

watch(() => props.maxNodesLimit, () => {
  renderCurrentLayer()
})

watch(() => props.proficiencyFilter, () => {
  renderCurrentLayer()
}, { deep: true })

// ── Lifecycle ──
onMounted(async () => {
  await nextTick()
  await initGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (graph.value) { graph.value.destroy(); graph.value = null }
})
</script>

<template>
  <div
    ref="containerRef"
    class="graph-2d-canvas"
  />
</template>

<style scoped>
.graph-2d-canvas {
  width: 100%;
  height: 100%;
}
</style>
