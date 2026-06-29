<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from "vue"
import { useRouter } from "vue-router"
import { Graph } from "@antv/g6"
import { Search, ZoomIn, ZoomOut, Aim, Collection, DataAnalysis, Upload, Document, TrendCharts, ArrowRight } from "@element-plus/icons-vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { RadarChart } from "echarts/charts"
import { TooltipComponent, LegendComponent, RadarComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])
import request from "@/api/request"
import MainLayout from "@/layouts/MainLayout.vue"
import { useGraphStore, type GraphNode, type ViewLayer, type OverviewMode } from "@/stores/graph"

// router available via useRouter() if needed
const graphStore = useGraphStore()
const graphRef = ref<HTMLElement | null>(null)
let graph: Graph | null = null

// ── 颜色常量 ──
const KA_FALLBACK_COLORS = ["#9B59B6", "#E6A23C", "#409EFF", "#67C23A", "#36CFC9", "#F56C6C", "#E040FB", "#FF7043", "#00BCD4", "#8BC34A", "#FF5252", "#7C4DFF", "#009688", "#FF9800"]
const KA_COLOR_MAP = computed(() => {
  const map = new Map<string, string>()
  graphStore.domains.forEach((d, i) => {
    map.set(d.id, d.color || KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length])
  })
  return map
})
const POSITION_COLOR = "#3B82F6"
const SKILL_COLOR = "#10B981"
const SKILL_BONUS_COLOR = "#F59E0B"

// ── KPI ──
const totalPositions = computed(() => graphStore.domains.reduce((s, d) => s + d.position_count, 0))
const totalSkills = computed(() => graphStore.domains.reduce((s, d) => s + d.skill_count, 0))
const totalDomains = computed(() => graphStore.domains.length)

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

// ── 视图模式切换 ──
const overviewMode = ref<OverviewMode>('domain')

function onOverviewModeChange(mode: string) {
  graphStore.fetchOverview(mode as OverviewMode)
}

// ── 布局模式切换（force / dagre 分层） ──
type LayoutMode = 'force' | 'dagre'
const layoutMode = ref<LayoutMode>('force')

function toggleLayout() {
  layoutMode.value = layoutMode.value === 'force' ? 'dagre' : 'force'
  renderCurrentLayer()
}

// ── EVOLVES_TO 演化边 ──
const showEvolution = ref(false)
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
const searchKeyword = ref("")
const showSearchDropdown = ref(false)
const searchHighlightIndex = ref(-1)
const searchResults = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return []
  // 搜索所有已加载节点 + 领域
  const results: { id: string; name: string; type: string }[] = []
  for (const d of graphStore.domains) {
    if (d.name.toLowerCase().includes(kw)) results.push({ id: d.id, name: d.name, type: "领域" })
  }
  for (const n of graphStore.allNodes) {
    if (n.properties.name.toLowerCase().includes(kw)) {
      const label = n.labels[0] === "Position" ? "岗位" : n.labels[0] === "Skill" ? "技能" : n.labels[0]
      results.push({ id: n.id, name: n.properties.name, type: label })
    }
  }
  results.sort((a, b) => {
    const ae = a.name.toLowerCase() === kw ? 0 : 1, be = b.name.toLowerCase() === kw ? 0 : 1
    return ae - be
  })
  return results.slice(0, 10)
})

