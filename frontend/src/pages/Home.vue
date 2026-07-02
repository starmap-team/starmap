<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
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
import { useGraphStore, type GraphNode, type ViewLayer, type OverviewMode } from "@/stores/graph"
import { tooltipStyle } from "@/utils/chartTheme"
import { NODE_TYPE_COLORS, KA_FALLBACK_COLORS } from "@/utils/graphColors"
import { useKPIMetrics } from "@/composables/useKPIMetrics"

const graphStore = useGraphStore()
const { totalPositions, totalSkills, totalDomains, totalRelations } = useKPIMetrics()

// ── CSS variable resolver (for ECharts radar — Canvas/WebGL uses Graph2D's own cv) ──
const _cvCache = new Map<string, string>()
function cv(name: string): string {
  let value = _cvCache.get(name)
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    _cvCache.set(name, value)
  }
  return value
}

// ── Template refs ──
const graph2DRef = ref<InstanceType<typeof Graph2D> | null>(null)
const graph3DRef = ref<InstanceType<typeof Graph3D> | null>(null)

// ── KA color map (built from store domains + fallback palette) ──
const kaColorMap = computed(() => {
  const map = new Map<string, string>()
  graphStore.domains.forEach((d, i) => {
    map.set(d.id, d.color || KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length])
  })
  return map
})

// ── UI state (page-level) ──
type LayoutMode = 'force' | 'dagre' | 'radial'
type ViewMode = '2d' | '3d'
const layoutMode = ref<LayoutMode>('force')
const viewMode = ref<ViewMode>('3d')
const autoRotate3D = ref(false)
const showEvolution = ref(false)
const maxNodesLimit = ref(80)
const proficiencyFilter = ref<string[]>(['精通', '熟悉', '了解'])
const selectedNode = ref<GraphNode | null>(null)

// ── 3D data with precomputed colors ──
const graph3DNodes = computed(() =>
  graphStore.visibleNodes.map(n => {
    const props = n.properties as Record<string, any>
    let color = NODE_TYPE_COLORS[n.labels[0]] ?? '#64748b'
    if (n.labels[0] === 'KnowledgeArea') {
      color = kaColorMap.value.get(n.id) ?? KA_FALLBACK_COLORS[0]
    }
    return {
      id: n.id,
      labels: n.labels,
      color,
      properties: {
        name: props.name,
        category: props.category,
        proficiency: props.proficiency,
        position_count: props.position_count,
        skill_count: props.skill_count,
        weight: props.weight,
      },
    }
  })
)

const graph3DLinks = computed(() =>
  graphStore.visibleEdges.map(e => ({
    source: e.source_id,
    target: e.target_id,
    type: e.type,
    properties: e.properties,
  }))
)

// ── Breadcrumb ──
interface BreadcrumbItem {
  label: string
  layer: ViewLayer
  action?: () => void
}
const breadcrumb = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = [{ label: "领域概览", layer: "domain", action: () => graphStore.goToDomainLayer() }]
  if (graphStore.expandedKAName) {
    items.push({ label: graphStore.expandedKAName, layer: "position", action: () => { graphStore.expandedPositionId = null; graphStore.currentLayer = "position" } })
  }
  if (graphStore.expandedPositionId) {
    const posNode = graphStore.nodeMap.get(graphStore.expandedPositionId)
    items.push({ label: posNode?.properties.name ?? "岗位", layer: "detail" })
  }
  return items
})

// ── Overview mode / layout / view mode ──
function onOverviewModeChange(mode: string) {
  graphStore.fetchOverview(mode as OverviewMode)
}

function toggleLayout() {
  layoutMode.value = layoutMode.value === 'force' ? 'dagre' : layoutMode.value === 'dagre' ? 'radial' : 'force'
}

// ── 3D camera controls ──
function onCameraPreset(preset: 'overview' | 'domain' | 'position') {
  graph3DRef.value?.setCameraPreset(preset)
}
function onResetCamera() {
  graph3DRef.value?.resetCamera()
}
function onToggleAutoRotate() {
  graph3DRef.value?.toggleAutoRotate()
  autoRotate3D.value = !autoRotate3D.value
}

// ── Node click / dblclick (shared by 2D + 3D — both emit nodeId: string) ──
function onNodeDblClick(nodeId: string) {
  const n = graphStore.nodeMap.get(nodeId)
  if (!n) return
  const label = n.labels[0]
  if (label === 'KnowledgeArea') {
    graphStore.goToPositionLayer(n.id, n.properties.name)
  } else if (label === 'Position') {
    graphStore.goToDetailLayer(n.id)
  }
}

// ── Filters (Graph2D watches these props) ──
function onMaxNodesChange(val: number) {
  maxNodesLimit.value = val
}
function onProficiencyFilter(levels: string[]) {
  proficiencyFilter.value = levels
}
function resetHighlight() {
  graph2DRef.value?.clearHighlight()
}

