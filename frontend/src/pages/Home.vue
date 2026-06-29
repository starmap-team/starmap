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
        shadowBlur: 12,
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
  graph.setLayout({ type: "force", preventOverlap: true, nodeSize: 80, nodeSpacing: 40, animate: true, strength: 0.5 })
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
    <div class="graph-page">
      <!-- KPI 卡片 -->
      <div class="kpi-strip">
        <div class="kpi-card" style="border-left-color: #3B82F6">
          <div class="kpi-icon" style="background: rgba(59,130,246,0.1); color: #3B82F6"><el-icon><DataAnalysis /></el-icon></div>
          <div class="kpi-body"><div class="kpi-value">{{ totalDomains }}</div><div class="kpi-label">技术领域</div></div>
        </div>
        <div class="kpi-card" style="border-left-color: #409EFF">
          <div class="kpi-icon" style="background: rgba(64,158,255,0.1); color: #409EFF"><el-icon><Collection /></el-icon></div>
          <div class="kpi-body"><div class="kpi-value">{{ totalPositions }}</div><div class="kpi-label">岗位数</div></div>
        </div>
        <div class="kpi-card" style="border-left-color: #10B981">
          <div class="kpi-icon" style="background: rgba(16,185,129,0.1); color: #10B981"><el-icon><TrendCharts /></el-icon></div>
          <div class="kpi-body"><div class="kpi-value">{{ totalSkills }}</div><div class="kpi-label">技能数</div></div>
        </div>
        <div class="quick-actions">
          <el-button type="primary" size="small" :icon="Upload" @click="$router.push('/match')">上传简历匹配</el-button>
          <el-button type="success" size="small" :icon="Document" @click="$router.push('/extract')">粘贴JD抽取</el-button>
          <el-button type="warning" size="small" :icon="TrendCharts" @click="$router.push('/evolution')">查看演化趋势</el-button>
        </div>
      </div>

      <!-- 视图模式切换 -->
      <div v-if="graphStore.currentLayer === 'domain'" class="view-mode-tabs">
        <el-radio-group v-model="overviewMode" size="small" @change="onOverviewModeChange">
          <el-radio-button value="domain">领域概览</el-radio-button>
          <el-radio-button value="tech_stack">技术栈视图</el-radio-button>
          <el-radio-button value="level">级别视图</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 面包屑导航 -->
      <div class="breadcrumb-nav">
        <template v-for="(item, i) in breadcrumb" :key="i">
          <span
            class="breadcrumb-item"
            :class="{ active: i === breadcrumb.length - 1 }"
            @click="i < breadcrumb.length - 1 && item.action?.()"
          >
            {{ item.label }}
          </span>
          <el-icon v-if="i < breadcrumb.length - 1" class="breadcrumb-sep"><ArrowRight /></el-icon>
        </template>
      </div>

      <!-- 图谱主区域 -->
      <div class="graph-layout">
        <main class="graph-main">
          <div v-loading="graphStore.loading" class="graph-container">
            <div ref="graphRef" class="graph-canvas" />
            <!-- 空状态提示 -->
            <div v-if="!graphStore.loading && graphStore.visibleNodes.length === 0" class="empty-hint">
              <el-icon size="48" color="#c0c4cc"><Aim /></el-icon>
              <p>暂无数据，请检查后端服务是否正常运行</p>
            </div>
          </div>
        </main>

        <!-- 右侧详情面板 -->
        <aside class="right-panel" :class="{ open: !!selectedNode }">
          <template v-if="selectedNode">
            <div class="panel-section">
              <div class="detail-header">
                <div class="section-title">节点详情</div>
                <el-button text size="small" type="danger" @click="closeDetail">关闭</el-button>
              </div>
              <div class="detail-info">
                <div class="detail-row">
                  <span class="detail-dot" :style="{ background: selectedNode.labels.includes('KnowledgeArea') ? (KA_COLOR_MAP.get(selectedNode.id) ?? '#9B59B6') : selectedNode.labels.includes('Position') ? POSITION_COLOR : SKILL_COLOR }" />
                  <strong>{{ selectedNode.properties.name }}</strong>
                </div>
                <div class="detail-row">
                  <span class="detail-label">类型</span>
                  <el-tag size="small" effect="plain">{{ selectedNode.labels.includes('KnowledgeArea') ? '领域' : selectedNode.labels.includes('Position') ? '岗位' : '技能' }}</el-tag>
                </div>
                <div v-if="selectedNode.properties.position_count != null" class="detail-row">
                  <span class="detail-label">岗位数</span>
                  <span>{{ selectedNode.properties.position_count }}</span>
                </div>
                <div v-if="selectedNode.properties.skill_count != null" class="detail-row">
                  <span class="detail-label">技能数</span>
                  <span>{{ selectedNode.properties.skill_count }}</span>
                </div>
                <div v-if="selectedNode.properties.proficiency" class="detail-row">
                  <span class="detail-label">熟练度</span>
                  <span>{{ selectedNode.properties.proficiency }}</span>
                </div>
                <div v-if="selectedNode.properties.source_count" class="detail-row">
                  <span class="detail-label">出现频率</span>
                  <span>{{ selectedNode.properties.source_count }}</span>
                </div>
                <div v-if="selectedNode.properties.trend" class="detail-row">
                  <span class="detail-label">趋势</span>
                  <el-tag size="small" :type="selectedNode.properties.trend === 'rising' ? 'success' : selectedNode.properties.trend === 'declining' ? 'danger' : 'info'">
                    {{ selectedNode.properties.trend === 'rising' ? '上升' : selectedNode.properties.trend === 'declining' ? '下降' : '稳定' }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- Position 技能雷达图 -->
            <template v-if="selectedNode.labels.includes('Position') && positionRadarOption">
              <div class="panel-section">
                <div class="section-title">📊 技能雷达</div>
                <VChart :option="positionRadarOption" autoresize style="height: 200px; width: 100%" />
              </div>
            </template>

            <!-- Position 关联岗位 -->
            <template v-if="selectedNode.labels.includes('Position') && relatedPositions.length">
              <div class="panel-section">
                <div class="section-title">🔗 相似岗位 ({{ relatedPositions.length }})</div>
                <div class="related-list">
                  <div v-for="rp in relatedPositions" :key="rp.node.id" class="related-item" @click="handleNodeClick(rp.node.id)">
                    <span class="related-dot" :style="{ background: POSITION_COLOR }" />
                    <span class="related-name">{{ rp.node.properties.name }}</span>
                    <el-tag size="small" type="warning" effect="plain">{{ rp.sharedCount }}共享</el-tag>
                  </div>
                </div>
              </div>
            </template>

            <!-- KA 下的岗位列表 -->
            <template v-if="selectedNode.labels.includes('KnowledgeArea') && kaRelatedPositions.length">
              <div class="panel-section">
                <div class="section-title">📋 包含岗位 ({{ kaRelatedPositions.length }})</div>
                <div class="related-list">
                  <div v-for="rp in kaRelatedPositions" :key="rp.id" class="related-item" @click="handleNodeClick(rp.id)">
                    <span class="related-dot" :style="{ background: POSITION_COLOR }" />
                    <span class="related-name">{{ rp.properties.name }}</span>
                    <el-icon size="14"><ArrowRight /></el-icon>
                  </div>
                </div>
              </div>
            </template>

            <!-- Position 操作按钮 -->
            <template v-if="selectedNode.labels.includes('Position')">
              <div class="panel-section">
                <el-button type="primary" size="small" :icon="DataAnalysis" @click="$router.push('/match')">用我的技能匹配此岗位</el-button>
                <el-button size="small" @click="$router.push(`/position/${encodeURIComponent(selectedNode.properties.name)}`)">查看岗位详情</el-button>
              </div>
            </template>
          </template>

          <!-- 空状态 -->
          <div v-else class="panel-placeholder">
            <el-icon size="36"><Aim /></el-icon>
            <p>点击节点查看详情</p>
            <p class="hint">
              <template v-if="graphStore.currentLayer === 'domain'">点击气泡进入领域</template>
              <template v-else-if="graphStore.currentLayer === 'position'">点击岗位查看技能</template>
              <template v-else>点击节点查看详情</template>
            </p>
          </div>
        </aside>
      </div>

      <!-- 底部工具栏 -->
      <footer class="bottom-toolbar">
        <div class="toolbar-group">
          <el-button-group>
            <el-button size="small" :icon="ZoomOut" @click="zoomOut" />
            <el-button size="small" :icon="Aim" @click="zoomFit" />
            <el-button size="small" :icon="ZoomIn" @click="zoomIn" />
          </el-button-group>
        </div>
        <div class="toolbar-group layer-indicator">
          <el-tag :type="graphStore.currentLayer === 'domain' ? 'primary' : graphStore.currentLayer === 'position' ? 'success' : 'warning'" size="small" effect="plain">
            {{ graphStore.currentLayer === 'domain' ? '领域概览' : graphStore.currentLayer === 'position' ? '岗位视图' : '技能详情' }}
          </el-tag>
          <span class="node-count">{{ graphStore.visibleNodes.length }} 节点 · {{ graphStore.visibleEdges.length }} 关系</span>
        </div>
        <div class="toolbar-group search-group">
          <div class="smart-search-wrapper">
            <el-input
              v-model="searchKeyword"
              size="small"
              placeholder="搜索领域、岗位、技能... (↑↓导航, Enter选择, Esc清空)"
              :prefix-icon="Search"
              clearable
              style="width: 340px"
              @input="onSearchInput"
              @clear="showSearchDropdown = false"
              @keydown="onSearchKeydown"
              @focus="onSearchInput"
              @blur="onSearchBlur"
            />
            <div v-if="showSearchDropdown && searchResults.length > 0" class="search-dropdown">
              <div
                v-for="(result, idx) in searchResults"
                :key="result.id"
                class="search-result-item"
                :class="{ highlighted: idx === searchHighlightIndex }"
                @mousedown.prevent="selectSearchResult(result)"
                @mouseenter="searchHighlightIndex = idx"
              >
                <span class="result-dot" :style="{ background: result.type === '领域' ? '#9B59B6' : result.type === '岗位' ? POSITION_COLOR : SKILL_COLOR }" />
                <span class="result-name">{{ result.name }}</span>
                <el-tag size="small" effect="plain" class="result-tag">{{ result.type }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  </MainLayout>
</template>

<style scoped>
.graph-page {
  max-width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 8px;
  gap: 10px;
}

/* KPI 卡片 */
.kpi-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-left: 4px solid;
  border-radius: 8px;
  padding: 10px 16px;
  min-width: 120px;
}
.kpi-icon {
  width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.kpi-body { display: flex; flex-direction: column; }
.kpi-value { font-size: 20px; font-weight: 700; color: #1e293b; line-height: 1.2; }
.kpi-label { font-size: 11px; color: #94a3b8; }
.quick-actions { margin-left: auto; display: flex; gap: 8px; }

/* 面包屑 */
.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  font-size: 14px;
}
.breadcrumb-item {
  color: #64748b;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s;
}
.breadcrumb-item:hover:not(.active) {
  color: #3B82F6;
  background: #eff6ff;
}
.breadcrumb-item.active {
  color: #1e293b;
  font-weight: 600;
  cursor: default;
}
.breadcrumb-sep {
  color: #cbd5e1;
  font-size: 12px;
}

/* 图谱布局 */
.graph-layout {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.graph-main {
  flex: 1;
  min-width: 0;
}
.graph-container {
  position: relative;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  height: 100%;
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
  gap: 8px;
  color: #94a3b8;
  font-size: 14px;
}

/* 右侧详情面板 */
.right-panel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.right-panel:not(.open) {
  width: 140px;
  padding: 12px;
}
.panel-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #94a3b8;
  font-size: 13px;
  gap: 6px;
}
.panel-placeholder .hint {
  font-size: 11px;
  color: #cbd5e1;
}
.panel-section {
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}
.panel-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.detail-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}
.detail-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.detail-label {
  color: #94a3b8;
  min-width: 56px;
}
.related-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 300px;
  overflow-y: auto;
}
.related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.related-item:hover {
  background: #f8fafc;
}
.related-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.related-name {
  flex: 1;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 底部工具栏 */
.bottom-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.layer-indicator {
  gap: 8px;
}
.node-count {
  font-size: 12px;
  color: #94a3b8;
}
.search-group {
  margin-left: auto;
}

/* 搜索 */
.smart-search-wrapper {
  position: relative;
}
.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  margin-top: 4px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px 0;
}
.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 13px;
}
.search-result-item:hover,
.search-result-item.highlighted {
  background: #f0f5ff;
}
.result-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.result-name {
  flex: 1;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-tag {
  flex-shrink: 0;
}

/* 响应式 */
@media (max-width: 1024px) {
  .right-panel { width: 220px; }
  .right-panel:not(.open) { width: 80px; }
  .kpi-strip { gap: 8px; }
  .kpi-card { min-width: 100px; padding: 8px 10px; }
  .quick-actions { margin-left: 0; width: 100%; }
}
@media (max-width: 768px) {
  .graph-layout { flex-direction: column; }
  .right-panel { width: 100%; max-height: 200px; }
  .right-panel:not(.open) { width: 100%; max-height: 60px; }
  .graph-canvas { min-height: 360px; }
  .bottom-toolbar { flex-wrap: wrap; gap: 8px; }
  .search-group { margin-left: 0; width: 100%; }
  .search-group .el-input { width: 100% !important; }
  .kpi-strip { flex-direction: column; align-items: stretch; }
  .quick-actions { flex-direction: column; }
}

/* 视图模式切换 */
.view-mode-tabs {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

</style>