function onSearchInput() {
  showSearchDropdown.value = searchResults.value.length > 0 && searchKeyword.value.trim().length > 0
  searchHighlightIndex.value = -1
}
function onSearchKeydown(e: KeyboardEvent) {
  if (e.key === "ArrowDown") { e.preventDefault(); searchHighlightIndex.value = searchHighlightIndex.value < searchResults.value.length - 1 ? searchHighlightIndex.value + 1 : 0 }
  else if (e.key === "ArrowUp") { e.preventDefault(); searchHighlightIndex.value = searchHighlightIndex.value > 0 ? searchHighlightIndex.value - 1 : searchResults.value.length - 1 }
  else if (e.key === "Enter") { e.preventDefault(); if (searchHighlightIndex.value >= 0) selectSearchResult(searchResults.value[searchHighlightIndex.value]); else if (searchResults.value.length) selectSearchResult(searchResults.value[0]) }
  else if (e.key === "Escape") { searchKeyword.value = ""; showSearchDropdown.value = false }
}
function selectSearchResult(result: { id: string; name: string; type: string }) {
  showSearchDropdown.value = false; searchHighlightIndex.value = -1; searchKeyword.value = ""
  // 如果是领域，跳到 position 层
  const domain = graphStore.domains.find(d => d.id === result.id)
  if (domain) {
    graphStore.goToPositionLayer(domain.id, domain.name)
    return
  }
  // 如果是岗位，找到所属 KA 并跳到 detail 层
  const node = graphStore.allNodes.find(n => n.id === result.id)
  if (node?.labels.includes("Position")) {
    // 找到该 Position 属于哪个 KA
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
  // 如果是技能，找到所属 Position
  if (node?.labels.includes("Skill")) {
    // 找到哪个 Position 需要这个 Skill
    for (const e of graphStore.allEdges) {
      if (e.target_id === result.id && e.type === "REQUIRES") {
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
function onSearchBlur() { setTimeout(() => { showSearchDropdown.value = false }, 200) }

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
    tooltip: { trigger: "item" },
    radar: {
      center: ["50%", "50%"],
      radius: "60%",
      indicator: sliced.map(s => ({ name: s.name, max: 1 })),
      axisName: { color: "#606266", fontSize: 10 },
    },
    series: [{
      type: "radar",
      data: [{
        value: sliced.map(s => s.value),
        name: "技能权重",
        areaStyle: { color: "rgba(59,130,246,0.15)" },
        lineStyle: { color: POSITION_COLOR, width: 2 },
        itemStyle: { color: POSITION_COLOR },
      }],
    }],
  }
})

// ── 关联岗位（相似岗位） ──
const relatedPositions = computed(() => {
  if (!selectedNode.value || !selectedNode.value.labels.includes("Position")) return []
  const posId = selectedNode.value.id
  const posSkillIds = new Set<string>()
  for (const e of graphStore.allEdges) {
    if (e.source_id === posId && e.type === "REQUIRES") posSkillIds.add(e.target_id)
  }
  if (!posSkillIds.size) return []
  const similarity = new Map<string, number>()
  for (const e of graphStore.allEdges) {
    if (e.type === "REQUIRES" && posSkillIds.has(e.target_id) && e.source_id !== posId) {
      similarity.set(e.source_id, (similarity.get(e.source_id) ?? 0) + 1)
    }
  }
  const results: { node: GraphNode; sharedCount: number }[] = []
  for (const [id, count] of similarity) {
    const node = graphStore.nodeMap.get(id)
    if (node) results.push({ node, sharedCount: count })
  }
  results.sort((a, b) => b.sharedCount - a.sharedCount)
  return results.slice(0, 6)
})

// ── 相关技能（KA 详情面板） ──
const kaRelatedPositions = computed(() => {
  if (!selectedNode.value || !selectedNode.value.labels.includes("KnowledgeArea")) return []
  return graphStore.positionsByKA.get(selectedNode.value.id) ?? []
})

// ── G6 图谱初始化 ──
function initGraph() {
  if (!graphRef.value) return
  if (graph) { graph.destroy(); graph = null }
  const container = graphRef.value
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  try {
    graph = new Graph({
      container,
      width,
      height,
      layout: { type: "force", preventOverlap: true, nodeSize: 40, nodeSpacing: 20, animate: true },
      node: {
        style: {
          labelFill: "#1f1f1f",
          labelFontSize: 12,
          labelPlacement: "bottom" as const,
          labelOffsetY: 8,
                  },
      },
      edge: {
        style: {
          stroke: "#d0d0d0",
          lineWidth: 1.5,
          opacity: 0.5,
          endArrow: true,
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
      plugins: ['minimap', { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { background: '#fff', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.12)', padding: '8px 12px', fontSize: '12px' } }],
    })

    graph.on("node:click", (event: any) => {
      const nodeId = event.target?.id
      if (!nodeId) return
      handleNodeClick(nodeId)
    })

    graph.on("canvas:click", () => {
      selectedNode.value = null
    })

    renderCurrentLayer()
  } catch (err) {
    console.error("[Home] Failed to initialize graph:", err)
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

  const graphNodes = graphStore.visibleNodes.map((n, i) => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    const skillCount = domain?.skill_count ?? 0
    const size = minSize + (skillCount / maxSkill) * (maxSize - minSize)
    const color = KA_COLOR_MAP.value.get(n.id) ?? KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length]
    return {
      id: n.id,
      style: {
        size,
        fill: color,
        fillOpacity: 0.85,
        stroke: color,
        lineWidth: 2,
        labelText: n.properties.name,
        labelFill: "#ffffff",
        labelFontSize: 14,
        labelFontWeight: "bold" as const,
        labelPlacement: "center" as const,
        shadowColor: "rgba(0,0,0,0.15)",
        shadowBlur: 16,
        
              },
    }
  })

  const graphEdges = graphStore.visibleEdges.map(e => ({
    id: `${e.source_id}-${e.target_id}-${e.type}`,
    source: e.source_id,
    target: e.target_id,
    style: {
      stroke: "#94a3b8",
      lineWidth: 1.5,
      opacity: 0.3,
      lineDash: [6, 4],
      endArrow: false,
    },
  }))

  graph.setData({ nodes: graphNodes, edges: graphEdges })
  const isLevel = overviewMode.value === 'level'
  const isTechStack = overviewMode.value === 'tech_stack'
  if (layoutMode.value === 'dagre' || isLevel) {
    graph.setLayout({ type: 'dagre', rankdir: 'TB', nodesep: isLevel ? 100 : 60, ranksep: isLevel ? 120 : 80, preventOverlap: true, nodeSize: 80 })
  } else if (isTechStack) {
    graph.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: true, clustering: true, clusterNodeStrength: 0.8, strength: 0.6 })
  } else {
    graph.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 40, animate: true, strength: 0.5 })
  }
  graph.render()
  setTimeout(() => graph?.fitView(), 300)
}

function renderPositionLayer() {
  if (!graph) return
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (KA_COLOR_MAP.value.get(kaId) ?? "#9B59B6") : "#9B59B6"
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
        labelFill: "#ffffff",
        labelFontSize: 13,
        labelFontWeight: "bold" as const,
        labelPlacement: "center" as const,
        shadowColor: "rgba(0,0,0,0.12)",
        shadowBlur: 8,
      },
    })
  }

  // Position 节点
  const posColor = POSITION_COLOR
  for (const p of positions) {
    let skillCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === "REQUIRES") skillCount++ }
    const size = 28 + (skillCount / maxSkillCount) * 16

    graphNodes.push({
      id: p.id,
      style: {
        size,
        fill: posColor,
        fillOpacity: 0.85,
        stroke: "#2563eb",
        lineWidth: 1.5,
        labelText: p.properties.name,
        labelFill: "#1e293b",
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
          lineWidth: 1.5,
          opacity: 0.3,
          lineDash: [4, 3],
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
            stroke: '#F56C6C',
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
      const src = positions.find(p => p.id === ev.source || p.properties.name === ev.source)
      const tgt = positions.find(p => p.id === ev.target || p.properties.name === ev.target)
      if (src && tgt) {
        graphEdges.push({
          id: `evo-${src.id}-${tgt.id}`,
          source: src.id,
          target: tgt.id,
          style: {
            stroke: '#F56C6C',
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
  graph.setLayout({ type: "radial", unitRadius: 120, preventOverlap: true, nodeSize: 48, focusNode: kaId || undefined, animate: true })
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
  const kaColor = kaId ? (KA_COLOR_MAP.value.get(kaId) ?? "#9B59B6") : "#9B59B6"

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
        labelFill: "#94a3b8",
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
      stroke: "#1d4ed8",
      lineWidth: 3,
      labelText: posNode?.properties.name ?? "岗位",
      labelFill: "#ffffff",
      labelFontSize: 13,
      labelFontWeight: "bold" as const,
      labelPlacement: "center" as const,
      shadowColor: "rgba(59,130,246,0.3)",
      shadowBlur: 12,
          },
  })

  // Skill 节点
  const posEdges = graphStore.visibleEdges.filter(e => e.source_id === posId)
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
        stroke: isRequired ? "#059669" : "#d97706",
        lineWidth: 1,
        labelText: skillNode.properties.name,
        labelFill: "#374151",
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
  graph.setLayout({ type: "radial", unitRadius: 100, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: true })
  graph.render()
  setTimeout(() => graph?.fitView(), 300)
}

// ── 节点点击处理 ──
// ── 双击展开 2 跳子图 ──
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
        fillOpacity: isCenter ? 1 : isRelated ? 0.8 : 0.2,
        lineWidth: isCenter ? 4 : isRelated ? 2 : 1,
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
function zoomIn() { graph?.zoomTo(graph!.getZoom() * 1.3) }
function zoomOut() { graph?.zoomTo(graph!.getZoom() * 0.7) }
function zoomFit() { graph?.fitView() }

// ── 响应式 ──
function handleResize() {
  if (!graph || !graphRef.value) return
  graph.setSize(graphRef.value.clientWidth, graphRef.value.clientHeight)
}

// ── Watch 层级变化 → 重新渲染 ──
watch(() => graphStore.currentLayer, () => {
  selectedNode.value = null
  renderCurrentLayer()
})

// ── 生命周期 ──
onMounted(async () => {
  await graphStore.fetchOverview()
  graphStore.fetchEvolutionEdges() // Load in background, non-blocking
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
      <div class="kpi-strip">
        <div class="kpi-card">
          <div class="kpi-icon" style="background: var(--info-ghost); color: var(--info)">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-value">{{ totalDomains }}</span>
            <span class="kpi-label">技术领域</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background: var(--primary-ghost); color: var(--primary)">
            <el-icon><Collection /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-value">{{ totalPositions }}</span>
            <span class="kpi-label">岗位数</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background: var(--success-ghost); color: var(--success)">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="kpi-body">
            <span class="kpi-value">{{ totalSkills }}</span>
            <span class="kpi-label">技能数</span>
          </div>
        </div>
        <div class="kpi-actions">
          <el-button size="small" :icon="Upload" @click="$router.push('/match')">简历匹配</el-button>
          <el-button size="small" :icon="Document" @click="$router.push('/extract')">JD 抽取</el-button>
          <el-button size="small" :icon="TrendCharts" @click="$router.push('/evolution')">演化趋势</el-button>
        </div>
      </div>

      <!-- ── Graph Controls Bar ── -->
      <div class="graph-controls">
        <div class="controls-left">
          <!-- Graph breadcrumb -->
          <nav class="graph-breadcrumb">
            <template v-for="(item, i) in breadcrumb" :key="i">
              <span
                class="gb-item"
                :class="{ active: i === breadcrumb.length - 1 }"
                @click="i < breadcrumb.length - 1 && item.action?.()"
              >{{ item.label }}</span>
              <span v-if="i < breadcrumb.length - 1" class="gb-sep">›</span>
            </template>
          </nav>

          <!-- View mode tabs -->
          <el-radio-group
            v-if="graphStore.currentLayer === 'domain'"
            v-model="overviewMode"
            size="small"
            @change="onOverviewModeChange"
            class="view-tabs"
          >
            <el-radio-button value="domain">领域</el-radio-button>
            <el-radio-button value="tech_stack">技术栈</el-radio-button>
            <el-radio-button value="level">级别</el-radio-button>
          </el-radio-group>
        </div>

        <div class="controls-right">
          <!-- Legend -->
          <div class="graph-legend">
            <span class="legend-item"><span class="ld-dot" style="background: var(--chart-3)"></span>领域</span>
            <span class="legend-item"><span class="ld-dot" style="background: var(--chart-1)"></span>岗位</span>
            <span class="legend-item"><span class="ld-dot" style="background: var(--success)"></span>技能</span>
            <span v-if="showEvolution" class="legend-item"><span class="ld-line"></span>演化</span>
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
          <div v-loading="graphStore.loading" class="graph-container">
            <div ref="graphRef" class="graph-canvas" />
            <div v-if="!graphStore.loading && graphStore.visibleNodes.length === 0" class="empty-hint">
              <el-icon size="40" color="var(--muted-foreground)"><Aim /></el-icon>
              <p>暂无数据，请检查后端服务</p>
            </div>

            <!-- Floating toolbar -->
            <div class="graph-toolbar glass">
              <el-tooltip content="放大" placement="top">
                <button class="tb-btn" @click="graph?.zoomBy(1.2)"><el-icon><ZoomIn /></el-icon></button>
              </el-tooltip>
              <el-tooltip content="缩小" placement="top">
                <button class="tb-btn" @click="graph?.zoomBy(0.8)"><el-icon><ZoomOut /></el-icon></button>
              </el-tooltip>
              <el-tooltip content="居中" placement="top">
                <button class="tb-btn" @click="graph?.fitView()"><el-icon><Aim /></el-icon></button>
              </el-tooltip>
              <span class="tb-divider"></span>
              <el-tooltip :content="layoutMode === 'force' ? '切换分层' : '切换力导向'" placement="top">
                <button class="tb-btn" @click="toggleLayout">
                  <span style="font-size: 12px; font-weight: 600">{{ layoutMode === 'force' ? '力' : '层' }}</span>
                </button>
              </el-tooltip>
              <span class="tb-divider"></span>
              <span class="tb-count">{{ graphStore.visibleNodes.length }} 节点</span>
            </div>
          </div>
        </main>

        <!-- ── Right Detail Panel ── -->
        <aside class="right-panel" :class="{ open: !!selectedNode }">
          <template v-if="selectedNode">
            <div class="rp-header">
              <div class="rp-type-badge" :style="{
                background: selectedNode.labels.includes('KnowledgeArea')
                  ? 'var(--chart-3)' : selectedNode.labels.includes('Position')
                  ? 'var(--chart-1)' : 'var(--success)'
              }">
                {{ selectedNode.labels.includes('KnowledgeArea') ? 'KA' : selectedNode.labels.includes('Position') ? 'P' : 'S' }}
              </div>
              <div class="rp-title-group">
                <h3 class="rp-title">{{ selectedNode.properties.name }}</h3>
                <span class="rp-subtitle">
                  {{ selectedNode.labels.includes('KnowledgeArea') ? '知识领域' : selectedNode.labels.includes('Position') ? '岗位' : '技能' }}
                </span>
              </div>
              <button class="rp-close" @click="closeDetail">×</button>
            </div>

            <!-- Radar for Position nodes -->
            <div v-if="positionRadarOption" class="rp-section">
              <div class="rp-section-title">技能雷达</div>
              <VChart :option="positionRadarOption" style="height: 200px" autoresize />
            </div>

            <!-- Properties -->
            <div class="rp-section">
              <div class="rp-section-title">属性</div>
              <div class="rp-props">
                <template v-if="selectedNode.labels.includes('Skill')">
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">类别</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.category ?? '—' }}</span>
                  </div>
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">趋势</span>
                    <el-tag
                      v-if="selectedNode.properties.trend"
                      size="small"
                      :type="selectedNode.properties.trend === 'rising' ? 'success' : selectedNode.properties.trend === 'declining' ? 'danger' : 'info'"
                    >{{ selectedNode.properties.trend === 'rising' ? '↑ 上升' : selectedNode.properties.trend === 'declining' ? '↓ 下降' : '→ 平稳' }}</el-tag>
                    <span v-else class="rp-prop-value">—</span>
                  </div>
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">来源数</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.source_count ?? 0 }}</span>
                  </div>
                </template>
                <template v-else-if="selectedNode.labels.includes('Position')">
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">级别</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.level ?? '—' }}</span>
                  </div>
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">权重</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.weight ?? '—' }}</span>
                  </div>
                </template>
                <template v-else>
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">岗位数</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.position_count ?? 0 }}</span>
                  </div>
                  <div class="rp-prop-row">
                    <span class="rp-prop-label">技能数</span>
                    <span class="rp-prop-value">{{ selectedNode.properties.skill_count ?? 0 }}</span>
                  </div>
                </template>
              </div>
            </div>

            <!-- Related items -->
            <div v-if="relatedPositions.length" class="rp-section">
              <div class="rp-section-title">相似岗位</div>
              <div class="rp-list">
                <div
                  v-for="r in relatedPositions"
                  :key="r.node.id"
                  class="rp-list-item"
                  @click="graphStore.goToDetailLayer(r.node.id); selectedNode = r.node"
                >
                  <span class="rp-list-dot" style="background: var(--chart-1)"></span>
                  <span class="rp-list-name">{{ r.node.properties.name }}</span>
                  <span class="rp-list-meta">{{ r.sharedCount }} 共享技能</span>
                </div>
              </div>
            </div>

            <div v-if="kaRelatedPositions.length" class="rp-section">
              <div class="rp-section-title">所属岗位</div>
              <div class="rp-list">
                <div
                  v-for="p in kaRelatedPositions"
                  :key="p.id"
                  class="rp-list-item"
                  @click="graphStore.goToDetailLayer(p.id); selectedNode = p"
                >
                  <span class="rp-list-dot" style="background: var(--chart-1)"></span>
                  <span class="rp-list-name">{{ p.properties.name }}</span>
                </div>
              </div>
            </div>
          </template>

          <!-- Empty state -->
          <div v-else class="rp-empty">
            <el-icon size="28" color="var(--muted-foreground)"><Aim /></el-icon>
            <p>点击节点查看详情</p>
          </div>
        </aside>
      </div>

      <!-- ── Bottom Search Bar ── -->
      <div class="search-bar glass">
        <div class="search-inner">
          <el-icon size="16" color="var(--muted-foreground)"><Search /></el-icon>
          <div class="search-input-wrapper">
            <input
              v-model="searchKeyword"
              class="search-input"
              placeholder="搜索岗位、技能、领域..."
              @input="onSearchInput"
              @keydown.down.prevent="onSearchKeydown"
              @keydown.up.prevent="onSearchKeydown"
              @keydown.enter.prevent="onSearchKeydown"
              @blur="onSearchBlur"
              @focus="onSearchInput"
            />
            <transition name="fade">
              <div v-if="showSearchDropdown" class="search-dropdown glass">
                <div
                  v-for="(r, idx) in searchResults"
                  :key="r.id"
                  class="search-item"
                  :class="{ highlighted: idx === searchHighlightIndex }"
                  @mousedown.prevent="selectSearchResult(r)"
                >
                  <span
                    class="si-dot"
                    :style="{ background: r.type === '领域' ? 'var(--chart-3)' : r.type === '岗位' ? 'var(--chart-1)' : 'var(--success)' }"
                  ></span>
                  <span class="si-name">{{ r.name }}</span>
                  <span class="si-tag">{{ r.type }}</span>
                </div>
              </div>
            </transition>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
/* ── Page Container ── */
.graph-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: calc(100vh - 180px);
}

/* ── KPI Strip ── */
.kpi-strip {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  min-width: 140px;
  transition: all var(--duration-fast) var(--ease-out);
}

.kpi-card:hover {
  border-color: color-mix(in srgb, var(--primary) 30%, var(--border));
  box-shadow: var(--shadow-sm);
}

.kpi-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.kpi-body {
  display: flex;
  flex-direction: column;
}

.kpi-value {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.kpi-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: 2px;
}

.kpi-actions {
  display: flex;
  gap: var(--space-2);
  margin-left: auto;
}

/* ── Graph Controls Bar ── */
.graph-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-2) 0;
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
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.gb-item {
  color: var(--muted-foreground);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast);
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
  font-size: 12px;
}

.view-tabs {
  --el-radio-button-checked-bg-color: var(--primary);
  --el-radio-button-checked-border-color: var(--primary);
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

/* ── Graph Layout ── */
.graph-layout {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.graph-main {
  flex: 1;
  min-width: 0;
}

.graph-container {
  position: relative;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  height: 100%;
  min-height: 520px;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 520px;
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

/* ── Floating Graph Toolbar ── */
.graph-toolbar {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
}

.tb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.tb-btn:hover {
  color: var(--foreground);
  background: var(--accent);
}

.tb-divider {
  width: 1px;
  height: 16px;
  background: var(--border);
  margin: 0 2px;
}

.tb-count {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  padding: 0 var(--space-2);
}

/* ── Right Detail Panel ── */
.right-panel {
  width: 300px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  transition: all var(--duration-slow) var(--ease-out);
}

.right-panel:not(.open) {
  width: 160px;
  padding: var(--space-4);
}

.rp-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.rp-type-badge {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--font-size-xs);
  font-weight: 700;
  flex-shrink: 0;
}

.rp-title-group {
  flex: 1;
  min-width: 0;
}

.rp-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rp-subtitle {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.rp-close {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: var(--muted-foreground);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all var(--duration-fast);
}

.rp-close:hover {
  color: var(--destructive);
  background: var(--destructive-ghost);
}

.rp-section {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.rp-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.rp-section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-2);
}

.rp-props {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.rp-prop-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
}

.rp-prop-label {
  color: var(--muted-foreground);
}

.rp-prop-value {
  color: var(--foreground);
  font-weight: 500;
}

.rp-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 240px;
  overflow-y: auto;
}

.rp-list-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background var(--duration-fast);
}

.rp-list-item:hover {
  background: var(--accent);
}

.rp-list-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.rp-list-name {
  flex: 1;
  color: var(--foreground);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rp-list-meta {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  flex-shrink: 0;
}

.rp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: var(--space-2);
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}

/* ── Bottom Search Bar ── */
.search-bar {
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-2) var(--space-4);
}

.search-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.search-input-wrapper {
  flex: 1;
  position: relative;
}

.search-input {
  width: 100%;
  border: none;
  background: none;
  outline: none;
  font-size: var(--font-size-sm);
  color: var(--foreground);
  font-family: var(--font-sans);
  padding: var(--space-2) 0;
}

.search-input::placeholder {
  color: var(--muted-foreground);
}

.search-dropdown {
  position: absolute;
  bottom: calc(100% + var(--space-2));
  left: 0;
  right: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  max-height: 280px;
  overflow-y: auto;
  padding: var(--space-1) 0;
  z-index: var(--z-dropdown);
}

.search-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background var(--duration-fast);
}

.search-item:hover,
.search-item.highlighted {
  background: var(--primary-ghost);
}

.si-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.si-name {
  flex: 1;
  color: var(--foreground);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.si-tag {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  flex-shrink: 0;
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

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
  .search-bar { margin: 0 calc(-1 * var(--space-4)); border-radius: 0; border-left: none; border-right: none; }
  .controls-left, .controls-right { flex-wrap: wrap; }
}
</style>
