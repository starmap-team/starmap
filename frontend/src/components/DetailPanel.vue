<script setup lang="ts">
import { computed, ref, onUnmounted } from "vue"
import VChart from "vue-echarts"
import { Aim } from "@element-plus/icons-vue"
import { useGraphStore, type GraphNode } from "@/stores/graph"
import type { RadarChartOption } from "@/composables/home/useHomeInteractions"
import { CATEGORY_LABELS } from "@/constants/labels"
import { displayName } from "@/utils/graphColors"

function categoryLabel(raw: string | undefined | null): string {
  if (!raw) return '—'
  return CATEGORY_LABELS[raw] ?? raw
}

/** Count REQUIRES edges for a Position node */
function positionSkillCount(positionId: string): number {
  let count = 0
  for (const e of graphStore.allEdges) {
    if (e.source_id === positionId && e.type === 'REQUIRES') count++
  }
  return count
}

/** Find the parent KnowledgeArea name for a Position.
 * 从不进入前端 → 原实现恒返回"其他"。改为优先从当前展开上下文反查：
 * 用户从哪个领域展开该岗位，就显示哪个领域（真实导航上下文）。
 */
function parentKAName(positionId: string): string {
  if (graphStore.expandedKAId) {
    const positions = graphStore.positionsByKA.get(graphStore.expandedKAId) ?? []
    if (positions.some(p => p.id === positionId)) {
      return graphStore.expandedKAName || '其他'
    }
  }
  for (const [kaId, posList] of graphStore.positionsByKA) {
    if (posList.some(p => p.id === positionId)) {
      return graphStore.domains.find(d => d.id === kaId)?.name ?? '其他'
    }
  }
  for (const e of graphStore.allEdges) {
    if (e.source_id === positionId && (e.type === 'BELONGS_TO' || e.type === 'CONTAINS')) {
      const ka = graphStore.nodeMap.get(e.target_id)
      if (ka) return displayName(ka.properties)
    }
  }
  return '其他'
}

const props = defineProps<{
  selectedNode: GraphNode | null
  positionRadarOption: RadarChartOption | null
}>()

const emit = defineEmits<{
  close: []
  navigateToDetail: [node: GraphNode]
}>()

const graphStore = useGraphStore()

// ── 面板可调大小 ──
const panelWidth = ref(300)
const isResizing = ref(false)
let _activeMouseMove: ((e: MouseEvent) => void) | null = null
let _activeMouseUp: (() => void) | null = null

function onResizeStart(e: MouseEvent) {
  isResizing.value = true
  const startX = e.clientX
  const startWidth = panelWidth.value

  _activeMouseMove = (e: MouseEvent) => {
    const delta = startX - e.clientX
    panelWidth.value = Math.max(200, Math.min(500, startWidth + delta))
  }

  _activeMouseUp = () => {
    isResizing.value = false
    document.removeEventListener('mousemove', _activeMouseMove!)
    document.removeEventListener('mouseup', _activeMouseUp!)
  }

  document.addEventListener('mousemove', _activeMouseMove)
  document.addEventListener('mouseup', _activeMouseUp)
}

onUnmounted(() => {
  isResizing.value = false
  if (_activeMouseMove) document.removeEventListener('mousemove', _activeMouseMove)
  if (_activeMouseUp) document.removeEventListener('mouseup', _activeMouseUp)
})

const nodeType = computed(() => {
  if (!props.selectedNode) return ""
  if (props.selectedNode.labels.includes("KnowledgeArea")) return "KA"
  if (props.selectedNode.labels.includes("Position")) return "P"
  return "S"
})

const nodeTypeLabel = computed(() => {
  if (!props.selectedNode) return ""
  if (props.selectedNode.labels.includes("KnowledgeArea")) return "知识领域"
  if (props.selectedNode.labels.includes("Position")) return "岗位"
  return "技能"
})

const nodeTypeColor = computed(() => {
  if (!props.selectedNode) return "var(--chart-1)"
  if (props.selectedNode.labels.includes("KnowledgeArea")) return "var(--chart-3)"
  if (props.selectedNode.labels.includes("Position")) return "var(--chart-1)"
  return "var(--success)"
})

