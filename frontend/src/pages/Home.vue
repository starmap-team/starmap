<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from "vue"
import { ElMessage } from 'element-plus'
// G6 loaded dynamically below for code-splitting
import { Collection, DataAnalysis, Upload, Document, TrendCharts, Aim } from "@element-plus/icons-vue"
import { use } from "echarts/core"
import { RadarChart } from "echarts/charts"
import { TooltipComponent, LegendComponent, RadarComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])
import request from "@/api/request"
import MainLayout from "@/layouts/MainLayout.vue"
import GraphToolbar from "@/components/GraphToolbar.vue"
import Graph3D from "@/components/Graph3D.vue"
import DetailPanel from "@/components/DetailPanel.vue"
import GraphSearchBar from "@/components/GraphSearchBar.vue"
import { useGraphStore, type GraphNode, type ViewLayer, type OverviewMode } from "@/stores/graph"
import { chartColors, tooltipStyle } from "@/utils/chartTheme"
import { loadG6Graph, cv } from "@/composables/useG6Graph"
import { useGraphColors } from "@/composables/useGraphColors"
import { useKPIMetrics } from "@/composables/useKPIMetrics"

// Dynamic import of @antv/g6 for code-splitting (saves ~553KB from initial bundle)
let G6Graph: any = null
async function ensureG6Loaded() {
  if (!G6Graph) {
    G6Graph = await loadG6Graph()
  }
  return G6Graph
}

// router available via useRouter() if needed
const graphStore = useGraphStore()
const graphRef = ref<HTMLElement | null>(null)
let graph: any = null

// ── Composables ──
const { POSITION_COLOR, SKILL_COLOR, SKILL_BONUS_COLOR, KA_COLOR_MAP } = useGraphColors()
const { totalPositions, totalSkills, totalDomains } = useKPIMetrics()
const KA_FALLBACK_COLORS = ref(['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc'])

// ── 面包屑导航 ──
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

// ── 视图模式切换（使用 store 中的 overviewMode） ──
function onOverviewModeChange(mode: string) {
  // Fade out current graph, fetch new data, fade in
  if (graph) {
    const nodes = graph.getNodeData().map((n: any) => ({ id: n.id, style: { fillOpacity: 0, scale: 0.5 } }))
    graph.updateNodeData(nodes)
    graph.draw()
  }
  graphStore.fetchOverview(mode as OverviewMode).then(() => {
    nextTick(() => renderCurrentLayer())
  })
}

// ── 布局模式切换（force / dagre 分层） ──
type LayoutMode = 'force' | 'dagre' | 'radial'
const layoutMode = ref<LayoutMode>('force')

function toggleLayout() {
  layoutMode.value = layoutMode.value === 'force' ? 'dagre' : layoutMode.value === 'dagre' ? 'radial' : 'force'
  renderCurrentLayer()
}

// ── 2D/3D 视图切换 ──
type ViewMode = '2d' | '3d'
const viewMode = ref<ViewMode>('3d')
const graph3DRef = ref<InstanceType<typeof Graph3D> | null>(null)
const autoRotate = ref(false)

function toggleViewMode() {
  viewMode.value = viewMode.value === '2d' ? '3d' : '2d'
}

// ── 3D camera presets ──
function onCameraPreset(preset: 'overview' | 'domain' | 'position') {
  graph3DRef.value?.setCameraPreset(preset)
}

function onResetCamera() {
  graph3DRef.value?.resetCamera()
}

function onToggleAutoRotate() {
  graph3DRef.value?.toggleAutoRotate()
  autoRotate.value = !autoRotate.value
}

// ── 3D node click handler ──
function on3DNodeClick(node: any) {
  const nodeId = node.id
  // Reuse existing handleNodeClick logic
  handleNodeClick(nodeId)
}

// ── Prepare 3D graph data (transform visible nodes/edges) ──
const graph3DNodes = computed(() => {
  return graphStore.visibleNodes.map(n => ({
    id: n.id,
    labels: n.labels,
    properties: {
      name: n.properties.name,
      category: (n.properties as any).category,
      proficiency: (n.properties as any).proficiency,
      position_count: (n.properties as any).position_count,
      skill_count: (n.properties as any).skill_count,
      weight: (n.properties as any).weight,
    },
  }))
})

