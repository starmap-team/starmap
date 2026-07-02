<script setup lang="ts">
/**
 * 职业路径规划图组件 — G6 DAG 可视化
 * 展示从当前岗位到目标岗位的职业晋升路径
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

interface CareerStep {
  position: string
  skills_required: string[]
  estimated_time: string
  probability: number
}

const props = defineProps<{
  path: CareerStep[]
}>()

const containerRef = ref<HTMLElement | null>(null)
let graph: any = null
let G6Graph: any = null

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

function getProbabilityColor(prob: number): string {
  if (prob >= 0.7) return '#16a34a'
  if (prob >= 0.4) return '#d97706'
  return '#dc2626'
}

function getProbabilityFill(prob: number): string {
  if (prob >= 0.7) return '#dcfce7'
  if (prob >= 0.4) return '#fef3c7'
  return '#fee2e2'
}

function buildGraphData() {
  const nodes: any[] = []
  const edges: any[] = []

  for (let i = 0; i < props.path.length; i++) {
    const step = props.path[i]
    const isStart = i === 0
    const isEnd = i === props.path.length - 1
    const probColor = getProbabilityColor(step.probability)
    const probFill = getProbabilityFill(step.probability)

    nodes.push({
      id: `step-${i}`,
      data: {
        ...step,
        index: i,
      },
      style: {
        fill: isStart ? '#dbeafe' : isEnd ? '#dcfce7' : probFill,
        stroke: isStart ? '#3b82f6' : isEnd ? '#16a34a' : probColor,
        lineWidth: isStart || isEnd ? 3 : 2,
        radius: 10,
        size: [160, 60],
        labelText: `${step.position}\n${step.estimated_time} · ${(step.probability * 100).toFixed(0)}%`,
        labelFill: cv('--foreground') || '#1c1917',
        labelFontSize: 11,
        labelPlacement: 'center' as const,
        labelLineHeight: 16,
      },
    })

    if (i > 0) {
      edges.push({
        source: `step-${i - 1}`,
        target: `step-${i}`,
        style: {
          stroke: cv('--border') || '#e7e5e4',
          lineWidth: 2,
          endArrow: true,
          endArrowSize: 8,
          strokeOpacity: 0.7,
        },
      })
    }
  }

  return { nodes, edges }
}

async function initGraph() {
  if (!containerRef.value) return
  if (graph) { graph.destroy(); graph = null }

  const container = containerRef.value
  const width = container.clientWidth || 700
  const height = container.clientHeight || 300

  try {
    const GraphClass = await ensureG6Loaded()
    graph = new GraphClass({
      container,
      width,
      height,
      layout: {
        type: 'dagre',
        rankdir: 'LR',
        nodesep: 25,
        ranksep: 100,
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
          lineWidth: 2,
          endArrow: true,
          endArrowSize: 8,
          strokeOpacity: 0.7,
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
            const skills = d.skills_required?.slice(0, 5).join('、') ?? '-'
            return `<div style="font-weight:600;margin-bottom:4px">${d.position}</div>
              <div>预计时间：${d.estimated_time}</div>
              <div>晋升概率：${(d.probability * 100).toFixed(0)}%</div>
              <div>核心技能：${skills}</div>`
          },
        },
      ],
    })

    const graphData = buildGraphData()
    graph.setData(graphData)
    graph.render()
  } catch (err) {
    console.error('[CareerPathGraph] Failed to initialize graph:', err)
  }
}

function handleResize() {
  if (graph && containerRef.value) {
    graph.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight)
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
  <div class="career-path-graph">
    <div
      v-if="path.length"
      ref="containerRef"
      class="graph-container"
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
          <circle
            cx="12"
            cy="12"
            r="10"
          />
          <path d="M12 8v4l3 3" />
        </svg>
      </div>
      <p class="empty-text">
        暂无职业路径数据
      </p>
      <p class="empty-hint-text">
        选择目标岗位后将规划职业晋升路径
      </p>
    </div>

    <!-- Step details below graph -->
    <div
      v-if="path.length"
      class="path-steps"
    >
      <div
        v-for="(step, idx) in path"
        :key="idx"
        class="path-step-item"
      >
        <div
          class="step-dot"
          :style="{ background: getProbabilityColor(step.probability) }"
        />
        <div class="step-info">
          <div class="step-position">
            {{ step.position }}
          </div>
          <div class="step-meta">
            <span>{{ step.estimated_time }}</span>
            <span class="step-prob" :style="{ color: getProbabilityColor(step.probability) }">
              {{ (step.probability * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
        <el-tag
          v-if="step.skills_required?.length"
          size="small"
          effect="plain"
          type="info"
        >
          {{ step.skills_required.slice(0, 3).join('、') }}{{ step.skills_required.length > 3 ? '...' : '' }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<style scoped>
.career-path-graph {
  width: 100%;
}
.graph-container {
  width: 100%;
  height: 300px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: var(--card);
}

.path-steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
.path-step-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast);
}
.path-step-item:hover {
  background: color-mix(in srgb, var(--primary) 3%, var(--card));
  border-color: color-mix(in srgb, var(--primary) 20%, var(--border));
}
.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.step-info {
  flex: 1;
  min-width: 0;
}
.step-position {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
}
.step-meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.step-prob {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
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