const relatedPositions = computed(() => {
  if (!props.selectedNode || !props.selectedNode.labels.includes("Skill")) return []
  const skillId = props.selectedNode.id
  const positionMap = new Map<string, { node: GraphNode; sharedCount: number }>()
  for (const e of graphStore.allEdges) {
    if (e.target_id === skillId && e.type === "REQUIRES") {
      const posNode = graphStore.nodeMap.get(e.source_id)
      if (!posNode) continue
      const existing = positionMap.get(posNode.id)
      if (existing) { existing.sharedCount++ } else { positionMap.set(posNode.id, { node: posNode, sharedCount: 1 }) }
    }
  }
  return Array.from(positionMap.values()).sort((a, b) => b.sharedCount - a.sharedCount).slice(0, 8)
})

const kaRelatedPositions = computed(() => {
  if (!props.selectedNode || !props.selectedNode.labels.includes("KnowledgeArea")) return []
  const kaId = props.selectedNode.id
  return graphStore.allNodes.filter(n => {
    if (!n.labels.includes("Position")) return false
 // Check both BELONGS_TO and CONTAINS edge types
    return graphStore.allEdges.some(e => 
      (e.source_id === n.id && e.target_id === kaId && (e.type === "BELONGS_TO" || e.type === "CONTAINS")) ||
      (e.source_id === kaId && e.target_id === n.id && (e.type === "CONTAINS"))
    )
  })
})

function close() { emit("close") }

function navigateToDetail(node: GraphNode) {
  graphStore.goToDetailLayer(node.id)
  emit("navigateToDetail", node)
}
</script>

<template>
  <aside
    class="detail-panel hover-lift"
    :class="{ open: !!selectedNode, resizing: isResizing }"
    :style="{ width: panelWidth + 'px' }"
  >
    <div
      class="dp-resize-handle"
      @mousedown.prevent="onResizeStart"
    />
    <template v-if="selectedNode">
      <div class="dp-header">
        <div
          class="dp-type-badge"
          :style="{ background: nodeTypeColor }"
        >
          {{ nodeType }}
        </div>
        <div class="dp-title-group">
          <h3 class="dp-title">
            {{ displayName(selectedNode.properties) }}
          </h3>
          <span class="dp-subtitle">{{ nodeTypeLabel }}</span>
        </div>
        <button
          class="dp-close"
          aria-label="关闭详情面板"
          @click="close"
        >
          ×
        </button>
      </div>
      <div
        v-if="positionRadarOption && selectedNode?.labels?.includes('Position')"
        class="dp-section"
      >
        <div class="dp-section-title">
          技能雷达
        </div>
        <VChart
          :option="positionRadarOption"
          class="radar-chart"
          autoresize
        />
      </div>
      <div class="dp-section">
        <div class="dp-section-title">
          属性
        </div>
        <div class="dp-props">
          <template v-if="selectedNode.labels.includes('Skill')">
            <div class="dp-prop-row">
              <span class="dp-prop-label">类别</span>
              <span class="dp-prop-value">{{ categoryLabel(selectedNode.properties.category) }}</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">趋势</span>
              <el-tag
                v-if="selectedNode.properties.trend"
                size="small"
                :type="selectedNode.properties.trend === 'rising' ? 'success' : selectedNode.properties.trend === 'declining' ? 'danger' : 'info'"
              >
                {{ selectedNode.properties.trend === 'rising' ? '↑ 上升' : selectedNode.properties.trend === 'declining' ? '↓ 下降' : '→ 平稳' }}
              </el-tag>
              <span
                v-else
                class="dp-prop-value"
              >暂无</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">来源数</span>
              <span class="dp-prop-value">{{ selectedNode.properties.source_count ?? 0 }} 个数据源</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">熟练度</span>
              <span class="dp-prop-value">{{ selectedNode.properties.proficiency ?? "暂无" }}</span>
            </div>
          </template>
          <template v-else-if="selectedNode.labels.includes('Position')">
            <div class="dp-prop-row">
              <span class="dp-prop-label">级别</span>
              <span class="dp-prop-value">{{ selectedNode.properties.level ?? "暂无" }}</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">需求技能数</span>
              <span class="dp-prop-value">{{ positionSkillCount(selectedNode.id) }} 项</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">关联岗位数</span>
              <span class="dp-prop-value">{{ selectedNode.properties.position_count ?? "—" }} 个</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">所属知识域</span>
              <span class="dp-prop-value">{{ parentKAName(selectedNode.id) }}</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">行业</span>
              <span class="dp-prop-value">{{ selectedNode.properties.industry || "未分类" }}</span>
            </div>
          </template>
          <template v-else>
            <div class="dp-prop-row">
              <span class="dp-prop-label">岗位数</span>
              <span class="dp-prop-value">{{ selectedNode.properties.position_count ?? 0 }}</span>
            </div>
            <div class="dp-prop-row">
              <span class="dp-prop-label">技能数</span>
              <span class="dp-prop-value">{{ selectedNode.properties.skill_count ?? 0 }}</span>
            </div>
          </template>
        </div>
      </div>
      <div
        v-if="relatedPositions.length"
        class="dp-section"
      >
        <div class="dp-section-title">
          相似岗位
        </div>
        <div class="dp-list">
          <div
            v-for="r in relatedPositions"
            :key="r.node.id"
            class="dp-list-item"
            role="button"
            tabindex="0"
            @click="navigateToDetail(r.node)"
          >
            <span class="dp-list-dot" />
            <span class="dp-list-name">{{ displayName(r.node.properties) }}</span>
            <span class="dp-list-meta">{{ r.sharedCount }} 共享技能</span>
          </div>
        </div>
      </div>
      <div
        v-if="kaRelatedPositions.length"
        class="dp-section"
      >
        <div class="dp-section-title">
          所属岗位
        </div>
        <div class="dp-list">
          <div
            v-for="p in kaRelatedPositions"
            :key="p.id"
            class="dp-list-item"
            role="button"
            tabindex="0"
            @click="navigateToDetail(p)"
          >
            <span class="dp-list-dot" />
            <span class="dp-list-name">{{ displayName(p.properties) }}</span>
          </div>
        </div>
      </div>
    </template>
    <div
      v-else
      class="dp-empty"
    >
      <el-icon
        size="28"
        color="var(--muted-foreground)"
        aria-hidden="true"
      >
        <Aim />
      </el-icon>
      <p>点击图谱节点查看详情</p>
      <p class="dp-empty-hint">
        或使用顶部搜索定位技能 / 岗位 / 领域
      </p>
    </div>
  </aside>