const graph3DLinks = computed(() => {
  return graphStore.visibleEdges.map(e => ({
    source: e.source_id,
    target: e.target_id,
    type: e.type,
    properties: e.properties,
  }))
})

// ── EVOLVES_TO 演化边 ──
const showEvolution = ref(false)
const maxNodesLimit = ref(50)
const proficiencyFilter = ref<string[]>(['精通', '熟悉', '了解'])

function onMaxNodesChange(val: number) {
  maxNodesLimit.value = val
  renderCurrentLayer()
}

function onProficiencyFilter(levels: string[]) {
  proficiencyFilter.value = levels
  renderCurrentLayer()
}

function resetHighlight() {
  clearHighlight()
}
const evolutionEdges = ref<{ source: string; target: string; similarity: number }[]>([])

async function fetchEvolutionEdges() {
  try {
    const data = await request.get('/evolution/paths/all')
    if (Array.isArray(data)) {
      evolutionEdges.value = data.map((p: any) => ({
        source: p.source_position,
        target: p.target_position,
        similarity: p.similarity ?? 0.5,
      }))
    }
  } catch {
    evolutionEdges.value = []
  }
}

function toggleEvolution() {
  showEvolution.value = !showEvolution.value
  if (showEvolution.value && evolutionEdges.value.length === 0) fetchEvolutionEdges()
  renderCurrentLayer()
}

// ── 选中的节点（详情面板） ──
const selectedNode = ref<GraphNode | null>(null)

// ── 搜索 ──

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
  // 遍历缓存的 positionsByKA
  for (const [kaId, positions] of graphStore.positionsByKA) {
    if (positions.some(p => p.id === positionId)) return kaId
  }
  return null
}

// ── 雷达图 ──
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

// ── G6 图谱初始化 ──
async function initGraph() {
  if (!graphRef.value) return
  if (graph) { graph.destroy(); graph = null }
  const container = graphRef.value
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  try {
    const GraphClass = await ensureG6Loaded(); graph = new GraphClass({
      container,
      width,
      height,
      layout: { type: "force", preventOverlap: true, nodeSize: 40, nodeSpacing: 20, animate: true },
      node: {
        style: {
          labelFill: cv("--foreground"),
          labelFontSize: 12,
          labelPlacement: "bottom" as const,
          labelOffsetY: 8,
                  },
      },
      edge: {
        style: {
          stroke: cv("--border"),
          lineWidth: 1.5,
          opacity: 0.5,
          endArrow: true,
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element", { type: "hover-activate", degree: 1, direction: "both" }],
      plugins: ['minimap', { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { background: cv('--card'), borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '10px 14px', fontSize: '12px', border: '1px solid ' + cv('--border'), color: cv('--foreground') } }],
    })

    graph.on("node:click", (event: any) => {
      const nodeId = event.target?.id
      if (!nodeId) return
      handleNodeClick(nodeId)
    })

    graph.on("node:dblclick", (event: any) => {
      const nodeId = event.target?.id
      if (!nodeId) return
      expandTwoHop(nodeId)
    })

    graph.on("canvas:click", () => {
      selectedNode.value = null
      clearHighlight()
    })

    renderCurrentLayer()
  } catch (err) {
    console.error("[Home] Failed to initialize graph:", err)
    ElMessage.error('图谱加载失败，请确认后端服务已启动')
  }
}

// ── 渲染当前层 ──
function renderCurrentLayer() {
  if (!graph) return
  if (graphStore.currentLayer === "domain") {
    renderDomainLayer()
  } else if (graphStore.currentLayer === "position") {
    renderPositionLayer()
  } else {
    renderDetailLayer()
  }
}

function renderDomainLayer() {
  if (!graph) return
  const maxSkill = Math.max(...graphStore.domains.map(d => d.skill_count), 1)
  const minSize = 50, maxSize = 100

  // Filter out empty domains for cleaner view
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
    const color = KA_COLOR_MAP.value.get(n.id) ?? KA_FALLBACK_COLORS.value[i % KA_FALLBACK_COLORS.value.length]
    return {
      id: n.id,
      style: {
        size,
        fill: color,
        fillOpacity: 0.9,
        stroke: color,
        lineWidth: importance > 100 ? 3 : 2,
        labelText: n.properties.name + "\n" + posCount + "岗 " + skillCount + "技",
        labelFill: cv("--primary-foreground"),
        labelFontSize: importance > 100 ? 15 : 13,
        labelFontWeight: "bold" as const,
        labelPlacement: "center" as const,
        shadowColor: "rgba(0,0,0,0.2)",
        shadowBlur: importance > 100 ? 20 : 12,
        cursor: "pointer" as const,
      },
    }
  })

  const graphEdges = graphStore.visibleEdges.map(e => ({
    id: `${e.source_id}-${e.target_id}-${e.type}`,
    source: e.source_id,
    target: e.target_id,
    style: {
      stroke: cv("--muted-foreground"),
      lineWidth: 1.5,
      opacity: 0.3,
      lineDash: [6, 4],
      endArrow: false,
    },
  }))

  graph.setData({ nodes: graphNodes, edges: graphEdges })
  // Staggered entrance: hide all nodes first, then reveal
  const entranceNodes = graphNodes.map((n: any) => ({
    id: n.id,
    style: { fillOpacity: 0, scale: 0.3 }
  }))
  graph.updateNodeData(entranceNodes)

  const isLevel = graphStore.overviewMode === 'level'
  const isTechStack = graphStore.overviewMode === 'tech_stack'
  if (layoutMode.value === 'dagre' || isLevel) {
    graph.setLayout({ type: 'dagre', rankdir: 'TB', nodesep: isLevel ? 140 : 80, ranksep: isLevel ? 160 : 100, preventOverlap: true, nodeSize: 80, controlPoints: true })
  } else if (isTechStack) {
    graph.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: true, clustering: true, clusterNodeStrength: 0.5, strength: 0.4, coulombDisScale: 0.005, gravity: 8, maxSpeed: 200, maxIteration: 100 })
  } else {
    graph.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: true, strength: 0.4, coulombDisScale: 0.005, gravity: 10, maxSpeed: 200, maxIteration: 100 })
  }
  graph.render()
  setTimeout(() => {
    graph?.fitView()
    // Animate entrance
    if (graph) {
      const finalNodes = graphNodes.map((n: any) => ({
        id: n.id,
        style: { fillOpacity: 0.85, scale: 1 }
      }))
      graph.updateNodeData(finalNodes)
      graph.draw()
    }
  }, 100)
}

