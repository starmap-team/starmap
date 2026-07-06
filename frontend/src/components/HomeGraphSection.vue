<script setup lang="ts">
import { ref } from 'vue'
import { Aim } from '@element-plus/icons-vue'
import Graph2D from '@/components/Graph2D.vue'
import Graph3D from '@/components/Graph3D.vue'
import GraphToolbar from '@/components/GraphToolbar.vue'
import HomeEvolutionPopup from '@/components/HomeEvolutionPopup.vue'
import type { OverviewMode } from '@/stores/graph'
import type { EvolutionEdgeDetail } from '@/components/HomeEvolutionPopup.vue'

type LayoutMode = 'force' | 'dagre' | 'radial'

defineProps<{
  viewMode: '2d' | '3d'
  layoutMode: LayoutMode
  showEvolution: boolean
  maxNodesLimit: number
  proficiencyFilter: string[]
  autoRotate3D: boolean
  loading: boolean
  visibleNodeCount: number
  /** 3D graph data — must match Graph3D's GraphNode3D / GraphLink3D interfaces */
  graph3DNodes: { id: string; labels?: string[]; color?: string; properties: { name: string; category?: string; proficiency?: string; position_count?: number; skill_count?: number; weight?: number; [key: string]: any }; x?: number; y?: number; z?: number }[]
  graph3DLinks: { source: string; target: string; type?: string; properties?: any }[]
  overviewMode: OverviewMode
  /** KA color map for 2D */
  kaColorMap: Map<string, string>
  /** Selected evolution edge for popup */
  selectedEvolutionEdge: EvolutionEdgeDetail | null
}>()

const emit = defineEmits<{
  nodeClick: [nodeId: string]
  nodeDblClick: [nodeId: string]
  canvasClick: []
  evolutionEdgeClick: [edgeData: { source: string; target: string; type: string; properties: any }]
  closeEvolutionDetail: []
  toggleLayout: []
  resetHighlight: []
  maxNodesChange: [value: number]
  proficiencyFilter: [levels: string[]]
  cameraPreset: [preset: 'overview' | 'domain' | 'position']
  resetCamera: []
  toggleAutoRotate: []
  zoomBy: [factor: number]
  fitView: []
  highlightNode: [nodeId: string]
  clearHighlight: []
}>()

// ── Template refs ──
const graph2DRef = ref<InstanceType<typeof Graph2D> | null>(null)
const graph3DRef = ref<InstanceType<typeof Graph3D> | null>(null)

// ── Toolbar event delegation ──
function onZoomIn() { graph2DRef.value?.zoomBy(1.2) }
function onZoomOut() { graph2DRef.value?.zoomBy(0.8) }
function onZoomFit() { graph2DRef.value?.fitView() }
function onResetHighlight() { graph2DRef.value?.clearHighlight() }
function onCameraPreset(preset: 'overview' | 'domain' | 'position') { graph3DRef.value?.setCameraPreset(preset) }
function onResetCamera() { graph3DRef.value?.resetCamera() }
function onToggleAutoRotate() {
  graph3DRef.value?.toggleAutoRotate()
  emit('toggleAutoRotate')
}

// ── Expose methods for parent (e.g. highlightNode, clearHighlight) ──
function highlightNode(nodeId: string) { graph2DRef.value?.highlightNode(nodeId) }
function clearHighlight() { graph2DRef.value?.clearHighlight() }

defineExpose({ highlightNode, clearHighlight })
</script>

<template>
  <div class="graph-layout">
    <main class="graph-main">
      <div
        v-loading="loading"
        class="graph-container grain"
      >
        <Graph2D
          v-if="viewMode === '2d'"
          ref="graph2DRef"
          :layout-mode="layoutMode"
          :ka-color-map="kaColorMap"
          :show-evolution="showEvolution"
          :max-nodes-limit="maxNodesLimit"
          :proficiency-filter="proficiencyFilter"
          @node-click="(id: string) => emit('nodeClick', id)"
          @node-dbl-click="(id: string) => emit('nodeDblClick', id)"
          @canvas-click="() => emit('canvasClick')"
          @edge-click="(data: any) => emit('evolutionEdgeClick', data)"
        />
        <Graph3D
          v-if="viewMode === '3d'"
          ref="graph3DRef"
          :nodes="graph3DNodes"
          :links="graph3DLinks"
          :overview-mode="overviewMode"
          @node-click="(id: string) => emit('nodeClick', id)"
          @node-dbl-click="(id: string) => emit('nodeDblClick', id)"
        />
        <div
          v-if="!loading && visibleNodeCount === 0"
          class="empty-hint"
        >
          <el-icon
            size="40"
            color="var(--muted-foreground)"
          >
            <Aim />
          </el-icon>
          <p class="empty-text">
            图谱数据为空
          </p>
          <p class="empty-hint-text">
            请确认后端服务已启动并有数据接入
          </p>
        </div>
        <GraphToolbar
          :node-count="visibleNodeCount"
          :layout-mode="layoutMode"
          :is3-d="viewMode === '3d'"
          :auto-rotate="autoRotate3D"
          :max-nodes="maxNodesLimit"
          :selected-proficiencies="proficiencyFilter"
          @zoom-in="onZoomIn"
          @zoom-out="onZoomOut"
          @zoom-fit="onZoomFit"
          @toggle-layout="() => emit('toggleLayout')"
          @reset-highlight="onResetHighlight"
          @max-nodes-change="(val: number) => emit('maxNodesChange', val)"
          @proficiency-filter="(levels: string[]) => emit('proficiencyFilter', levels)"
          @camera-preset="onCameraPreset"
          @reset-camera="onResetCamera"
          @toggle-auto-rotate="onToggleAutoRotate"
        />

        <!-- Evolution Edge Detail Popup (inside graph-container for relative positioning) -->
        <HomeEvolutionPopup
          :edge="selectedEvolutionEdge"
          @close="() => emit('closeEvolutionDetail')"
        />
      </div>
    </main>
    <slot />
  </div>
</template>

<style scoped>
/* ── Graph Layout ── */
.graph-layout { display: flex; gap: var(--space-4); flex: 1; min-height: 0; perspective: 1200px; }
.graph-main { flex: 1; min-width: 0; }
.graph-container { position: relative; background: var(--card); transform: rotateX(1deg); transform-origin: center bottom; border: 1px solid var(--border); border-radius: var(--radius-2xl); overflow: hidden; height: 100%; min-height: 520px; box-shadow: var(--shadow-md); perspective: 1200px; }
.graph-container::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at center, transparent 50%, color-mix(in srgb, var(--background) 30%, transparent) 100%); pointer-events: none; z-index: 2; border-radius: inherit; }
.graph-container::after { content: ''; position: absolute; inset: 0; background-image: radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--border) 50%, transparent) 1px, transparent 0); background-size: 32px 32px; opacity: 0.3; pointer-events: none; z-index: 0; }
.empty-hint { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2); color: var(--muted-foreground); font-size: var(--font-size-sm); }

/* ── Responsive ── */
@media (max-width: 768px) {
  .graph-layout { flex-direction: column; }
  .graph-container { min-height: 360px; }
}
</style>