</template>

<style scoped>
.detail-panel {
  position: relative;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-5);
  transition: all var(--duration-slow) var(--ease-out);
  box-shadow: var(--shadow-xs);
}
.detail-panel:not(.open) {
  width: 160px !important;
  padding: var(--space-4);
}
.detail-panel.resizing {
  transition: none;
  user-select: none;
}
.dp-resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  background: transparent;
  transition: background var(--duration-fast);
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}
.dp-resize-handle:hover {
  background: var(--primary);
  opacity: 0.3;
}
.dp-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.dp-type-badge {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--font-size-xs);
  font-weight: 700;
  flex-shrink: 0;
  letter-spacing: -0.02em;
}
.dp-title-group { flex: 1; min-width: 0; }
.dp-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: var(--tracking-tight);
}
.dp-subtitle { font-size: var(--font-size-xs); color: var(--muted-foreground); }
.dp-close {
  width: 26px;
  height: 26px;
  border: none;
  background: none;
  color: var(--muted-foreground);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-lg);
  transition: all var(--duration-fast);
}
.dp-close:hover { color: var(--destructive); background: var(--destructive-ghost); }
.dp-section {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}
.dp-section:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.dp-section-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: var(--space-2);
}
.dp-props { display: flex; flex-direction: column; gap: var(--space-2); }
.dp-prop-row { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-size-sm); }
.dp-prop-label { color: var(--muted-foreground); }
.dp-prop-value { color: var(--foreground); font-weight: 500; font-variant-numeric: tabular-nums; }
.dp-list { display: flex; flex-direction: column; gap: 2px; max-height: 240px; overflow-y: auto; }
.dp-list-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all var(--duration-fast);
}
.dp-list-item:hover { background: var(--primary-ghost); }
.dp-list-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--chart-1); }
.dp-list-name { flex: 1; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dp-list-meta { font-size: var(--font-size-xs); color: var(--muted-foreground); flex-shrink: 0; }
.dp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: var(--space-2);
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}
.radar-chart { height: 200px; }
@media (max-width: 1024px) {
  .detail-panel { width: 240px; }
  .detail-panel:not(.open) { width: 100px; }
}
@media (max-width: 768px) {
  .detail-panel { width: 100%; max-height: 200px; }
  .detail-panel:not(.open) { width: 100%; max-height: 60px; }
}
</style>