function renderPositionLayer() {
  if (!graph) return
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (KA_COLOR_MAP.value.get(kaId) ?? cv("--chart-3")) : cv("--chart-3")
  const positions = graphStore.positionsByKA.get(kaId ?? "") ?? []
  const maxSkillCount = Math.max(...positions.map(p => {
    let count = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === "REQUIRES") count++ }
    return count
  }), 1)

  const graphNodes: any[] = []
  const graphEdges: any[] = []

  // KA 节点（中心，缩小）
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
        labelFill: cv("--primary-foreground"),
        labelFontSize: 13,
        labelFontWeight: "bold" as const,
        labelPlacement: "center" as const,
        shadowColor: kaColor,
        shadowBlur: 24,
        shadowOffsetY: 3,
      },
    })
  }

  // Apply maxNodesLimit to positions (keep KA node + limit positions)
  const maxPositionNodes = Math.max(maxNodesLimit.value - 1, 5)
  const sortedPositions = [...positions].sort((a, b) => {
    let aCount = 0, bCount = 0
    for (const e of graphStore.allEdges) {
      if (e.source_id === a.id && e.type === 'REQUIRES') aCount++
      if (e.source_id === b.id && e.type === 'REQUIRES') bCount++
    }
    return bCount - aCount
  })
  const limitedPositions = sortedPositions.slice(0, maxPositionNodes)

  // Position 节点
  const posColor = POSITION_COLOR
  for (const p of limitedPositions) {
    let skillCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === "REQUIRES") skillCount++ }
    const size = 28 + (skillCount / maxSkillCount) * 16

    graphNodes.push({
      id: p.id,
      style: {
        size,
        fill: posColor,
        fillOpacity: 0.85,
        stroke: cv("--primary-hover"),
        lineWidth: 1.5,
        labelText: p.properties.name,
        labelFill: cv("--foreground"),
        labelFontSize: 11,
        labelFontWeight: "normal" as const,
        labelPlacement: "bottom" as const,
        labelOffsetY: 6,
              },
    })

    // KA → Position 边
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

  // EVOLVES_TO 演化边（跨领域）
  if (showEvolution.value) {
    for (const ev of evolutionEdges.value) {
      const sourceNode = graphStore.nodeMap.get(ev.source) || graphStore.allNodes.find(n => n.properties.name === ev.source)
      const targetNode = graphStore.nodeMap.get(ev.target) || graphStore.allNodes.find(n => n.properties.name === ev.target)
      if (sourceNode && targetNode) {
        graphEdges.push({
          id: `evo-${ev.source}-${ev.target}`,
          source: sourceNode.id,
          target: targetNode.id,
          style: {
            stroke: cv("--destructive"),
            lineWidth: 2 + ev.similarity * 3,
            opacity: 0.8,
            lineDash: [12, 6],
            endArrow: true,
            endArrowSize: 8,
          },
        })
      }
    }
  }

  // EVOLVES_TO 演化边（岗位层）
  if (showEvolution.value) {
    for (const ev of evolutionEdges.value) {
      const src = limitedPositions.find(p => p.id === ev.source || p.properties.name === ev.source)
      const tgt = limitedPositions.find(p => p.id === ev.target || p.properties.name === ev.target)
      if (src && tgt) {
        graphEdges.push({
          id: `evo-${src.id}-${tgt.id}`,
          source: src.id,
          target: tgt.id,
          style: {
            stroke: cv("--destructive"),
            lineWidth: 2 + ev.similarity * 3,
            opacity: 0.8,
            lineDash: [12, 6],
            endArrow: true,
            endArrowSize: 8,
          },
        })
      }
    }
  }

  graph.setData({ nodes: graphNodes, edges: graphEdges })
  graph.setLayout({ type: "radial", unitRadius: 160, preventOverlap: true, nodeSize: 48, focusNode: kaId || undefined, animate: true })
  graph.render()
  setTimeout(() => graph?.fitView(), 300)
}

