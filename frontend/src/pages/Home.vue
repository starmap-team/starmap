<script setup lang="ts">
/**
 * 全景图谱页 — AntV G6 力导向图
 * 左侧面板：技术栈筛选 + 级别筛选
 * 右侧面板：节点详情
 * 底部工具栏：布局切换 / 缩放 / 搜索
 * 支持技能粒度下钻
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Graph } from '@antv/g6'
import { Search, ZoomIn, ZoomOut, Aim, Collection } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useGraphStore, type GraphNode, type ViewMode } from '@/stores/graph'

const graphStore = useGraphStore()
const graphRef = ref<HTMLElement | null>(null)
let graph: Graph | null = null

// ── 7 类节点颜色 ──
const COLOR_MAP: Record<string, string> = {
  Position: '#409EFF',
  Skill: '#67C23A',
  Tool: '#E6A23C',
  KnowledgeArea: '#9B59B6',
  Certificate: '#36CFC9',
  LearningResource: '#E040FB',
  Industry: '#FF7043',
}

const LABEL_NAMES: Record<string, string> = {
  Position: '岗位',
  Skill: '技能',
  Tool: '工具',
  KnowledgeArea: '领域',
  Certificate: '证书',
  LearningResource: '学习资源',
  Industry: '行业',
}

// ── 筛选器 ──
const techFilters = ['AI', '大数据', '物联网', '前端', '后端', '云计算']
const selectedTech = ref<string[]>([])

function toggleFilter(arr: string[], val: string) {
  const idx = arr.indexOf(val)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(val)
}

// ── 被筛选掉的节点 ID 集合 ──
const filteredNodeIds = computed(() => {
  const ids = new Set<string>()
  for (const n of graphStore.nodes) {
    const name = n.properties.name
    if (selectedTech.value.length && !selectedTech.value.some(t => name.includes(t))) {
      ids.add(n.id)
    }
  }
  return ids
})

// ── 视图模式选项 ──未完成
const viewModeOptions = [
  { label: '技术栈', value: 'tech' as const },
  { label: '级别', value: 'level' as const },
  { label: '热度', value: 'heat' as const },
  { label: '演化', value: 'evolution' as const },
]

// ── 布局模式 ──
type LayoutType = 'force' | 'dagre' | 'radial'
const currentLayout = ref<LayoutType>('force')
const layoutOptions = [
  { label: '力导向', value: 'force' as const },
  { label: '层次', value: 'dagre' as const },
  { label: '辐射', value: 'radial' as const },
]

// ── 搜索 ──
const searchKeyword = ref('')

// ── 选中节点（右侧面板 + 下钻） ──
const selectedNode = ref<GraphNode | null>(null)
const drillStack = ref<GraphNode[]>([])

// 选中节点的关联节点
const relatedNodes = computed(() => {
  if (!selectedNode.value) return []
  const nodeId = selectedNode.value.id
  const relatedIds = new Set<string>()
  for (const e of graphStore.edges) {
    if (e.source_id === nodeId) relatedIds.add(e.target_id)
    if (e.target_id === nodeId) relatedIds.add(e.source_id)
  }
  return graphStore.nodes.filter(n => relatedIds.has(n.id))
})

// 知识领域 → 关联的技能节点（下钻第1跳用）
const relatedSkills = computed(() => {
  if (!selectedNode.value) return []
  return relatedNodes.value.filter(n => n.labels.includes('Skill') || n.labels.includes('Tool'))
})

// 技能 → 知识点列表（下钻第2跳用）
const knowledgePoints = computed(() => {
  if (!selectedNode.value) return []
  return selectedNode.value.properties.knowledge_points ?? []
})

// 是否是领域节点 —— 决定右侧面板展示模式
const isKnowledgeArea = computed(() =>
  selectedNode.value?.labels.includes('KnowledgeArea') ?? false
)

// 是否是技能节点
const isSkill = computed(() =>
  selectedNode.value?.labels.includes('Skill') ?? false
)
// ── 下钻面包屑 ──
const drillBreadcrumb = computed(() => {
  const items = drillStack.value.map(n => ({ id: n.id, name: n.properties.name }))
  if (selectedNode.value) {
    items.push({ id: selectedNode.value.id, name: selectedNode.value.properties.name })
  }
  return items
})

// ── 节点点击 → 选中并高亮关联 ──
function handleNodeClick(nodeId: string) {
  const node = graphStore.nodes.find(n => n.id === nodeId)
  if (!node) return
  if (selectedNode.value && selectedNode.value.id !== nodeId) {
    drillStack.value = [...drillStack.value, selectedNode.value]
  }
  selectedNode.value = node
  highlightRelated(nodeId)
}

// ── 下钻面包屑回退 ──
function goDrillBack(index: number) {
  if (index === -1) {
    selectedNode.value = null
    drillStack.value = []
    clearHighlight()
    return
  }
  const target = drillStack.value[index]
  drillStack.value = drillStack.value.slice(0, index)
  selectedNode.value = target
  highlightRelated(target.id)
}

// ── 关闭右侧详情面板 ──
function closeDetail() {
  selectedNode.value = null
  drillStack.value = []
  clearHighlight()
}

// ── 高亮关联 ──
function highlightRelated(nodeId: string) {
  if (!graph) return
  const relatedIds = new Set<string>([nodeId])
  for (const e of graphStore.edges) {
    if (e.source_id === nodeId) relatedIds.add(e.target_id)
    if (e.target_id === nodeId) relatedIds.add(e.source_id)
  }

  const updatedNodes = graphStore.nodes.map(n => {
    const isRelated = relatedIds.has(n.id)
    const isCenter = n.id === nodeId
    return {
      id: n.id,
      style: {
        size: isCenter ? 40 : isRelated ? 30 : 18,
        opacity: isRelated || isCenter ? 1 : 0.2,
        labelText: isRelated || isCenter ? n.properties.name : '',
      },
    }
  })

  const updatedEdges = graphStore.edges.map(e => {
    const isRelated = e.source_id === nodeId || e.target_id === nodeId
    return {
      id: `${e.source_id}-${e.target_id}-${e.type}`,
      style: {
        stroke: isRelated ? '#409EFF' : '#d0d0d0',
        lineWidth: isRelated ? 2 : 0.5,
        opacity: isRelated ? 0.8 : 0.08,
      },
    }
  })

  graph.updateNodeData(updatedNodes)
  graph.updateEdgeData(updatedEdges)
  graph.draw()
}

// ── 清除高亮，恢复默认样式 ──
function clearHighlight() {
  if (!graph) return
  const resetNodes = graphStore.nodes.map(n => ({
    id: n.id,
    style: { size: 28, opacity: 1, labelText: n.properties.name },
  }))
  const resetEdges = graphStore.edges.map(e => ({
    id: `${e.source_id}-${e.target_id}-${e.type}`,
    style: { stroke: '#d0d0d0', lineWidth: 1, opacity: 0.4 },
  }))
  graph.updateNodeData(resetNodes)
  graph.updateEdgeData(resetEdges)
  graph.draw()
}

// ── 搜索节点 ──
function handleSearch() {
  if (!searchKeyword.value.trim() || !graph) return
  const kw = searchKeyword.value.trim().toLowerCase()
  const found = graphStore.nodes.find(n => n.properties.name.toLowerCase().includes(kw))
  if (found) {
    handleNodeClick(found.id)
  }
}

// ── 布局参数配置 ──
function getLayoutConfig(type: LayoutType) {
  if (type === 'force') {
    return {
      type: 'force' as const,
      linkDistance: 180,
      nodeStrength: -80,//排斥力
      edgeStrength: 80,//边拉力
      preventOverlap: true,
      nodeSize: 28,
      collideStrength: 2,//碰撞检测
      nodeSpacing: 15,//球大小
      gravity: 1,//中心引力
      damping: 0.3,//收敛，多迭代
      animate: true,
    }
  }
  if (type === 'dagre') return { type: 'dagre' as const, rankdir: 'TB' as const, nodesep: 30, ranksep: 50, animate: true }
  return { type: 'radial' as const, unitRadius: 80, preventOverlap: true, nodeSize: 28, focusNode: graphStore.nodes[0]?.id ?? '', animate: true }
}

// ── 初始化 G6 图谱实例 ──
function initGraph() {
  if (!graphRef.value || !graphStore.nodes.length) return
  if (graph) { graph.destroy(); graph = null }

  graph = new Graph({
    container: graphRef.value,
    width: graphRef.value.clientWidth,
    height: graphRef.value.clientHeight,
    data: {
      nodes: graphStore.nodes.map(n => ({
        id: n.id,
        style: {
          size: 28,
          fill: COLOR_MAP[n.labels[0]] ?? '#909399',
          labelText: n.properties.name,
          labelFill: '#1f1f1f',
          labelFontSize: 11,
          labelPlacement: 'bottom',
          labelOffsetY: 6,
        },
      })),
      edges: graphStore.edges.map(e => ({
        id: `${e.source_id}-${e.target_id}-${e.type}`,
        source: e.source_id,
        target: e.target_id,
      })),
    } as any,
    layout: getLayoutConfig('force'),
    node: {
      type: 'circle',
      style: {
        labelFill: '#1f1f1f',
        labelFontSize: 11,
        labelPlacement: 'bottom',
        labelOffsetY: 6,
      },
    },
    edge: {
      type: 'line',
      style: { stroke: '#d0d0d0', lineWidth: 1, opacity: 0.4 },
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', {
      type: 'click-select',
      onClick(event: any) {
        const id = event.target?.id
        if (id) handleNodeClick(id)
      },
    }],
  })

  graph.render()
}

// ── 切换布局 ──
function switchLayout(type: LayoutType) {
  currentLayout.value = type
  if (!graph) return
  if (type === 'radial') {
    applyRadialLayout()
    return
  }
  if (type === 'dagre') {
    applyDagreLayout()
    return
  }
  graph.setLayout(getLayoutConfig(type))
  graph.layout()
}

// ── 辐射布局：按节点类型分层、手动计算同心圆坐标 ──
function applyRadialLayout() {
  if (!graph || !graphRef.value) return

  const width = graphRef.value.clientWidth
  const height = graphRef.value.clientHeight
  const cx = width / 2
  const cy = height / 2

  // 按 label 分类
  const groups: Record<string, GraphNode[]> = { Position: [], Skill: [], Tool: [], _other: [] }
  for (const n of graphStore.nodes) {
    const label = n.labels[0]
    if (label === 'Position') groups.Position.push(n)
    else if (label === 'Skill') groups.Skill.push(n)
    else if (label === 'Tool') groups.Tool.push(n)
    else groups._other.push(n)
  }

  const rings: { nodes: GraphNode[]; radius: number }[] = [
    { nodes: groups.Position, radius: 50 },
    { nodes: groups.Skill,    radius: 180 },
    { nodes: groups.Tool,     radius: 310 },
    { nodes: groups._other,   radius: 440 },
  ]

  const posMap = new Map<string, { x: number; y: number }>()
  for (const ring of rings) {
    const count = ring.nodes.length
    if (count === 0) continue
    for (let i = 0; i < count; i++) {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2 // 从12点钟方向开始
      posMap.set(ring.nodes[i].id, {
        x: cx + ring.radius * Math.cos(angle),
        y: cy + ring.radius * Math.sin(angle),
      })
    }
  }

  const updatedNodes = graphStore.nodes.map(n => {
    const pos = posMap.get(n.id)
    return {
      id: n.id,
      style: {
        x: pos?.x ?? cx,
        y: pos?.y ?? cy,
      },
    }
  })

  graph.updateNodeData(updatedNodes)
  graph.draw()
}

// ── 层次布局：按节点类型分层，手动计算行列坐标 ──
function applyDagreLayout() {
  if (!graph || !graphRef.value) return

  const width = graphRef.value.clientWidth
  const height = graphRef.value.clientHeight

  // 从上到下的层级顺序
  const layerOrder: string[][] = [
    ['KnowledgeArea'],
    ['Position'],
    ['Skill'],
    ['Tool'],
    ['Certificate', 'LearningResource', 'Industry'],
  ]

  const numLayers = layerOrder.length
  const topPad = 60
  const bottomPad = 60
  const usableH = height - topPad - bottomPad
  const layerGap = numLayers > 1 ? usableH / (numLayers - 1) : 0

  const leftPad = 80
  const rightPad = 80
  const usableW = width - leftPad - rightPad

  const posMap = new Map<string, { x: number; y: number }>()

  for (let li = 0; li < layerOrder.length; li++) {
    const layerNodes = graphStore.nodes.filter(n => layerOrder[li].includes(n.labels[0]))
    const count = layerNodes.length
    const y = topPad + li * layerGap

    for (let i = 0; i < count; i++) {
      const x = count > 1
        ? leftPad + (i * usableW) / (count - 1)
        : width / 2
      posMap.set(layerNodes[i].id, { x, y })
    }
  }

  const updatedNodes = graphStore.nodes.map(n => {
    const pos = posMap.get(n.id)
    return {
      id: n.id,
      style: {
        x: pos?.x ?? width / 2,
        y: pos?.y ?? height / 2,
      },
    }
  })

  graph.updateNodeData(updatedNodes)
  graph.draw()
}

// ── 缩放 ──
function zoomIn() { graph?.zoomTo(graph.getZoom() * 1.3) }
function zoomOut() { graph?.zoomTo(graph.getZoom() * 0.7) }
function zoomFit() {
  if (!graph) return
  graph.fitView()
}

// ── 筛选变化 → 只更新样式 ──
watch(filteredNodeIds, () => {
  if (!graph) return
  const ids = filteredNodeIds.value
  const updatedNodes = graphStore.nodes.map(n => ({
    id: n.id,
    style: {
      opacity: ids.has(n.id) ? 0.1 : 1,
      size: ids.has(n.id) ? 8 : 28,
      labelText: ids.has(n.id) ? '' : n.properties.name,
    },
  }))
  graph.updateNodeData(updatedNodes)
  graph.draw()
})

// ── 窗口缩放时自适应画布尺寸 ──
function handleResize() {
  if (!graph || !graphRef.value) return
  graph.setSize(graphRef.value.clientWidth, graphRef.value.clientHeight)
}

// ── 挂载：拉取数据 → 初始化图谱 → 监听窗口缩放 ──
onMounted(async () => {
  await graphStore.fetchGraph()
  await nextTick()
  initGraph()
  window.addEventListener('resize', handleResize)
})

// ── 卸载：移除监听 → 销毁图谱实例 ──
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (graph) { graph.destroy(); graph = null }
})
</script>

<template>
  <MainLayout>
    <div class="graph-page">
      <div class="page-header">
        <h2>全景图谱</h2>
        <p class="page-desc">
          {{ graphStore.nodes.length }} 节点 · {{ graphStore.edges.length }} 关联
        </p>
      </div>

      <!-- ═══ 视图切换 Tab ═══ -->
      <div class="view-tabs">
        <el-radio-group
          :model-value="graphStore.viewMode"
          size="small"
          @change="(val: string) => graphStore.setViewMode(val as ViewMode)"
        >
          <el-radio-button
            v-for="vm in viewModeOptions"
            :key="vm.value"
            :value="vm.value"
          >
            {{ vm.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <div class="graph-layout">
        <!-- ═══ 左侧面板：筛选器 ═══ -->
        <aside class="left-panel">
          <!-- 图例 -->
          <div class="panel-section">
            <div class="section-title">图例</div>
            <div class="legend-list">
              <div
                v-for="(color, label) in COLOR_MAP"
                :key="label"
                class="legend-row"
              >
                <span
                  class="legend-dot"
                  :style="{ background: color }"
                />
                <span>{{ LABEL_NAMES[label] }}</span>
              </div>
            </div>
          </div>

          <!-- 技术栈筛选 -->
          <div class="panel-section">
            <div class="section-title">技术栈</div>
            <div class="filter-chips">
              <el-checkbox
                v-for="tech in techFilters"
                :key="tech"
                :model-value="selectedTech.includes(tech)"
                size="small"
                border
                @change="toggleFilter(selectedTech, tech)"
              >
                {{ tech }}
              </el-checkbox>
            </div>
          </div>
        </aside>

        <!-- ═══ 中间：图谱 ═══ -->
        <main class="graph-main">
          <div
            v-loading="graphStore.loading"
            class="graph-container"
          >
            <div
              ref="graphRef"
              class="graph-canvas"
            />
          </div>
        </main>

        <!-- ═══ 右侧面板：节点详情 ═══ -->
        <aside
          class="right-panel"
          :class="{ open: !!selectedNode }"
        >
          <template v-if="selectedNode">
            <div class="panel-section">
              <div class="detail-header">
                <div class="section-title">节点详情</div>
                <el-button
                  text
                  size="small"
                  type="danger"
                  @click="closeDetail"
                >
                  关闭
                </el-button>
              </div>

              <!-- 下钻面包屑 -->
              <div
                v-if="drillBreadcrumb.length > 1"
                class="drill-crumb"
              >
                <el-breadcrumb separator="→">
                  <el-breadcrumb-item
                    v-for="(item, idx) in drillBreadcrumb"
                    :key="item.id"
                  >
                    <a
                      href="#"
                      @click.prevent="goDrillBack(idx === drillBreadcrumb.length - 1 ? idx : idx)"
                    >{{ item.name }}</a>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>

              <!-- 节点基本信息 -->
              <div class="detail-info">
                <div class="detail-row">
                  <span
                    class="detail-dot"
                    :style="{ background: COLOR_MAP[selectedNode.labels[0]] ?? '#909399' }"
                  />
                  <strong>{{ selectedNode.properties.name }}</strong>
                </div>
                <div class="detail-row">
                  <span class="detail-label">类型</span>
                  <el-tag
                    size="small"
                    effect="plain"
                  >
                    {{ LABEL_NAMES[selectedNode.labels[0]] }}
                  </el-tag>
                </div>
                <div
                  v-if="selectedNode.properties.proficiency"
                  class="detail-row"
                >
                  <span class="detail-label">熟练度</span>
                  <span>{{ selectedNode.properties.proficiency }}</span>
                </div>
                <div
                  v-if="selectedNode.properties.source_count"
                  class="detail-row"
                >
                  <span class="detail-label">出现频次</span>
                  <span>{{ selectedNode.properties.source_count }}</span>
                </div>
                <div
                  v-if="selectedNode.properties.trend"
                  class="detail-row"
                >
                  <span class="detail-label">趋势</span>
                  <el-tag
                    size="small"
                    :type="selectedNode.properties.trend === 'rising' ? 'success' : selectedNode.properties.trend === 'declining' ? 'danger' : 'info'"
                  >
                    {{ selectedNode.properties.trend === 'rising' ? '上升' : selectedNode.properties.trend === 'declining' ? '下降' : '稳定' }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 岗位节点：跳转详情 -->
            <div
              v-if="selectedNode.labels.includes('Position')"
              class="panel-section"
            >
              <el-button
                type="primary"
                size="small"
                @click="$router.push(`/position/${encodeURIComponent(selectedNode.properties.name)}`)"
              >
                查看岗位详情
              </el-button>
            </div>

            <!-- 下钻区：领域 → 技能列表 -->
            <div
              v-if="isKnowledgeArea && relatedSkills.length"
              class="panel-section"
            >
              <div class="section-title">
                📋 包含技能 ({{ relatedSkills.length }})
              </div>
              <div class="related-list">
                <div
                  v-for="rn in relatedSkills"
                  :key="rn.id"
                  class="related-item"
                  @click="handleNodeClick(rn.id)"
                >
                  <span
                    class="legend-dot"
                    :style="{ background: COLOR_MAP[rn.labels[0]] ?? '#909399' }"
                  />
                  <span class="related-name">{{ rn.properties.name }}</span>
                  <el-tag
                    size="small"
                    effect="plain"
                  >
                    {{ LABEL_NAMES[rn.labels[0]] }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 下钻区：技能 → 知识点 -->
            <div
              v-if="isSkill && knowledgePoints.length"
              class="panel-section"
            >
              <div class="section-title">
                 知识点 ({{ knowledgePoints.length }})
              </div>
              <div class="kp-list">
                <div
                  v-for="kp in knowledgePoints"
                  :key="kp"
                  class="kp-item"
                >
                  <el-icon size="14"><Collection /></el-icon>
                  <span>{{ kp }}</span>
                </div>
              </div>
            </div>

            <!-- 通用：其他节点 → 全部关联 -->
            <div
              v-if="!isKnowledgeArea && !isSkill && relatedNodes.length"
              class="panel-section"
            >
              <div class="section-title">
                关联 ({{ relatedNodes.length }})
              </div>
              <div class="related-list">
                <div
                  v-for="rn in relatedNodes"
                  :key="rn.id"
                  class="related-item"
                  @click="handleNodeClick(rn.id)"
                >
                  <span
                    class="legend-dot"
                    :style="{ background: COLOR_MAP[rn.labels[0]] ?? '#909399' }"
                  />
                  <span class="related-name">{{ rn.properties.name }}</span>
                  <el-tag
                    size="small"
                    effect="plain"
                  >
                    {{ LABEL_NAMES[rn.labels[0]] }}
                  </el-tag>
                </div>
              </div>
            </div>
          </template>

          <div
            v-else
            class="panel-placeholder"
          >
            <el-icon size="36">
              <Aim />
            </el-icon>
            <p>点击节点查看详情</p>
            <p class="hint">支持技能粒度下钻</p>
          </div>
        </aside>
      </div>

      <!-- ═══ 底部工具栏 ═══ -->
      <footer class="bottom-toolbar">
        <!-- 布局切换 -->
        <div class="toolbar-group">
          <el-radio-group
            :model-value="currentLayout"
            size="small"
            @change="switchLayout"
          >
            <el-radio-button
              v-for="lo in layoutOptions"
              :key="lo.value"
              :value="lo.value"
            >
              {{ lo.label }}
            </el-radio-button>
          </el-radio-group>
        </div>

        <!-- 缩放控制 -->
        <div class="toolbar-group">
          <el-button-group>
            <el-button
              size="small"
              :icon="ZoomOut"
              @click="zoomOut"
            />
            <el-button
              size="small"
              :icon="Aim"
              @click="zoomFit"
            />
            <el-button
              size="small"
              :icon="ZoomIn"
              @click="zoomIn"
            />
          </el-button-group>
        </div>

        <!-- 搜索 -->
        <div class="toolbar-group search-group">
          <el-input
            v-model="searchKeyword"
            size="small"
            placeholder="搜索节点名称"
            :prefix-icon="Search"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
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
  height: calc(100vh - 80px);
}

.page-header {
  margin-bottom: 10px;
  padding: 0 8px;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 2px;
}

.page-desc {
  color: #909399;
  font-size: 13px;
  margin: 0;
}

/* ── 视图切换 Tab ── */
.view-tabs {
  padding: 0 8px 10px;
}