// ── Evolution toggle ──
function toggleEvolution() {
  showEvolution.value = !showEvolution.value
  if (showEvolution.value && graphStore.evolutionEdges.length === 0) graphStore.fetchEvolutionEdges()
}

function closeDetail() {
  selectedNode.value = null
  graph2DRef.value?.clearHighlight()
}

// ── Node click handler (shared by 2D + 3D) ──
async function handleNodeClick(nodeId: string) {
  if (graphStore.currentLayer === "domain") {
    const domain = graphStore.domains.find(d => d.id === nodeId)
    if (domain) {
      selectedNode.value = {
        id: domain.id,
        labels: ["KnowledgeArea"],
        properties: { name: domain.name, position_count: domain.position_count, skill_count: domain.skill_count },
      }
      await graphStore.goToPositionLayer(domain.id, domain.name)
    }
    return
  }
  if (graphStore.currentLayer === "position") {
    if (nodeId === graphStore.expandedKAId) {
      const domain = graphStore.domains.find(d => d.id === nodeId)
      selectedNode.value = domain ? {
        id: domain.id,
        labels: ["KnowledgeArea"],
        properties: { name: domain.name, position_count: domain.position_count, skill_count: domain.skill_count },
      } : null
      return
    }
    const node = graphStore.nodeMap.get(nodeId)
    if (node?.labels.includes("Position")) {
      selectedNode.value = node
      graphStore.goToDetailLayer(nodeId)
    }
    return
  }
  // Detail layer
  const node = graphStore.nodeMap.get(nodeId)
  if (node) selectedNode.value = node
  graph2DRef.value?.highlightNode(nodeId)
}

function onCanvasClick() {
  selectedNode.value = null
  graph2DRef.value?.clearHighlight()
}

// ── Search ──
function handleSearchSelect(id: string, _name: string, _type: string) {
  const domain = graphStore.domains.find(d => d.id === id)
  if (domain) {
    graphStore.goToPositionLayer(domain.id, domain.name)
    return
  }
  const node = graphStore.allNodes.find(n => n.id === id)
  if (node?.labels.includes("Position")) {
    const kaId = findKAForPosition(node.id)
    if (kaId) {
      const ka = graphStore.domains.find(d => d.id === kaId)
      graphStore.goToPositionLayer(kaId, ka?.name ?? "").then(() => {
        graphStore.goToDetailLayer(node.id)
        selectedNode.value = node
      })
    }
    return
  }
  if (node?.labels.includes("Skill")) {
    for (const e of graphStore.allEdges) {
      if (e.target_id === id && e.type === "REQUIRES") {
        const posNode = graphStore.nodeMap.get(e.source_id)
        if (posNode) {
          const kaId = findKAForPosition(posNode.id)
          if (kaId) {
            const ka = graphStore.domains.find(d => d.id === kaId)
            graphStore.goToPositionLayer(kaId, ka?.name ?? "").then(() => {
              graphStore.goToDetailLayer(posNode.id)
              selectedNode.value = node
            })
          }
          return
        }
      }
    }
  }
}

function findKAForPosition(positionId: string): string | null {
  for (const [kaId, positions] of graphStore.positionsByKA) {
    if (positions.some(p => p.id === positionId)) return kaId
  }
  return null
}

// ── Radar chart ──
const positionRadarOption = computed(() => {
  if (!selectedNode.value || !selectedNode.value.labels.includes("Position")) return null
  const posId = selectedNode.value.id
  const skills: { name: string; value: number }[] = []
  for (const e of graphStore.allEdges) {
    if (e.source_id === posId && e.type === "REQUIRES") {
      const skillNode = graphStore.nodeMap.get(e.target_id)
      if (!skillNode) continue
      skills.push({ name: skillNode.properties.name, value: Math.min(e.properties?.weight ?? 0.5, 1) })
    }
  }
  if (!skills.length) return null
  const sliced = skills.slice(0, 8)
  return {
    tooltip: { ...tooltipStyle(), trigger: "item" },
    radar: {
      center: ["50%", "50%"],
      radius: "60%",
      indicator: sliced.map(s => ({ name: s.name, max: 1 })),
      axisName: { color: cv("--muted-foreground"), fontSize: 10, fontFamily: `'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Noto Sans SC', sans-serif` },
    },
    series: [{
      type: "radar",
      data: [{
        value: sliced.map(s => s.value),
        name: "技能权重",
        areaStyle: { color: `color-mix(in srgb, ${cv("--primary")} 15%, transparent)` },
        lineStyle: { color: cv("--primary"), width: 2 },
        itemStyle: { color: cv("--primary") },
      }],
    }],
  }
})

// ── Lifecycle ──
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
              @node-click="handleNodeClick"
              @node-dbl-click="onNodeDblClick"
            />
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
</style>