function renderDetailLayer() {
  if (!graph) return
  const posId = graphStore.expandedPositionId
  if (!posId) return

  const graphNodes: any[] = []
  const graphEdges: any[] = []
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (KA_COLOR_MAP.value.get(kaId) ?? cv("--chart-3")) : cv("--chart-3")

  // KA 节点（远处，更小）
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
        labelFill: cv("--muted-foreground"),
        labelFontSize: 10,
        labelPlacement: "bottom" as const,
        labelOffsetY: 4,
      },
    })
  }

  // Position 节点（中心）
  const posNode = graphStore.nodeMap.get(posId)
  graphNodes.push({
    id: posId,
    style: {
      size: 50,
      fill: POSITION_COLOR,
      fillOpacity: 0.9,
      stroke: cv("--primary-hover"),
      lineWidth: 3,
      labelText: posNode?.properties.name ?? "岗位",
      labelFill: cv("--primary-foreground"),
      labelFontSize: 13,
      labelFontWeight: "bold" as const,
      labelPlacement: "center" as const,
      shadowColor: "rgba(59,130,246,0.3)",
      shadowBlur: 12,
          },
  })

  // Skill 节点 — apply maxNodesLimit + proficiency filter (reserve ~3 for KA + Position nodes)
  const allPosEdges = graphStore.visibleEdges.filter(e => e.source_id === posId)

  // Apply proficiency filter: when all 3 levels are selected, show everything
  const hasActiveFilter = proficiencyFilter.value.length < 3
  const filteredEdges = hasActiveFilter
    ? allPosEdges.filter(e => {
        const skillNode = graphStore.nodeMap.get(e.target_id)
        if (!skillNode) return false
        const prof = skillNode.properties.proficiency || (e.properties as any)?.level || ''
        return prof ? proficiencyFilter.value.includes(prof) : true
      })
    : allPosEdges

  const maxSkillNodes = Math.max(maxNodesLimit.value - 3, 5)
  const sortedEdges = [...filteredEdges].sort((a, b) => (b.properties?.weight ?? 0.5) - (a.properties?.weight ?? 0.5))
  const posEdges = sortedEdges.slice(0, maxSkillNodes)
  const maxWeight = Math.max(...posEdges.map(e => e.properties?.weight ?? 0.5), 0.1)

  for (const e of posEdges) {
    const skillNode = graphStore.nodeMap.get(e.target_id)
    if (!skillNode) continue
    const weight = e.properties?.weight ?? 0.5
    const isRequired = weight >= 0.6
    const size = 14 + (weight / maxWeight) * 14

    graphNodes.push({
      id: e.target_id,
      style: {
        size,
        fill: isRequired ? SKILL_COLOR : SKILL_BONUS_COLOR,
        fillOpacity: 0.8,
        stroke: isRequired ? cv("--success") : cv("--warning"),
        lineWidth: 1,
        labelText: skillNode.properties.name,
        labelFill: cv("--foreground"),
        labelFontSize: 10,
        labelPlacement: "bottom" as const,
        labelOffsetY: 4,
      },
    })

    // Position → Skill 边
    graphEdges.push({
      id: `${posId}-${e.target_id}-REQUIRES`,
      source: posId,
      target: e.target_id,
      style: {
        stroke: isRequired ? SKILL_COLOR : SKILL_BONUS_COLOR,
        lineWidth: isRequired ? 2 : 1.5,
        opacity: 0.6,
        lineDash: isRequired ? [] : [5, 3],
        endArrow: !isRequired,
      },
    })
  }

  graph.setData({ nodes: graphNodes, edges: graphEdges })
  graph.setLayout({ type: "radial", unitRadius: 140, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: true })
  graph.render()
  setTimeout(() => graph?.fitView(), 300)
}

