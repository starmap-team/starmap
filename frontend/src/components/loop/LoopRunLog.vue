<script setup lang="ts">
/**
 * LoopRunLog — Run Log + History
 * Log entries + duration chart + history table.
 */
import { computed } from 'vue'
import type { LoopRun, LoopHistoryItem } from '@/stores/loop'

const props = defineProps<{
  currentRun: LoopRun | null
  history: LoopHistoryItem[]
  totalDuration: number
}>()

// ── Run log ──
const runLog = computed(() => {
  if (!props.currentRun) return []
  const log: { time: string; message: string; type: string }[] = []
  for (const step of props.currentRun.steps) {
    if (step.status === 'success') {
      log.push({ time: formatDuration(step.duration_ms), message: `✓ Step ${step.step}: ${step.name} 完成`, type: 'success' })
    } else if (step.status === 'degraded') {
      log.push({ time: formatDuration(step.duration_ms), message: `⚠ Step ${step.step}: ${step.name} 降级 — ${step.warning ?? '部分数据不可用'}`, type: 'warning' })
    } else if (step.status === 'failed') {
      log.push({ time: '', message: `✕ Step ${step.step}: ${step.name} 失败 — ${step.error ?? '未知错误'}`, type: 'error' })
    } else if (step.status === 'running') {
      log.push({ time: '', message: `⟳ Step ${step.step}: ${step.name} 执行中...`, type: 'info' })
    }
  }
  return log
})

function formatDuration(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// ── 运行状态中文化（全盘友好性）: completed/partial/failed 等内部标识 → 中文 ──
const RUN_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  partial: '部分完成',
  failed: '失败',
  running: '执行中',
  pending: '等待中',
  cancelled: '已取消',
  success: '成功',
  degraded: '降级',
}

function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status
}
</script>

<template>
  <!-- Run Log + Duration Stats -->
  <div
    v-if="currentRun && runLog.length > 0"
    class="step-section animate-fade-in"
  >
    <el-card
      shadow="never"
      class="step-card run-log-card"
    >
      <template #header>
        <div class="sc-header">
          <h2 class="sc-title">
            运行日志
          </h2>
          <div class="total-duration">
            总耗时: <strong>{{ formatDuration(totalDuration) }}</strong>
          </div>
        </div>
      </template>

      <div class="log-entries">
        <div
          v-for="(entry, idx) in runLog"
          :key="idx"
          class="log-entry"
          :class="`log-${entry.type}`"
        >
          <span class="log-message">{{ entry.message }}</span>
          <span
            v-if="entry.time"
            class="log-time"
          >{{ entry.time }}</span>
        </div>
      </div>

      <!-- Duration bar chart (simple) -->
      <div class="duration-bars">
        <div
          v-for="step in currentRun.steps"
          :key="step.step"
          class="dur-bar-row"
        >
          <span class="dur-label">Step {{ step.step }}</span>
          <div class="dur-bar-track">
            <div
              class="dur-bar-fill"
              :class="`dur-${step.status}`"
              :style="{ width: step.duration_ms ? `${Math.max(5, (step.duration_ms / (totalDuration || 1)) * 100)}%` : '0%' }"
            />
          </div>
          <span class="dur-value">{{ formatDuration(step.duration_ms) }}</span>
        </div>
      </div>
    </el-card>
  </div>

  <!-- History -->
  <div
    v-if="history.length > 0 && !currentRun"
    class="step-section animate-fade-in"
  >
    <el-card
      shadow="never"
      class="step-card"
    >
      <template #header>
        <h2 class="sc-title">
          历史记录
        </h2>
      </template>
      <el-table
        :data="history"
        stripe
        size="small"
        empty-text="暂无数据"
      >
        <el-table-column
          prop="run_id"
          label="运行 ID"
          min-width="160"
        />
        <el-table-column
          prop="target_position"
          label="目标岗位"
          min-width="120"
        />
        <el-table-column
          label="状态"
          width="90"
          align="center"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'completed' ? 'success' : row.status === 'partial' ? 'warning' : 'info'"
              size="small"
            >
              {{ runStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="步骤"
          width="80"
          align="center"
        >
          <template #default="{ row }">
            {{ (row.steps ?? []).filter((s: any) => s.status === 'success').length }}/{{ (row.steps ?? []).length }}
          </template>
        </el-table-column>
        <el-table-column
          label="耗时"
          width="90"
          align="center"
        >
          <template #default="{ row }">
            {{ formatDuration((row.total_duration_seconds ?? 0) * 1000) }}
          </template>
        </el-table-column>
        <el-table-column
          label="时间"
          width="160"
        >
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '—' }}
          </template>
        </el-table-column>
      </el-table>
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

/* ── Run Log ── */
.run-log-card::before {
  background: linear-gradient(90deg, var(--chart-2), var(--chart-1));
}
.total-duration {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}
.log-entries {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: color-mix(in srgb, var(--foreground) 3%, var(--card));
  border-radius: var(--radius-lg);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: var(--font-size-xs);
}
.log-entry {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
}
.log-message {
  color: var(--foreground);
}
.log-time {
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.log-success .log-message { color: var(--success); }
.log-warning .log-message { color: var(--warning); }
.log-error .log-message { color: var(--danger); }
.log-info .log-message { color: var(--primary); }

/* ── Duration Bars ── */
.duration-bars {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dur-bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.dur-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  width: 56px;
  flex-shrink: 0;
  font-weight: 500;
}
.dur-bar-track {
  flex: 1;
  height: 8px;
  background: var(--muted);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dur-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.6s var(--ease-out);
  min-width: 4px;
}
.dur-success { background: linear-gradient(90deg, var(--success), var(--success, #22c55e)); }
.dur-degraded { background: linear-gradient(90deg, var(--warning), var(--warning, #f59e0b)); }
.dur-failed { background: linear-gradient(90deg, var(--destructive), var(--destructive, #ef4444)); }
.dur-running { background: linear-gradient(90deg, var(--primary), var(--chart-2)); }
.dur-waiting { background: var(--border); }
.dur-value {
  font-size: 11px;
  color: var(--muted-foreground);
  width: 50px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
</style>