/* ── 三栏布局 ── */
.graph-layout {
  display: flex;
  flex: 1;
  gap: 10px;
  min-height: 0;
  padding: 0 8px;
}

/* ── 左侧面板 ── */
.left-panel {
  width: 180px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
}

.panel-section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.legend-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.filter-chips .el-checkbox {
  margin-right: 0;
  font-size: 12px;
}

/* ── 中间图谱 ── */
.graph-main {
  flex: 1;
  min-width: 0;
}

.graph-container {
  position: relative;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 500px;
}

/* ── 右侧面板 ── */
.right-panel {
  width: 240px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  transition: all 0.3s;
}

.right-panel:not(.open) {
  width: 120px;
}

.panel-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #c0c4cc;
  font-size: 13px;
  gap: 4px;
}

.panel-placeholder .hint {
  font-size: 11px;
  color: #dcdfe6;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.drill-crumb {
  margin-bottom: 10px;
  font-size: 12px;
}

.detail-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.detail-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.detail-label {
  color: #909399;
  min-width: 50px;
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
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.related-item:hover {
  background: #f5f7fa;
}

.related-name {
  flex: 1;
  color: #303133;
}

/* 知识点列表 */
.kp-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}

.kp-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
}

/* ── 底部工具栏 ── */
.bottom-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  margin: 8px 8px 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.toolbar-group {
  display: flex;
  align-items: center;
}

.search-group {
  margin-left: auto;
}

/* ── 响应式 ── */
@media (max-width: 1024px) {
  .left-panel {
    width: 140px;
    padding: 8px;
  }

  .right-panel {
    width: 200px;
  }

  .right-panel:not(.open) {
    width: 60px;
  }
}

@media (max-width: 768px) {
  .graph-layout {
    flex-direction: column;
  }

  .left-panel,
  .right-panel {
    width: 100%;
    flex-shrink: 1;
    max-height: 160px;
  }

  .right-panel:not(.open) {
    width: 100%;
    max-height: 60px;
  }

  .graph-canvas {
    min-height: 360px;
  }

  .bottom-toolbar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .search-group {
    margin-left: 0;
    width: 100%;
  }

  .search-group .el-input {
    width: 100% !important;
  }
}
</style>
