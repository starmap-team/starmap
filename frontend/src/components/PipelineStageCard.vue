<script setup lang="ts">
/**
 * 流水线阶段卡片组件
 * 展示单个 ETL 阶段的状态、进度、耗时、错误数、重试次数
 * 支持 failed 状态下的重试按钮
 */
import { computed } from 'vue'
import { chartColors } from '@/utils/chartTheme'
import { STAGE_LABELS } from '@/stores/pipeline'

export interface StageData {
  name: string
  status: 'waiting' | 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  duration_ms: number
  records_processed: number
  errors: number
  progress: number
  retry_count?: number
  depends_on?: string[]
}

const props = defineProps<{
  stage: StageData
}>()

const emit = defineEmits<{
  retry: [stageName: string]
}>()

const statusConfig = computed(() => {
  const colors = chartColors()
  switch (props.stage.status) {
    case 'running':
      return { color: colors.info, label: '运行中', icon: '⏳' }
    case 'completed':
      return { color: colors.success, label: '已完成', icon: '✓' }
    case 'failed':
      return { color: colors.danger, label: '失败', icon: '✕' }
    case 'skipped':
      return { color: '#d1d5db', label: '已跳过', icon: '—' }
    case 'pending':
      return { color: colors.muted, label: '待执行', icon: '○' }
    case 'waiting':
    default:
      return { color: colors.muted, label: '等待中', icon: '○' }
  }
})

const stageLabel = computed(() => STAGE_LABELS[props.stage.name] || props.stage.name)

const formattedDuration = computed(() => {
  const ms = props.stage.duration_ms
  if (ms <= 0) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = ((ms % 60000) / 1000).toFixed(0)
  return `${min}m ${sec}s`
})

const formattedRecords = computed(() => {
  const n = props.stage.records_processed
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
})
</script>

<template>
  <el-card
    shadow="hover"
    class="stage-card"
    :class="[`stage-${stage.status}`]"
  >
    <div class="stage-header">
      <div class="stage-status-indicator">
        <span
          class="status-dot"
          :style="{ background: statusConfig.color }"
        />
        <span
          v-if="stage.status === 'running'"
          class="status-pulse"
          :style="{ borderColor: statusConfig.color }"
        />
      </div>
      <div class="stage-info">
        <div class="stage-name">
          {{ stageLabel }}
        </div>
        <div
          class="stage-status-label"
          :style="{ color: statusConfig.color }"
        >
          <span class="status-icon">{{ statusConfig.icon }}</span>
          {{ statusConfig.label }}
          <span
            v-if="stage.retry_count && stage.retry_count > 0"
            class="retry-badge"
          >重试×{{ stage.retry_count }}</span>
        </div>
      </div>
      <el-button
        v-if="stage.status === 'failed'"
        size="small"
        type="warning"
        link
        @click="emit('retry', stage.name)"
      >
        重试
      </el-button>
    </div>

    <div
      v-if="stage.status === 'running'"
      class="stage-progress"
    >
      <el-progress
        :percentage="stage.progress"
        :stroke-width="6"
        :color="statusConfig.color"
        :show-text="false"
      />
      <span class="progress-text">{{ stage.progress }}%</span>
    </div>

    <div class="stage-metrics">
      <div class="metric">
        <span class="metric-label">耗时</span>
        <span class="metric-value">{{ formattedDuration }}</span>
      </div>
      <div class="metric">
        <span class="metric-label">处理量</span>
        <span class="metric-value">{{ formattedRecords }}</span>
      </div>
      <div
        v-if="stage.errors > 0"
        class="metric metric-error"
      >
        <span class="metric-label">错误</span>
        <span
          class="metric-value"
          :style="{ color: chartColors().danger }"
        >{{ stage.errors }}</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.stage-card {
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
  min-width: 180px;
}
.stage-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.stage-running {
  border-left: 3px solid var(--info);
}
.stage-completed {
  border-left: 3px solid var(--success);
}
.stage-failed {
  border-left: 3px solid var(--destructive);
}
.stage-pending {
  border-left: 3px solid var(--muted-foreground);
  opacity: 0.8;
}
.stage-skipped {
  border-left: 3px solid #d1d5db;
  opacity: 0.5;
}
.stage-waiting {
  border-left: 3px solid var(--muted-foreground);
  opacity: 0.7;
}
.stage-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.stage-status-indicator {
  position: relative;
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}
.status-dot {
  display: block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: relative;
  z-index: 1;
}
.status-pulse {
  position: absolute;
  top: -4px;
  left: -4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid;
  animation: pulse-ring 1.5s ease-out infinite;
}
@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.6); opacity: 0; }
}
.stage-info {
  flex: 1;
  min-width: 0;
}
.stage-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}
.stage-status-label {
  font-size: var(--font-size-xs);
  font-weight: 500;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.status-icon {
  font-size: 11px;
  margin-right: 2px;
}
.retry-badge {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--warning) 15%, transparent);
  color: var(--warning);
  font-weight: 600;
}
.stage-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.progress-text {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.stage-metrics {
  display: flex;
  gap: var(--space-4);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.metric-label {
  font-size: 10px;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.metric-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}
.metric-error .metric-value {
  color: var(--destructive);
}
</style>
