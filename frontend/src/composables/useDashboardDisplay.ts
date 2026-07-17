/**
 * DataDashboard display maps + time formatter + pipeline default stages.
 * Extracted from DataDashboard.vue (Phase 7 D round 9).
 * Pure helpers/computeds. Color maps depend on chartColors() so they are
 * computed at call time.
 */
import { computed, type ComputedRef } from 'vue'
import { chartColors } from '@/utils/chartTheme'
import type { useDashboardStore, PipelineTimelineItem } from '@/stores/dashboard'

type DashboardStore = ReturnType<typeof useDashboardStore>

const DEFAULT_PIPELINE_STAGES: ReadonlyArray<PipelineTimelineItem> = [
  { stage: '采集', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '去重', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '清洗', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '入库', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '图谱', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
]

export function stageIcon(status: string): string {
  switch (status) {
    case 'running': return '●'
    case 'completed': return '✓'
    case 'failed': return '✗'
    default: return '○'
  }
}

export function useDashboardDisplay(store: DashboardStore): {
  pipelineStages: ComputedRef<PipelineTimelineItem[]>
  statusColor: ComputedRef<Record<string, string>>
  eventIcon: Record<string, string>
  eventSeverityColor: Record<string, string>
  eventTypeColor: ComputedRef<Record<string, string>>
  formatTime: (ts: string) => string
  stageIcon: (status: string) => string
} {
  const colors = chartColors()

  const pipelineStages: ComputedRef<PipelineTimelineItem[]> = computed(() => {
    if (store.pipelineTimeline.length) return store.pipelineTimeline as PipelineTimelineItem[]
    return [...DEFAULT_PIPELINE_STAGES]
  })

  const statusColor: ComputedRef<Record<string, string>> = computed(() => ({
    running: colors.info,
    completed: colors.success,
    failed: colors.danger,
    waiting: colors.muted + '33',
  }))

  const eventIcon: Record<string, string> = {
    skill_update: '💡',
    match_event: '🎯',
    graph_update: '🔗',
    pipeline_event: '⚙️',
    extraction: '📄',
  }

  const eventSeverityColor: Record<string, string> = {
    info: colors.chart[0] + '99',
    success: colors.success + '99',
    warning: colors.warning + '99',
    error: colors.danger + '99',
  }

  // Map event types -> accent color for the left border indicator.
  // CSS variables are read at call time so dark/light theme switches apply.
  const eventTypeColor: ComputedRef<Record<string, string>> = computed(() => ({
    pipeline_update: 'var(--info)',
    quality_alert: 'var(--success)',
    data_milestone: 'var(--warning)',
    extraction_complete: 'var(--chart-3)',
    skill_update: 'var(--chart-2)',
    graph_update: 'var(--chart-1)',
    match_event: 'var(--chart-4)',
    pipeline_event: 'var(--info)',
    extraction: 'var(--chart-3)',
  }))

  function formatTime(ts: string): string {
    if (!ts) return ''
    const d = new Date(ts)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    if (isToday) return `${h}:${m}:${s}`
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${mo}-${day} ${h}:${m}`
  }

  return { pipelineStages, statusColor, eventIcon, eventSeverityColor, eventTypeColor, formatTime, stageIcon }
}
