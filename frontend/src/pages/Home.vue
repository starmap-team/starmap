<script setup lang="ts">
import { onMounted } from "vue"
import { Collection, DataAnalysis, Upload, Document, TrendCharts, Aim, Connection } from "@element-plus/icons-vue"
import { use } from "echarts/core"
import { RadarChart } from "echarts/charts"
import { TooltipComponent, LegendComponent, RadarComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])
import MainLayout from "@/layouts/MainLayout.vue"
import GraphToolbar from "@/components/GraphToolbar.vue"
import Graph2D from "@/components/Graph2D.vue"
import Graph3D from "@/components/Graph3D.vue"
import DetailPanel from "@/components/DetailPanel.vue"
import GraphSearchBar from "@/components/GraphSearchBar.vue"
import { useGraphStore } from "@/stores/graph"
import { useKPIMetrics } from "@/composables/useKPIMetrics"
import {
  useGraphToolbarState,
  useHomeLayout,
  useEvolutionPanel,
  useNodeSelection,
  useHomeInteractions,
} from "@/composables/home"

const graphStore = useGraphStore()
const { totalPositions, totalSkills, totalDomains, totalRelations } = useKPIMetrics()
const { layoutMode, maxNodesLimit, proficiencyFilter, toggleLayout, onMaxNodesChange, onProficiencyFilter } = useGraphToolbarState()
const { viewMode, autoRotate3D } = useHomeLayout()
const { showEvolution, graph3DEvolutionLinks } = useEvolutionPanel()
const { selectedNode, clearSelection } = useNodeSelection()
const interactions = useHomeInteractions(() => graphStore)

// Re-export bindings the <template> references under stable names.
const { graph2DRef, graph3DRef, evolutionDrawerVisible, selectedEvolutionEdge,
  evolutionTrendLabel, evolutionTrendType, breadcrumb, positionRadarOption,
  onOverviewModeChange, onCameraPreset, onResetCamera, onNodeDblClick,
  resetHighlight, toggleEvolution, closeDetail, handleNodeClick,
  onCanvasClick, handleSearchSelect, openEvolutionDrawer, closeEvolutionDrawer } = interactions

const onToggleAutoRotate = () => interactions.onToggleAutoRotate(autoRotate3D)
const onToggleEvolution = () => toggleEvolution(showEvolution, selectedNode)
const onCloseDetail = () => closeDetail(clearSelection)
const onCanvasClickWithClear = () => onCanvasClick(clearSelection)
const onHandleNodeClick = async (id: string) => handleNodeClick(id, selectedNode)
const onHandleSearchSelect = (id: string, name: string, type: string) =>
  handleSearchSelect(id, name, type, selectedNode)

onMounted(async () => {
  await graphStore.fetchOverview()
})
</script>

