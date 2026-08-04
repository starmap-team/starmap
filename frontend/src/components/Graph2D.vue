<script setup lang="ts">
/**
 * Graph2D — G6 v5 force-directed graph visualization (2D counterpart to Graph3D).
 *
 * Architecture (Phase 7 refactor):
 *   - useG6Lifecycle   → G6 instance init/destroy/resize (lifecycle)
 *   - useGraphAnimation → Node entrance growth animation
 *   - useGraphHighlight → Highlight + 1-hop neighbor fade
 *   - useGraph2DLayers  → Layer-specific renderers (domain/position/detail)
 *   - useGraphRenderQueue → Debounced rAF-based render dispatcher
 *
 * Data flow: props (UI state) + graphStore (domain data) → render queue → G6.
 * State changes are batched in a 16ms window to prevent render storms.
 */
import { onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useGraphStore } from '@/stores/graph'
import type { G6ElementEvent, EvolutionEdgeClickPayload } from '@/types/g6'
import { renderDomainLayer, type DomainLayerDeps, renderPositionLayer, type PositionLayerDeps, renderDetailLayer, type DetailLayerDeps } from '@/composables/useGraph2DLayers'
import { useG6Lifecycle, useGraphAnimation, useGraphHighlight, useGraphRenderQueue, useGraphLOD } from '@/composables/graph2d'

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
  edgeClick: [edgeData: EvolutionEdgeClickPayload]
}>()

// ── Store ──
const graphStore = useGraphStore()

// ── Composable wiring ──
const { graph, containerRef, init, destroy } = useG6Lifecycle()
const { animate } = useGraphAnimation()
const { highlightNode } = useGraphHighlight(
  { get value() { return graph.value } },
  () => graphStore.visibleNodes,
  () => graphStore.visibleEdges,
)
// LOD: hide labels for dense graphs to improve readability + perf
const lod = useGraphLOD({ hideLabelsAbove: 30, simplifyAbove: 100, defaultLabelsVisible: true })

// Layer deps — getter accessors avoid stale closure capture
const domainDeps: DomainLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  layoutMode: () => props.layoutMode,
  showEvolution: () => props.showEvolution,
  animateNodeGrowth: (ids) => animate(graph.value, ids),
}
const positionDeps: PositionLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  showEvolution: () => props.showEvolution,
  maxNodesLimit: () => props.maxNodesLimit,
  animateNodeGrowth: (ids) => animate(graph.value, ids),
}
const detailDeps: DetailLayerDeps = {
  graph: () => graph.value,
  kaColorMap: () => props.kaColorMap,
  maxNodesLimit: () => props.maxNodesLimit,
  proficiencyFilter: () => props.proficiencyFilter,
  showEvolution: () => props.showEvolution,
  animateNodeGrowth: (ids) => animate(graph.value, ids),
}

// Render queue with rAF batching — collapses 8+ watch triggers into 1 render
const renderQueue = useGraphRenderQueue([], 16)
renderQueue.register({
  name: 'layer-dispatch',
  priority: 10,
  fn: async (_g) => {
    // Update LOD based on current node count
    const nodeCount = graphStore.currentLayer === 'position' ? (graphStore.positionsByKA.get(graphStore.expandedKAId ?? '')?.length ?? 0) : graphStore.visibleNodes.length
    lod.setNodeCount(nodeCount)
    if (graphStore.currentLayer === 'domain') {
      renderDomainLayer(domainDeps)
    } else if (graphStore.currentLayer === 'position') {
      await renderPositionLayer(positionDeps)
    } else {
      renderDetailLayer(detailDeps)
    }
  },
})

// ── G6 event wiring ──
function onNodeClick(event: G6ElementEvent) {
  const nodeId = event.target?.id
  if (nodeId) emit('nodeClick', nodeId)
}
function onNodeDblClick(event: G6ElementEvent) {
  const nodeId = event.target?.id
  if (nodeId) emit('nodeDblClick', nodeId)
}
function onCanvasClick() { emit('canvasClick') }
function onEdgeClick(event: G6ElementEvent) {
  const edgeId = event.target?.id
  if (edgeId?.startsWith('evo-')) {
    const evEdge = graphStore.evolutionEdges.find(e => edgeId === `evo-${e.source_id}-${e.target_id}`)
    if (evEdge) emit('edgeClick', { source: evEdge.source_id, target: evEdge.target_id, type: evEdge.type, properties: evEdge.properties })
  }
}

function wireGraphEvents(): void {
  if (!graph.value) return
  graph.value.on('node:click', onNodeClick)
  graph.value.on('node:dblclick', onNodeDblClick)
  graph.value.on('canvas:click', onCanvasClick)
  graph.value.on('edge:click', onEdgeClick)
}

// ── Imperative API ──
function zoomBy(factor: number) { graph.value?.zoomBy(factor) }
function fitView() { graph.value?.fitView() }
function clearHighlightAndRerender() { renderQueue.flush(graph.value) }
defineExpose({ zoomBy, fitView, highlightNode, clearHighlight: clearHighlightAndRerender })

// ── Watchers (all funneled into render queue) ──
const watchSources = [
  () => graphStore.currentLayer,
  () => graphStore.overviewMode,
  () => graphStore.visibleNodes,
  () => graphStore.evolutionEdges,
  () => props.layoutMode,
  () => props.showEvolution,
  () => props.maxNodesLimit,
  () => props.proficiencyFilter,
] as const

watch(watchSources, () => renderQueue.schedule(graph.value), { deep: true })

// ── Lifecycle ──
onMounted(async () => {
  await nextTick()
  await init({ width: containerRef.value?.clientWidth || 800, height: containerRef.value?.clientHeight || 600 })
  wireGraphEvents()
  renderQueue.schedule(graph.value)
})

onUnmounted(() => {
  renderQueue.flush(null)
  destroy()
})
</script>

<template>
  <div
    ref="containerRef"
    class="graph-2d-canvas"
    role="application"
    aria-label="图谱可视化区域，使用滚轮缩放，拖拽平移，点击节点查看详情"
  />
</template>

<style scoped>
.graph-2d-canvas {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
}
</style>
