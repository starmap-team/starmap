<script setup lang="ts">
/**
 * 学习路径流程图组件 — DAG 可视化
 * 展示技能前置关系和学习进度
 * 使用 G6 v5 的 antdag DAG 布局
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

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
let graph: any = null
let G6Graph: any = null

const STATUS_COLORS: Record<string, string> = {
  not_started: '#94a3b8',
  in_progress: '#d97706',
  mastered: '#16a34a',
}

const STATUS_FILLS: Record<string, string> = {
  not_started: '#f1f5f9',
  in_progress: '#fef3c7',
  mastered: '#dcfce7',
}

const STATUS_LABELS: Record<string, string> = {
  not_started: '未开始',
  in_progress: '学习中',
  mastered: '已掌握',
}

async function ensureG6Loaded() {
  if (!G6Graph) {
    const g6 = await import('@antv/g6')
    G6Graph = g6.Graph
  }
  return G6Graph
}

function cv(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function buildGraphData() {
  const nodes: any[] = []
  const edges: any[] = []
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
  if (!containerRef.value) return
  if (graph) { graph.destroy(); graph = null }

  const container = containerRef.value
  const width = container.clientWidth || 700
  const height = container.clientHeight || 400

  try {
    const GraphClass = await ensureG6Loaded()
    graph = new GraphClass({
      container,
      width,
      height,
      layout: {
        type: 'dagre',
        rankdir: 'LR',
        nodesep: 30,
        ranksep: 80,
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
          style: {
            background: cv('--card') || '#ffffff',
            borderRadius: '10px',
            boxShadow: '0 6px 20px rgba(0,0,0,0.1)',
            padding: '8px 12px',
            fontSize: '12px',
            border: '1px solid ' + (cv('--border') || '#e7e5e4'),
            color: cv('--foreground') || '#1c1917',
          },
          getContent: (_event: any, items: any[]) => {
            if (!items?.length) return ''
            const d = items[0].data
            return `<div style="font-weight:600;margin-bottom:4px">${d.skill}</div>
              <div>状态：${d.statusLabel}</div>
              <div>进度：${d.progress_pct}%</div>
              <div>预计：${d.estimated_hours}h</div>`
          },
        },
      ],
    })

    const graphData = buildGraphData()
    graph.setData(graphData)
    graph.render()
  } catch (err) {
    console.error('[LearningPathFlow] Failed to initialize graph:', err)
  }
}

function handleResize() {
  if (graph && containerRef.value) {
    const w = containerRef.value.clientWidth
    const h = containerRef.value.clientHeight
    graph.setSize(w, h)
  }
}

watch(() => props.path, async () => {
  await nextTick()
  if (props.path.length) initGraph()
}, { deep: true })

onMounted(() => {
  if (props.path.length) initGraph()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (graph) { graph.destroy(); graph = null }
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
        <span class="legend-dot" style="background: #94a3b8" />
        未开始
      </span>
      <span class="legend-item">
        <span class="legend-dot" style="background: #d97706" />
        学习中
      </span>
      <span class="legend-item">
        <span class="legend-dot" style="background: #16a34a" />
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
