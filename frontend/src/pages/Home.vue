<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { Aim, TrendCharts } from "@element-plus/icons-vue"
import { use } from "echarts/core"
import { RadarChart } from "echarts/charts"
import { TooltipComponent, LegendComponent, RadarComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])
import MainLayout from "@/layouts/MainLayout.vue"
import Graph2D from "@/components/Graph2D.vue"
import Graph3D from "@/components/Graph3D.vue"
import DetailPanel from "@/components/DetailPanel.vue"
import GraphSearchBar from "@/components/GraphSearchBar.vue"
import GraphToolbar from "@/components/GraphToolbar.vue"
import HomeKpiStrip from "@/components/HomeKpiStrip.vue"
import HomeGraphControls from "@/components/HomeGraphControls.vue"
import HomeEvolutionDrawer from "@/components/HomeEvolutionDrawer.vue"
import { useGraphStore } from "@/stores/graph"
import { useKPIMetrics } from "@/composables/useKPIMetrics"
import {
  useGraphToolbarState,
  useHomeLayout,
  useEvolutionPanel,
  useNodeSelection,
  useHomeInteractions,
  useGraph2DData,
  useGraph3DData,
} from "@/composables/home"

const router = useRouter()
const graphStore = useGraphStore()
const { totalPositions, totalSkills, totalDomains, totalRelations } = useKPIMetrics()
const { layoutMode, maxNodesLimit, proficiencyFilter, toggleLayout, onMaxNodesChange, onProficiencyFilter } = useGraphToolbarState()
const { viewMode, autoRotate3D } = useHomeLayout()
const { showEvolution, graph3DEvolutionLinks } = useEvolutionPanel()
const { selectedNode, clearSelection } = useNodeSelection()
const { kaColorMap } = useGraph2DData()
const { graph3DNodes, graph3DLinks } = useGraph3DData()
const interactions = useHomeInteractions(() => graphStore)
const evolutionDrawer = ref<InstanceType<typeof HomeEvolutionDrawer>>()

// Re-export bindings the <template> references under stable names.
const { graph2DRef, graph3DRef, breadcrumb, positionRadarOption,
  onOverviewModeChange, onCameraPreset, onResetCamera, onNodeDblClick,
  resetHighlight, toggleEvolution, closeDetail, handleNodeClick,
  onCanvasClick, handleSearchSelect } = interactions

const onToggleAutoRotate = () => interactions.onToggleAutoRotate(autoRotate3D)
const onToggleEvolution = () => toggleEvolution(showEvolution, selectedNode)
const onCloseDetail = () => closeDetail(clearSelection)
const onCanvasClickWithClear = () => onCanvasClick(clearSelection)
const onHandleNodeClick = async (id: string) => handleNodeClick(id, selectedNode)
const onHandleSearchSelect = (id: string, name: string, type: string) =>
  handleSearchSelect(id, name, type, selectedNode)
const onOpenEvolutionDrawer = (edge: any) => evolutionDrawer.value?.open(edge)
const onNavigate = (path: string) => router.push(path)

onMounted(async () => {
  await graphStore.fetchOverview()
})
</script>

<template>
  <MainLayout>
    <div class="graph-page animate-fade-in">
      <!-- ── KPI Strip ── -->
      <HomeKpiStrip
        :total-domains="totalDomains"
        :total-positions="totalPositions"
        :total-skills="totalSkills"
        :total-relations="totalRelations"
        @navigate="onNavigate"
      />

      <!-- ── Graph Controls Bar ── -->
      <HomeGraphControls
        :breadcrumb="breadcrumb"
        :view-mode="viewMode"
        :show-evolution="showEvolution"
        :show-overview-radio="graphStore.currentLayer === 'domain'"
        :overview-mode="graphStore.overviewMode"
        :current-layer="graphStore.currentLayer"
        @set-view-mode="(m: '2d' | '3d') => viewMode = m"
        @toggle-evolution="onToggleEvolution"
        @overview-mode-change="onOverviewModeChange"
      />

      <!-- ── Graph Main Area ── -->
      <div class="graph-layout">
        <main class="graph-main">
          <div
            v-loading="graphStore.loading"
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
              @node-click="onHandleNodeClick"
              @node-dbl-click="onNodeDblClick"
              @canvas-click="onCanvasClickWithClear"
            />
            <Graph3D
              v-if="viewMode === '3d'"
              ref="graph3DRef"
              :nodes="graph3DNodes"
              :links="graph3DLinks"
              :current-layer="graphStore.currentLayer"
              :show-evolution="showEvolution"
              :evolution-paths="graph3DEvolutionLinks"
              :current-domain-id="graphStore.expandedKAId"
              @node-click="onHandleNodeClick"
              @node-dbl-click="onNodeDblClick"
              @evolution-edge-click="onOpenEvolutionDrawer"
            />
            <div
              v-if="showEvolution && viewMode === '3d' && graphStore.currentLayer === 'position' && !graphStore.focusedPositionName"
              class="evolution-hint"
            >
              <el-icon :size="18">
                <TrendCharts />
              </el-icon>
              <span>点击岗位查看演化路径</span>
            </div>
            <div
              v-if="!graphStore.loading && graphStore.visibleNodes.length === 0"
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
              @reset-highlight="resetHighlight"
              @max-nodes-change="onMaxNodesChange"
              @proficiency-filter="onProficiencyFilter"
              @camera-preset="onCameraPreset"
              @reset-camera="onResetCamera"
              @toggle-auto-rotate="onToggleAutoRotate"
            />
          </div>
        </main>
        <DetailPanel
          :selected-node="selectedNode"
          :position-radar-option="positionRadarOption"
          @close="onCloseDetail"
          @navigate-to-detail="(n) => selectedNode = n"
        />
      </div>

      <GraphSearchBar @node-selected="onHandleSearchSelect" />

      <!-- 演化详情抽屉 -->
      <HomeEvolutionDrawer ref="evolutionDrawer" />
    </div>
  </MainLayout>
</template>

<style scoped>
/* ── Page Container ── */
.graph-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-height: calc(100vh - 180px);
}

/* ── Graph Layout ── */
.graph-layout { display: flex; gap: var(--space-4); flex: 1; min-height: 0; perspective: 1200px; }
.graph-main { flex: 1; min-width: 0; }
.graph-container { position: relative; background: var(--card); transform: rotateX(1deg); transform-origin: center bottom; border: 1px solid var(--border); border-radius: var(--radius-2xl); overflow: hidden; height: 100%; min-height: 520px; box-shadow: var(--shadow-md); perspective: 1200px; }
.graph-container::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at center, transparent 50%, color-mix(in srgb, var(--background) 30%, transparent) 100%); pointer-events: none; z-index: 2; border-radius: inherit; }
.graph-container::after { content: ''; position: absolute; inset: 0; background-image: radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--border) 50%, transparent) 1px, transparent 0); background-size: 32px 32px; opacity: 0.3; pointer-events: none; z-index: 0; }
.empty-hint { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2); color: var(--muted-foreground); font-size: var(--font-size-sm); }

/* ── Evolution Layer Hint ── */
.evolution-hint {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: color-mix(in srgb, var(--primary) 12%, rgba(10, 14, 26, 0.85));
  border: 1px solid color-mix(in srgb, var(--primary) 40%, transparent);
  border-radius: var(--radius-full);
  color: var(--primary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  z-index: 20;
  pointer-events: none;
  backdrop-filter: blur(8px);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .graph-layout { flex-direction: column; }
  .graph-container { min-height: 360px; }
}
</style>
