<script setup lang="ts">
/**
 * 学习路径流程图组件 — DAG 可视化
 * 展示技能前置关系和学习进度
 * 使用 G6 v5 的 antdag DAG 布局
 */
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { chartColors, cv, g6TooltipStyle } from '@/utils/chartTheme'
import { ensureG6Loaded } from '@/composables/useG6'
import { LEARNING_STATUS_LABELS } from '@/constants/labels'
import type { NodeData, EdgeData, G6ElementEvent, G6ElementDatum, Graph } from '@/types/g6'

interface PathNode {
  skill: string
  status: 'not_started' | 'in_progress' | 'mastered'
  prerequisites: string[]
  estimated_hours: number
  progress_pct: number
}

const props = defineProps<{
  path: PathNode[]
}>()

const containerRef = ref<HTMLElement | null>(null)

// G6 graph lifecycle (inlined from useG6Graph)
let graph: Graph | null = null
async function createGraph(options: Record<string, unknown>) {
  if (!containerRef.value) return
  if (graph) { graph.destroy(); graph = null }
  const w = containerRef.value.clientWidth || 700
  const h = containerRef.value.clientHeight || 300
  const GraphClass = await ensureG6Loaded()
  graph = new GraphClass({ container: containerRef.value, width: w, height: h, ...options })
  return graph
}
function handleResize() { if (graph && containerRef.value) graph.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight) }
onMounted(() => window.addEventListener('resize', handleResize))
onUnmounted(() => { window.removeEventListener('resize', handleResize); if (graph) { graph.destroy(); graph = null } })

const cc = chartColors()

const STATUS_COLORS: Record<string, string> = {
  not_started: cc.muted,
  in_progress: cc.warning,
  mastered: cc.success,
}

const STATUS_FILLS: Record<string, string> = {
  not_started: '#f1f5f9',
  in_progress: '#fef3c7',
  mastered: '#dcfce7',
}

const STATUS_LABELS = LEARNING_STATUS_LABELS

function buildGraphData() {
  const nodes: NodeData[] = []
  const edges: EdgeData[] = []
  const skillSet = new Set(props.path.map(p => p.skill))

  for (const item of props.path) {
    nodes.push({
      id: item.skill,
      data: {
        ...item,
        statusLabel: STATUS_LABELS[item.status] ?? item.status,
      },
      style: {
        fill: STATUS_FILLS[item.status] ?? STATUS_FILLS.not_started,
        stroke: STATUS_COLORS[item.status] ?? STATUS_COLORS.not_started,
        lineWidth: item.status === 'in_progress' ? 3 : 2,
        radius: 8,
        size: [140, 52],
        labelText: `${item.skill}\n${item.progress_pct}% · ${item.estimated_hours}h`,
        labelFill: cv('--foreground') || '#1c1917',
        labelFontSize: 11,
        labelPlacement: 'center' as const,
        labelLineHeight: 16,
        iconText: item.status === 'mastered' ? '✓' : item.status === 'in_progress' ? '◉' : '○',
        iconFill: STATUS_COLORS[item.status],
        iconFontSize: 14,
        iconPlacement: 'left-top' as const,
      },
    })

    for (const prereq of item.prerequisites) {
      if (skillSet.has(prereq)) {
        edges.push({
          source: prereq,
          target: item.skill,
          style: {
            stroke: cv('--border') || '#e7e5e4',
            lineWidth: 1.5,
            endArrow: true,
            endArrowSize: 6,
          },
        })
      }
    }
  }

  return { nodes, edges }
}

async function initGraph() {
  const g = await createGraph({
    autoFit: {
      type: 'view',
      options: { when: 'always' },
    },
    padding: [24, 24, 24, 24],
    layout: {
      type: 'dagre',
      rankdir: 'LR',
      nodesepFunc: () => 36,
      ranksepFunc: () => 100,
      controlPoints: true,
    },
    node: {
      style: {
        labelFill: cv('--foreground') || '#1c1917',
        labelFontSize: 11,
        labelPlacement: 'center' as const,
      },
    },
    edge: {
      style: {
        stroke: cv('--border') || '#e7e5e4',
        lineWidth: 1.5,
        endArrow: true,
        endArrowSize: 6,
        strokeOpacity: 0.6,
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas'],
    plugins: [
      {
        type: 'tooltip',
        enable: true,
        trigger: 'pointerenter',
        offset: [10, 10],
        style: g6TooltipStyle(),
        getContent: async (_event: G6ElementEvent, items: G6ElementDatum[]) => {
          if (!items?.length) return ''
          const d = items[0].data as unknown as PathNode & { statusLabel: string }
          return `<div style="font-weight:600;margin-bottom:4px">${d.skill}</div>
            <div>状态：${d.statusLabel}</div>
            <div>进度：${d.progress_pct}%</div>
            <div>预计：${d.estimated_hours}h</div>`
        },
      },
    ],
  })
  if (!g) return

  const graphData = buildGraphData()
  g.setData(graphData)
  g.render()
 // Ensure dagre layout fits viewport (defensive: small graphs may not trigger autoFit)
  if (typeof g.fitView === 'function') {
    try { await g.fitView() } catch (_) { /* ignore */ }
  }
}

watch(() => props.path, async () => {
  await nextTick()
  if (props.path.length) initGraph()
}, { deep: true })

onMounted(() => {
  if (props.path.length) initGraph()
})
</script>

<template>
  <div class="learning-path-flow">
    <div
      v-if="path.length"
      ref="containerRef"
      class="flow-container"
    />
    <div
      v-else
      class="custom-empty"
    >
      <div class="empty-icon-wrapper">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      </div>
      <p class="empty-text">
        暂无学习路径
      </p>
      <p class="empty-hint-text">
        创建学习计划后将展示技能学习路径图
      </p>
    </div>

    <!-- Legend -->
    <div
      v-if="path.length"
      class="flow-legend"
    >
      <span class="legend-item">
        <span
          class="legend-dot"
          :style="{ background: cc.muted }"
        />
        未开始
      </span>
      <span class="legend-item">
        <span
          class="legend-dot"
          :style="{ background: cc.warning }"
        />
        学习中
      </span>
      <span class="legend-item">
        <span
          class="legend-dot"
          :style="{ background: cc.success }"
        />
        已掌握
      </span>
    </div>
  </div>
</template>

<style scoped>
.learning-path-flow {
  width: 100%;
}
.flow-container {
  width: 100%;
  height: 380px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: var(--card);
}
.flow-legend {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding: var(--space-2);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-4);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
</style>