// ── 节点点击处理 ──
// ── 双击展开 2 跳子图 ──
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function expandTwoHop(nodeId: string) {
  if (!graph) return
  const oneHop = new Set<string>([nodeId])
  const twoHop = new Set<string>([nodeId])

  // 1 跳
  for (const e of graphStore.allEdges) {
    if (e.source_id === nodeId) oneHop.add(e.target_id)
    if (e.target_id === nodeId) oneHop.add(e.source_id)
  }
  // 2 跳
  for (const hopId of oneHop) {
    if (hopId === nodeId) continue
    for (const e of graphStore.allEdges) {
      if (e.source_id === hopId) twoHop.add(e.target_id)
      if (e.target_id === hopId) twoHop.add(e.source_id)
    }
  }

  // 高亮 2 跳内的节点，淡化其余
  if (graph) {
    const updateNodes = graphStore.visibleNodes.map(n => ({
      id: n.id,
      style: {
        fillOpacity: twoHop.has(n.id) ? 0.9 : 0.08,
        lineWidth: twoHop.has(n.id) ? 2 : 0.5,
      },
    }))
    graph.updateNodeData(updateNodes)
    graph.draw()
  }

  // 选中中心节点
  const node = graphStore.nodeMap.get(nodeId)
  if (node) selectedNode.value = node
}

async function handleNodeClick(nodeId: string) {
  // Domain 层：点击 KA → 进入 Position 层
  if (graphStore.currentLayer === "domain") {
    const domain = graphStore.domains.find(d => d.id === nodeId)
    if (domain) {
      selectedNode.value = {
        id: domain.id,
        labels: ["KnowledgeArea"],
        properties: { name: domain.name, position_count: domain.position_count, skill_count: domain.skill_count },
      }
      await graphStore.goToPositionLayer(domain.id, domain.name)
      renderCurrentLayer()
    }
    return
  }

  // Position 层：点击 Position → 进入 Detail 层；点击 KA → 选中
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
      renderCurrentLayer()
    }
    return
  }

  // Detail 层：点击 Skill → 选中；点击 Position → 选中
  if (graphStore.currentLayer === "detail") {
    const node = graphStore.nodeMap.get(nodeId)
    if (node) selectedNode.value = node
    if (graph) highlightNode(nodeId)
  }
}

function highlightNode(nodeId: string) {
  if (!graph) return
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
        shadowColor: isCenter ? cv("--primary") : "transparent",
        shadowBlur: isCenter ? 24 : 0,
      },
    }
  })
  graph.updateNodeData(updateNodes)
  graph.draw()
}

function clearHighlight() {
  renderCurrentLayer()
}

