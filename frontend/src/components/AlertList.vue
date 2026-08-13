<script setup lang="ts">
/**
 * 异常告警列表组件 — Sprint 1.2
 * 展示告警级别/类型/时间/处理状态
 */
import { computed } from 'vue'
import { chartColors } from '@/utils/chartTheme'
import { asTagType } from '@/utils/element'
import { formatRelativeTime } from '@/utils/formatTime'

export interface AlertItem {
  id: string | number
  level?: 'info' | 'warning' | 'error' | 'critical'
  type?: string
  message?: string
  created_at?: string
  status?: 'pending' | 'processing' | 'resolved' | 'ignored'
}

defineProps<{
  alerts: AlertItem[]
}>()

const emit = defineEmits<{
  (e: 'resolve', id: string | number): void
  (e: 'ignore', id: string | number): void
}>()

const levelConfig = computed(() => {
  const colors = chartColors()
  return {
    info:     { type: 'info' as const,    color: colors.info,    label: '信息' },
    warning:  { type: 'warning' as const, color: colors.warning, label: '警告' },
    error:    { type: 'danger' as const,  color: colors.danger,  label: '错误' },
    critical: { type: 'danger' as const,  color: colors.danger,  label: '严重' },
  }
})

function getLevelType(level: string): string {
  return (levelConfig.value as Record<string, { type: string; label: string }>)[level]?.type ?? 'info'
}

function getLevelLabel(level: string): string {
  return (levelConfig.value as Record<string, { type: string; label: string }>)[level]?.label ?? level
}

const statusConfig: Record<string, { type: string; label: string }> = {
  pending:    { type: 'warning', label: '待处理' },
  processing: { type: 'info',    label: '处理中' },
  resolved:   { type: 'success', label: '已解决' },
  ignored:    { type: 'info',    label: '已忽略' },
}

const typeIconMap: Record<string, string> = {
  quality:    'DataLine',
  crawl:      'Download',
  duplicate:  'CopyDocument',
  timeout:    'Clock',
  auth:       'Lock',
  system:     'Monitor',
}

// ── 告警类型中文化（全盘友好性）: 内部 type 标识 → 用户友好中文 ──
const typeConfig: Record<string, { type: string; label: string }> = {
  quality:   { type: 'warning', label: '质量' },
  crawl:     { type: 'info',    label: '采集' },
  duplicate: { type: 'info',    label: '去重' },
  timeout:   { type: 'danger',  label: '超时' },
  auth:      { type: 'danger',  label: '认证' },
  system:    { type: 'info',    label: '系统' },
}

function getTypeLabel(type: string): string {
  return typeConfig[type]?.label ?? type
}

</script>

<template>
  <div class="alert-list">
    <el-table
      :data="alerts"
      stripe
      size="small"
      max-height="400"
      empty-text="暂无告警信息"
      row-class-name="alert-row"
    >
      <el-table-column
        label="级别"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="getLevelType(row.level)"
            size="small"
            effect="dark"
            round
          >
            {{ getLevelLabel(row.level) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        label="类型"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          <div class="type-cell">
            <el-icon
              :size="14"
              class="type-icon"
            >
              <component :is="typeIconMap[row.type] ?? 'Warning'" />
            </el-icon>
            <span>{{ getTypeLabel(row.type) }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        prop="message"
        label="告警信息"
        min-width="200"
        show-overflow-tooltip
      />

      <el-table-column
        label="时间"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          <span class="time-text">{{ formatRelativeTime(row.created_at) }}</span>
        </template>
      </el-table-column>

      <el-table-column
        label="状态"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="asTagType(statusConfig[row.status]?.type)"
            size="small"
            effect="plain"
            round
          >
            {{ statusConfig[row.status]?.label ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        label="操作"
        width="140"
        align="center"
      >
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'pending' || row.status === 'processing'"
            size="small"
            type="success"
            plain
            @click="emit('resolve', row.id)"
          >
            解决
          </el-button>
          <el-button
            v-if="row.status === 'pending'"
            size="small"
            type="info"
            plain
            @click="emit('ignore', row.id)"
          >
            忽略
          </el-button>
          <span
            v-if="row.status === 'resolved' || row.status === 'ignored'"
            class="action-done"
          >--</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.alert-list {
  width: 100%;
}
.type-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}
.type-icon {
  color: var(--muted-foreground);
}
.time-text {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}
.action-done {
  color: var(--muted-foreground);
  font-size: var(--font-size-xs);
}
</style>
