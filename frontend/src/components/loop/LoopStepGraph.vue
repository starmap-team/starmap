<script setup lang="ts">
/**
 * LoopStepGraph — Step 3: Graph Update
 * Mini G6 graph container + legend.
 * The graph container ref is exposed so the parent (via useLoopGraph) can render into it.
 * Phase 07-02 D-05: also surfaces 新增节点/关系数 口径行.
 */
import { computed } from 'vue'
import type { StepResult } from '@/stores/loop'

const props = defineProps<{
  step: StepResult
  celebrated: boolean
}>()

const emit = defineEmits<{
  (e: 'graph-ref', el: HTMLElement | null): void
}>()

// D-05 口径拆解 — graph_sync 返回 nodes_written / edges_written
// (来自 graph_sync.py:140, 279-280 既有契约 key，不重命名)
const nodesWritten = computed<number | null>(() => {
  const d = props.step?.data as { nodes_written?: number; nodes?: number } | undefined
  if (!d) return null
  if (typeof d.nodes_written === 'number') return d.nodes_written
  if (typeof d.nodes === 'number') return d.nodes
  return null
})

const edgesWritten = computed<number | null>(() => {
  const d = props.step?.data as { edges_written?: number; edges?: number } | undefined
  if (!d) return null
  if (typeof d.edges_written === 'number') return d.edges_written
  if (typeof d.edges === 'number') return d.edges
  return null
})
</script>

<template>
  <div
    class="step-section animate-fade-in"
    :class="{ 'anim-celebrate': celebrated }"
  >
    <el-card
      shadow="never"
      class="step-card"
    >
      <template #header>
        <div class="sc-header">
          <h2 class="sc-title">
            <span class="step-num">3</span>
            图谱更新
          </h2>
          <div class="sc-metrics">
            <el-tag
              type="info"
              size="small"
              effect="plain"
            >
              新增节点: {{ nodesWritten ?? '—' }}
            </el-tag>
            <el-tag
              type="info"
              size="small"
              effect="plain"
            >
              新增关系: {{ edgesWritten ?? '—' }}
            </el-tag>
            <div
              v-if="step?.warning"
              class="degraded-badge"
            >
              ⚠ {{ step.warning }}
            </div>
          </div>
        </div>
      </template>

      <div class="graph-legend">
        <span class="legend-item">
          <span class="legend-dot legend-new" />
          新增节点
        </span>
        <span class="legend-item">
          <span class="legend-dot legend-existing" />
          已有节点
        </span>
        <span class="legend-item">
          <span class="legend-dot legend-edge" />
          关系边
        </span>
      </div>

      <div
        v-if="step?.status === 'running'"
        v-loading="true"
        style="min-height: 320px"
      />
      <div
        v-else
        :ref="(el: any) => emit('graph-ref', el as HTMLElement | null)"
        class="mini-graph-container"
      />
    </el-card>
  </div>
</template>

<style scoped>
/* ── Step Section ── */
.step-section {
  margin-bottom: var(--space-5);
  animation: fade-in-up 0.4s var(--ease-out);
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Step Card ── */
.step-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  position: relative;
  overflow: hidden;
}
.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  opacity: 0.8;
}

.sc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sc-metrics {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}
.sc-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--chart-2));
  color: white;
  font-size: var(--font-size-sm);
  font-weight: 700;
  flex-shrink: 0;
}

/* ── Step 3: Graph ── */
.graph-legend {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
  justify-content: center;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.legend-new {
  background: var(--success, #22c55e);
  box-shadow: 0 0 6px color-mix(in srgb, var(--success, #22c55e) 50%, transparent);
}
.legend-existing {
  background: var(--primary);
}
.legend-edge {
  background: var(--border);
  border-radius: 2px;
  height: 2px;
  width: 14px;
}
.mini-graph-container {
  width: 100%;
  height: 320px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  overflow: hidden;
  background: color-mix(in srgb, var(--card) 95%, var(--foreground));
}
.degraded-badge {
  font-size: var(--font-size-xs);
  color: var(--warning);
  background: color-mix(in srgb, var(--warning) 10%, var(--card));
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid color-mix(in srgb, var(--warning) 20%, var(--border));
}

/* ── Celebration Effect ── */
.anim-celebrate {
  animation: loopCelebrate 0.7s var(--ease-out) both;
}
@keyframes loopCelebrate {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 40%, transparent); }
  50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--success) 0%, transparent); }
  100% { box-shadow: 0 0 0 0 transparent; }
}
</style>