function closeDetail() {
  selectedNode.value = null
  clearHighlight()
}

// ── 缩放控制 ──
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function zoomIn() { const g = graph as any; g?.zoomTo(g.getZoom() * 1.3) }
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function zoomOut() { const g = graph as any; g?.zoomTo(g.getZoom() * 0.7) }
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function zoomFit() { (graph as any)?.fitView() }

// ── 响应式 ──
function handleResize() {
  if (!graph || !graphRef.value) return
  (graph as any).setSize(graphRef.value.clientWidth, graphRef.value.clientHeight)
}

// ── Watch 层级变化 → 重新渲染 ──
watch(() => graphStore.currentLayer, () => {
  selectedNode.value = null
  renderCurrentLayer()
})

// ── Watch viewMode → re-render G6 when switching back to 2D ──
watch(viewMode, (mode) => {
  if (mode === '2d' && graph) {
    nextTick(() => renderCurrentLayer())
  }
})

// ── 生命周期 ──
onMounted(async () => {
  await graphStore.fetchOverview()
  await nextTick()
  initGraph()
  window.addEventListener("resize", handleResize)
})

onUnmounted(() => {
  window.removeEventListener("resize", handleResize)
  if (graph) { graph.destroy(); graph = null }
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
          <!-- Graph breadcrumb -->
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
              >›</span>
            </template>
          </nav>

          <!-- View mode tabs -->
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
          <!-- 2D / 3D Toggle -->
          <div class="view-mode-toggle">
            <button
              class="vm-btn"
              :class="{ 'vm-btn--active': viewMode === '2d' }"
              @click="viewMode = '2d'"
            >2D</button>
            <button
              class="vm-btn"
              :class="{ 'vm-btn--active': viewMode === '3d' }"
              @click="viewMode = '3d'"
            >3D</button>
            <span class="vm-indicator" :class="{ 'vm-indicator--3d': viewMode === '3d' }" />
          </div>

          <!-- Legend -->
          <div class="graph-legend">
            <span class="legend-item"><span class="ld-dot ld-dot--domain" />领域</span>
            <span class="legend-item"><span class="ld-dot ld-dot--position" />岗位</span>
            <span class="legend-item"><span class="ld-dot ld-dot--skill" />技能</span>
            <span
              v-if="showEvolution"
              class="legend-item"
            ><span class="ld-line" />演化</span>
          </div>

          <!-- Evolution toggle -->
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
            <!-- 2D Graph (G6) — shown when viewMode === '2d' -->
            <div
              v-show="viewMode === '2d'"
              ref="graphRef"
              class="graph-canvas"
            />

            <!-- 3D Graph — shown when viewMode === '3d' -->
            <Graph3D
              v-show="viewMode === '3d'"
              ref="graph3DRef"
              :nodes="graph3DNodes"
              :links="graph3DLinks"
              @node-click="on3DNodeClick"
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
              </p><p class="empty-hint-text">
                请确认后端服务已启动并有数据接入
              </p>
            </div>

            <!-- Floating toolbar -->
            <GraphToolbar
              :node-count="graphStore.visibleNodes.length"
              :layout-mode="layoutMode"
              :is3-d="viewMode === '3d'"
              :auto-rotate="autoRotate"
              @zoom-in="graph?.zoomBy(1.2)"
              @zoom-out="graph?.zoomBy(0.8)"
              @zoom-fit="graph?.fitView()"
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

        <!-- ── Right Detail Panel ── -->
        <DetailPanel
          :selected-node="selectedNode"
          :position-radar-option="positionRadarOption"
          @close="closeDetail"
          @navigate-to-detail="(n) => selectedNode = n"
        />
      </div>

      <!-- ── Bottom Search Bar ── -->
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
.kpi-strip {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  min-width: 140px;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  border-color: color-mix(in srgb, var(--primary) 20%, var(--border));
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: var(--font-size-xl);
  position: relative;
  z-index: 1;
}
.kpi-body {
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}
.kpi-value {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--foreground);
  line-height: 1.1;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-label {
  font-size: 10px;
  color: var(--muted-foreground);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 600;
}
.kpi-trend {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: 1px;
  opacity: 0.7;
}
.kpi-actions {
  display: flex;
  gap: var(--space-2);
  margin-left: auto;
}
.kpi-icon--info { background: var(--info-ghost); color: var(--info); }
.kpi-icon--primary { background: var(--primary-ghost); color: var(--primary); }
.kpi-icon--success { background: var(--success-ghost); color: var(--success); }

/* ── Graph Controls Bar ── */
.graph-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-1);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-2) var(--space-4);
  box-shadow: var(--shadow-xs);
}
.controls-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.controls-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.graph-breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--font-size-sm);
}
.gb-item {
  color: var(--muted-foreground);
  cursor: pointer;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast);
  font-weight: 500;
}
.gb-item:hover:not(.active) {
  color: var(--primary);
  background: var(--primary-ghost);
}
.gb-item.active {
  color: var(--foreground);
  font-weight: 600;
  cursor: default;
}
.gb-sep {
  color: var(--border);
  font-size: var(--font-size-xs);
  margin: 0 2px;
}
.view-tabs {
  --el-radio-button-checked-bg-color: var(--primary);
  --el-radio-button-checked-border-color: var(--primary);
}

