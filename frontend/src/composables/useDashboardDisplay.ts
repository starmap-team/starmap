/**
 * DataDashboard display maps + time formatter + pipeline default stages.
 * Extracted from DataDashboard.vue (Phase 7 D round 9).
 * Pure helpers/computeds. Color maps depend on chartColors() so they are
 * computed at call time.
 */
import { computed, type ComputedRef } from 'vue'
import { chartColors } from '@/utils/chartTheme'
import type { useDashboardStore } from '@/stores/dashboard'

type DashboardStore = ReturnType<typeof useDashboardStore>

export interface PipelineStage {
  stage: string
  status: 'waiting' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  records_processed: number
  progress: number
}

const DEFAULT_PIPELINE_STAGES: ReadonlyArray<PipelineStage> = [
  { stage: '采集', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '去重', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '清洗', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '入库', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '图谱', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
]

export function useDashboardDisplay(store: DashboardStore): {
  pipelineStages: ComputedRef<PipelineStage[]>
  statusColor: ComputedRef<Record<string, string>>
  eventIcon: ComputedRef<Record<string, string>>
  eventSeverityColor: ComputedRef<Record<string, string>>
  formatTime: (ts: string) => string
} {
  const pipelineStages: ComputedRef<PipelineStage[]> = computed(() => {
    if (store.pipelineTimeline.length) return store.pipelineTimeline as PipelineStage[]
    return [...DEFAULT_PIPELINE_STAGES]
  })

  const statusColor: ComputedRef<Record<string, string>> = computed(() => {
    const c = chartColors()
    return {
      running: c.info,
      completed: c.success,
      failed: c.danger,
      waiting: c.muted + '33',
    }
  })

  const eventIcon: ComputedRef<Record<string, string>> = computed(() => ({
    skill_update: '💡',
    match_event: '🎯',
    graph_update: '🔗',
    pipeline_event: '⚙️',
    extraction: '📄',
  }))

  const eventSeverityColor: ComputedRef<Record<string, string>> = computed(() => {
    const c = chartColors()
    return {
      info: c.chart[0] + '99',
      success: c.success + '99',
      warning: c.warning + '99',
      error: c.danger + '99',
    }
  })

  function formatTime(ts: string): string {
    if (!ts) return ''
    const d = new Date(ts)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  }

  return { pipelineStages, statusColor, eventIcon, eventSeverityColor, formatTime }
}