<template>
  <MainLayout>
    <div class="graph-page animate-fade-in">
      <!-- ── KPI Strip ── -->
      <div class="kpi-strip stagger">
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon--info">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-label">技术领域</span>
            <span class="kpi-value">{{ totalDomains }}</span>
            <span class="kpi-trend">知识图谱核心分类</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon--primary">
            <el-icon><Collection /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-label">岗位数</span>
            <span class="kpi-value">{{ totalPositions }}</span>
            <span class="kpi-trend">IT 行业全覆盖</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon--success">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-label">技能数</span>
            <span class="kpi-value">{{ totalSkills }}</span>
            <span class="kpi-trend">持续增长中</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon--warning">
            <el-icon><Connection /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-label">关系数</span>
            <span class="kpi-value">{{ totalRelations }}</span>
            <span class="kpi-trend">知识关联网络</span>
          </div>
        </div>
        <div class="kpi-actions">
          <el-button
            size="small"
            :icon="Upload"
            @click="$router.push('/match')"
          >
            简历匹配
          </el-button>
          <el-button
            size="small"
            :icon="Document"
            @click="$router.push('/extract')"
          >
            JD 抽取
          </el-button>
          <el-button
            size="small"
            :icon="TrendCharts"
            @click="$router.push('/evolution')"
          >
            演化趋势
          </el-button>
        </div>
      </div>

      <!-- ── Graph Controls Bar ── -->
      <div class="graph-controls">
        <div class="controls-left">
          <nav class="graph-breadcrumb">
            <template
              v-for="(item, i) in breadcrumb"
              :key="i"
            >
              <span
                class="gb-item"
                :class="{ active: i === breadcrumb.length - 1 }"
                @click="i < breadcrumb.length - 1 && item.action?.()"
              >{{ item.label }}</span>
              <span
                v-if="i < breadcrumb.length - 1"
                class="gb-sep"
              >></span>
            </template>
          </nav>
          <el-radio-group
            v-if="graphStore.currentLayer === 'domain'"
            :model-value="graphStore.overviewMode"
            size="small"
            class="view-tabs"
            @change="onOverviewModeChange"
          >
            <el-radio-button value="domain">
              领域
            </el-radio-button>
            <el-radio-button value="tech_stack">
              技术栈
            </el-radio-button>
            <el-radio-button value="level">
              级别
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="controls-right">
          <div class="view-mode-toggle">
            <button
              class="vm-btn"
              :class="{ 'vm-btn--active': viewMode === '2d' }"
              @click="viewMode = '2d'"
            >
              2D
            </button>
            <button
              class="vm-btn"
              :class="{ 'vm-btn--active': viewMode === '3d' }"
              @click="viewMode = '3d'"
            >
              3D
            </button>
            <span
              class="vm-indicator"
              :class="{ 'vm-indicator--3d': viewMode === '3d' }"
            />
          </div>
          <div class="graph-legend">
            <span class="legend-item"><span class="ld-dot ld-dot--domain" />领域</span>
            <span class="legend-item"><span class="ld-dot ld-dot--position" />岗位</span>
            <span class="legend-item"><span class="ld-dot ld-dot--skill" />技能</span>
            <span
              v-if="showEvolution"
              class="legend-item"
            ><span class="ld-line" />演化</span>
          </div>
          <el-button
            size="small"
            :type="showEvolution ? 'primary' : 'default'"
            text
            @click="toggleEvolution"
          >
            {{ showEvolution ? '隐藏演化' : '显示演化' }}
          </el-button>
        </div>
      </div>

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
              @node-click="handleNodeClick"
              @node-dbl-click="onNodeDblClick"
              @canvas-click="onCanvasClick"
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
              @node-click="handleNodeClick"
              @node-dbl-click="onNodeDblClick"
              @evolution-edge-click="openEvolutionDrawer"
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
          @close="closeDetail"
          @navigate-to-detail="(n) => selectedNode = n"
        />
      </div>

      <GraphSearchBar @node-selected="handleSearchSelect" />

      <!-- 演化详情抽屉 (D-11/D-12) -->
      <el-drawer
        v-model="evolutionDrawerVisible"
        title="演化路径详情"
        size="420px"
        direction="rtl"
        @close="closeEvolutionDrawer"
      >
        <div
          v-if="selectedEvolutionEdge"
          class="evo-drawer-body"
        >
          <div class="evo-title-row">
            <span class="evo-pos">{{ selectedEvolutionEdge.source_id }}</span>
            <el-icon
              :size="20"
              color="var(--primary)"
            >
              <Connection />
            </el-icon>
            <span class="evo-pos">{{ selectedEvolutionEdge.target_id }}</span>
          </div>
          <el-tag
            :type="(evolutionTrendType[selectedEvolutionEdge.properties?.trend ?? 'stable'] ?? 'info') as any"
            effect="plain"
            size="default"
          >
            {{ evolutionTrendLabel[selectedEvolutionEdge.properties?.trend ?? 'stable'] ?? selectedEvolutionEdge.properties?.trend }}
          </el-tag>
          <el-descriptions
            :column="1"
            border
            class="evo-desc"
          >
            <el-descriptions-item label="相似度">
              {{ ((selectedEvolutionEdge.properties?.similarity ?? 0) * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="证据数">
              {{ selectedEvolutionEdge.properties?.evidence_count ?? 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="信任度">
              {{ ((selectedEvolutionEdge.properties?.similarity ?? 0) * 100).toFixed(0) }}%
            </el-descriptions-item>
          </el-descriptions>
          <div
            v-if="selectedEvolutionEdge.properties?.skill_overlap?.length"
            class="evo-section"
          >
            <div class="evo-section-title">
              技能重叠 ({{ selectedEvolutionEdge.properties.skill_overlap.length }})
            </div>
            <div class="evo-tags">
              <el-tag
                v-for="s in selectedEvolutionEdge.properties.skill_overlap"
                :key="s"
                size="small"
                effect="plain"
                type="success"
              >
                {{ s }}
              </el-tag>
            </div>
          </div>
          <div
            v-if="selectedEvolutionEdge.properties?.key_gaps?.length"
            class="evo-section"
          >
            <div class="evo-section-title">
              关键差距 ({{ selectedEvolutionEdge.properties.key_gaps.length }})
            </div>
            <div class="evo-tags">
              <el-tag
                v-for="g in selectedEvolutionEdge.properties.key_gaps"
                :key="g"
                size="small"
                effect="plain"
                type="danger"
              >
                {{ g }}
              </el-tag>
            </div>
          </div>
        </div>
        <div
          v-else
          class="evo-empty"
        >
          未选中演化边
        </div>
      </el-drawer>
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

/* ── KPI Strip ── */
.kpi-strip { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.kpi-card { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-5); background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-xl); min-width: 140px; transition: all var(--duration-normal) var(--ease-out); position: relative; overflow: hidden; }
.kpi-card::before { content: ''; position: absolute; inset: 0; opacity: 0; background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent); transition: opacity var(--duration-normal); }
.kpi-card:hover { border-color: color-mix(in srgb, var(--primary) 20%, var(--border)); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.kpi-card:hover::before { opacity: 1; }
.kpi-icon { width: 38px; height: 38px; border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: var(--font-size-xl); position: relative; z-index: 1; }
.kpi-body { display: flex; flex-direction: column; position: relative; z-index: 1; }
.kpi-value { font-size: var(--font-size-2xl); font-weight: 800; color: var(--foreground); line-height: 1.1; letter-spacing: var(--tracking-tight); font-variant-numeric: tabular-nums; }
.kpi-label { font-size: 10px; color: var(--muted-foreground); letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }
.kpi-trend { font-size: var(--font-size-xs); color: var(--muted-foreground); margin-top: 1px; opacity: 0.7; }
.kpi-actions { display: flex; gap: var(--space-2); margin-left: auto; }
.kpi-icon--info { background: var(--info-ghost); color: var(--info); }
.kpi-icon--primary { background: var(--primary-ghost); color: var(--primary); }
.kpi-icon--success { background: var(--success-ghost); color: var(--success); }
.kpi-icon--warning { background: var(--warning-ghost); color: var(--warning); }

/* ── Graph Controls Bar ── */
.graph-controls { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3); padding: var(--space-2) var(--space-1); background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-xl); padding: var(--space-2) var(--space-4); box-shadow: var(--shadow-xs); }
.controls-left { display: flex; align-items: center; gap: var(--space-4); }
.controls-right { display: flex; align-items: center; gap: var(--space-3); }
.graph-breadcrumb { display: flex; align-items: center; gap: var(--space-1-5); font-size: var(--font-size-sm); }
.gb-item { color: var(--muted-foreground); cursor: pointer; padding: 3px 8px; border-radius: var(--radius-sm); transition: all var(--duration-fast); font-weight: 500; }
.gb-item:hover:not(.active) { color: var(--primary); background: var(--primary-ghost); }
.gb-item.active { color: var(--foreground); font-weight: 600; cursor: default; }
.gb-sep { color: var(--border); font-size: var(--font-size-xs); margin: 0 2px; }
.view-tabs { --el-radio-button-checked-bg-color: var(--primary); --el-radio-button-checked-border-color: var(--primary); }
.view-tabs .el-radio-button__inner { font-size: var(--font-size-xs); font-weight: 500; letter-spacing: 0.02em; padding: 6px 14px; transition: all var(--duration-normal) var(--ease-out); }

/* ── 2D / 3D View Mode Toggle ── */
.view-mode-toggle { display: flex; align-items: center; position: relative; background: color-mix(in srgb, var(--muted-foreground) 8%, transparent); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 2px; }
.vm-btn { position: relative; z-index: 2; padding: 4px 14px; border: none; background: none; color: var(--muted-foreground); font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.04em; cursor: pointer; border-radius: var(--radius-md); transition: color var(--duration-fast) var(--ease-out); }
.vm-btn--active { color: var(--primary-foreground); }
.vm-indicator { position: absolute; top: 2px; left: 2px; width: calc(50% - 2px); height: calc(100% - 4px); background: var(--primary); border-radius: var(--radius-md); transition: transform var(--duration-normal) var(--ease-out); z-index: 1; box-shadow: 0 1px 4px color-mix(in srgb, var(--primary) 40%, transparent); }
.vm-indicator--3d { transform: translateX(100%); }
.graph-legend { display: flex; align-items: center; gap: var(--space-3); font-size: var(--font-size-xs); color: var(--muted-foreground); }
.legend-item { display: flex; align-items: center; gap: var(--space-1); }
.ld-dot { width: 8px; height: 8px; border-radius: 50%; }
.ld-line { width: 16px; height: 0; border-top: 2px dashed var(--destructive); }
.ld-dot--domain { background: var(--chart-3); }
.ld-dot--position { background: var(--chart-1); }
.ld-dot--skill { background: var(--success); }

/* ── Graph Layout ── */
.graph-layout { display: flex; gap: var(--space-4); flex: 1; min-height: 0; perspective: 1200px; }
.graph-main { flex: 1; min-width: 0; }
.graph-container { position: relative; background: var(--card); transform: rotateX(1deg); transform-origin: center bottom; border: 1px solid var(--border); border-radius: var(--radius-2xl); overflow: hidden; height: 100%; min-height: 520px; box-shadow: var(--shadow-md); perspective: 1200px; }
.graph-container::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at center, transparent 50%, color-mix(in srgb, var(--background) 30%, transparent) 100%); pointer-events: none; z-index: 2; border-radius: inherit; }
.graph-container::after { content: ''; position: absolute; inset: 0; background-image: radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--border) 50%, transparent) 1px, transparent 0); background-size: 32px 32px; opacity: 0.3; pointer-events: none; z-index: 0; }
.empty-hint { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2); color: var(--muted-foreground); font-size: var(--font-size-sm); }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .kpi-actions { margin-left: 0; width: 100%; }
}
@media (max-width: 768px) {
  .graph-layout { flex-direction: column; }
  .kpi-strip { flex-direction: column; align-items: stretch; }
  .kpi-actions { flex-direction: column; }
  .controls-left, .controls-right { flex-wrap: wrap; }
  .graph-container { min-height: 360px; }
}

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

/* ── Evolution Drawer ── */
.evo-drawer-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}
.evo-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
}
.evo-pos {
  padding: 6px 14px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  letter-spacing: var(--tracking-tight);
}
.evo-desc { margin-top: var(--space-2); }
.evo-section { display: flex; flex-direction: column; gap: var(--space-2); }
.evo-section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.evo-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.evo-empty {
  padding: var(--space-10);
  text-align: center;
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}
</style>