/* ── 2D / 3D View Mode Toggle ── */
.view-mode-toggle {
  display: flex;
  align-items: center;
  position: relative;
  background: color-mix(in srgb, var(--muted-foreground) 8%, transparent);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 2px;
}
.vm-btn {
  position: relative;
  z-index: 2;
  padding: 4px 14px;
  border: none;
  background: none;
  color: var(--muted-foreground);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: color var(--duration-fast) var(--ease-out);
}
.vm-btn--active {
  color: var(--primary-foreground);
}
.vm-indicator {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(50% - 2px);
  height: calc(100% - 4px);
  background: var(--primary);
  border-radius: var(--radius-md);
  transition: transform var(--duration-normal) var(--ease-out);
  z-index: 1;
  box-shadow: 0 1px 4px color-mix(in srgb, var(--primary) 40%, transparent);
}
.vm-indicator--3d {
  transform: translateX(100%);
}
.view-tabs .el-radio-button__inner {
  font-size: var(--font-size-xs);
  font-weight: 500;
  letter-spacing: 0.02em;
  padding: 6px 14px;
  transition: all var(--duration-normal) var(--ease-out);
}
.graph-legend {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.ld-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.ld-line {
  width: 16px;
  height: 0;
  border-top: 2px dashed var(--destructive);
}
.ld-dot--domain { background: var(--chart-3); }
.ld-dot--position { background: var(--chart-1); }
.ld-dot--skill { background: var(--success); }

/* ── Graph Layout ── */
.graph-layout {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
  perspective: 1200px;
}
.graph-main {
  flex: 1;
  min-width: 0;
}
.graph-container {
  position: relative;
  background: var(--card);
  transform: rotateX(1deg);
  transform-origin: center bottom;
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  overflow: hidden;
  height: 100%;
  min-height: 520px;
  box-shadow: var(--shadow-md);
  perspective: 1200px;
}
.graph-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 50%, color-mix(in srgb, var(--background) 30%, transparent) 100%);
  pointer-events: none;
  z-index: 2;
  border-radius: inherit;
}
.graph-container::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--border) 50%, transparent) 1px, transparent 0);
  background-size: 32px 32px;
  opacity: 0.3;
  pointer-events: none;
  z-index: 0;
}
.graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 520px;
  position: relative;
  z-index: 1;
}
.empty-hint {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}

/* Right panel styles moved to DetailPanel.vue component */

/* ── Transitions ── */
.fade-enter-active, .fade-leave-active { transition: opacity var(--duration-fast); }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .right-panel { width: 240px; }
  .right-panel:not(.open) { width: 100px; }
  .kpi-actions { margin-left: 0; width: 100%; }
}
@media (max-width: 768px) {
  .graph-layout { flex-direction: column; }
  .right-panel { width: 100%; max-height: 200px; }
  .right-panel:not(.open) { width: 100%; max-height: 60px; }
  .graph-canvas { min-height: 360px; }
  .graph-container { min-height: 360px; }
  .kpi-strip { flex-direction: column; align-items: stretch; }
  .kpi-actions { flex-direction: column; }
    .controls-left, .controls-right { flex-wrap: wrap; }
}
</style>