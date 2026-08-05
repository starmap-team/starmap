/**
 * 数据流水线运行 Store — 运行状态、阶段、数据质量、SSE 实时进度
 * 管理 ETL 运行链路：爬虫采集 → 去重 → 清洗 → 入库 → 图谱构建（Phase 3 串行化）
 * 支持：DAG 串行调度、阶段选择、失败重试/断点续跑、SSE实时进度
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { QualityAlert } from '@/types/quality'
import type { DataSourceDetail } from '@/types/datasource'

import { useResponseValidation } from '@/validation/useResponseValidation'
import pipelineSchema from '../../../starmap-contracts/schemas/pipeline.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validatePipeline } = useResponseValidation()

// Re-export for backward compatibility
export type { QualityAlert } from '@/types/quality'
export type { DataSourceDetail as DataSource } from '@/types/datasource'

// ── 类型定义 ──

export interface PipelineStage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  progress: number
  duration_ms: number
  records_processed: number
  records_seen?: number         // Phase 3.8.11
  errors: string[]
  errors_count: number
  retry_count: number
  depends_on: string[]
  // Phase 3.7: 实时活动上下文
  current_activity?: string
  recent_samples?: Array<Record<string, unknown>>
  sub_breakdown?: Record<string, number>
  elapsed_ms?: number
}

/** Phase 3.7: 实时活动事件 (来自 SSE pipeline_update) */
export interface LiveActivityEvent {
  stage: string
  status: string
  progress: number
  records_processed: number
  message: string
  current_activity?: string
  recent_samples?: Array<Record<string, unknown>>
  sub_breakdown?: Record<string, number>
  elapsed_ms?: number
  timestamp: number
}

export interface PipelineRun {
  id: string
  run_type: 'full' | 'incremental' | 'source_sync'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  stages: PipelineStage[]
  total_records: number
  new_records: number
  updated_records: number
  quality_score: number
  error_log: string | null
  selected_stages: string[] | null
}

// ponytail: DataSource removed — canonical type is DataSourceDetail in types/datasource.ts

export interface PipelineStatus {
  is_running: boolean
  current_run: PipelineRun | null
  last_run: PipelineRun | null
  recent_failed_run: PipelineRun | null
  run_counts: Record<string, number>
  active_data_sources: number
  today_crawl_volume: number
  success_rate: number
  avg_quality_score: number
}

export interface DataQualityMetrics {
  overall_score: number
  completeness: number
  accuracy: number
  freshness_hours: number
  duplicate_rate: number
  total_records: number
  valid_records: number
  consistency: number
  timeliness: number
  trend: Array<{ date: string; score: number }>
  alerts: QualityAlert[]
}

interface DataQualityResponse {
  metrics?: Omit<DataQualityMetrics, 'alerts'>
  alerts?: QualityAlert[]
  [key: string]: unknown
}

// ── Phase 1 SSE 事件类型 (D-10) ──

// ponytail: QualityAlert removed — canonical type in types/quality.ts

export interface DataMilestone {
  type: string
  count: number
  source: string
  message: string
  timestamp: string
}

export interface ExtractionComplete {
  jd_id: string
  source: string
  skills_count: number
  duration_ms: number
  quality_score: number
  timestamp: string
}

// ── Store 定义 ──

export const usePipelineRunStore = defineStore('pipelineRun', () => {
  const pipelineStatus = ref<PipelineStatus | null>(null)
  const runs = ref<PipelineRun[]>([])
  const stages = ref<PipelineStage[]>([])
  const dataQuality = ref<DataQualityMetrics | null>(null)
  const dataSources = ref<DataSourceDetail[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // SSE 实时进度事件
  const liveEvents = ref<Array<{ stage: string; status: string; progress: number; message: string }>>([])

  // Phase 3.7: 实时活动 (current_activity + recent_samples + sub_breakdown)
  const liveActivity = ref<Record<string, LiveActivityEvent>>({})
  // 阶段活动历史（最近 50 条）
  const activityHistory = ref<LiveActivityEvent[]>([])

  // Phase 1 SSE-04 / SSE-05: 3 个新事件类型 state（D-07）
  const qualityAlerts = ref<QualityAlert[]>([])
  const milestones = ref<DataMilestone[]>([])
  const recentExtractions = ref<ExtractionComplete[]>([])

  async function fetchStatus() {
    loading.value = true
    error.value = null
    try {
      const data = validatePipeline(
        await request.get('/pipeline/status') as PipelineStatus,
        pipelineSchema, '/pipeline/status', 'PipelineStatusResponse',
      ) as PipelineStatus
      pipelineStatus.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取流水线状态失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchRuns() {
    loading.value = true
    error.value = null
    try {
      const data = validatePipeline(
        await request.get('/pipeline/runs') as PipelineRun[],
        pipelineSchema, '/pipeline/runs', 'PipelineRunResponse',
      ) as PipelineRun[]
      runs.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取运行记录失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchRunDetail(runId: string): Promise<PipelineRun | null> {
    loading.value = true
    error.value = null
    try {
      const data = validatePipeline(
        await request.get(`/pipeline/runs/${runId}`) as PipelineRun,
        pipelineSchema, `/pipeline/runs/${runId}`, 'PipelineRunResponse',
      ) as PipelineRun
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取运行详情失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function triggerPipeline(runType: string = 'full', selectedStages?: string[]) {
    loading.value = true
    error.value = null
    try {
      const body: Record<string, unknown> = { run_type: runType }
      if (selectedStages) body.selected_stages = selectedStages
      await request.post('/pipeline/trigger', body)
      await fetchStatus()
      await fetchStages()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '触发流水线失败'
    } finally {
      loading.value = false
    }
  }

  async function retryStage(runId: string, stageName: string) {
    loading.value = true
    error.value = null
    try {
      await request.post(`/pipeline/runs/${runId}/retry`, { stage_name: stageName })
      await fetchStages()
      await fetchStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '重试阶段失败'
    } finally {
      loading.value = false
    }
  }

  async function resumeRun(runId: string) {
    loading.value = true
    error.value = null
    try {
      await request.post(`/pipeline/runs/${runId}/resume`)
      await fetchStages()
      await fetchStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '断点续跑失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchStages() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/stages') as { stages: PipelineStage[] }
      stages.value = data.stages || data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取阶段状态失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchDataQuality() {
    loading.value = true
    error.value = null
    try {
      const raw = validatePipeline(
        await request.get('/pipeline/data-quality') as DataQualityResponse,
        pipelineSchema, '/pipeline/data-quality', 'DataQualityResponse',
      ) as DataQualityResponse
      // Phase 1: API 返回嵌套 { metrics: {...}, alerts: [...] } 结构
      // 需要解包 metrics + 合并 alerts 到顶层
      const metrics = (raw && raw.metrics) ? raw.metrics : raw
      const alerts = (raw && raw.alerts) ? raw.alerts : []
      const result = { ...metrics, alerts } as DataQualityMetrics
      dataQuality.value = result
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据质量失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchDataSources() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/datasources') as DataSourceDetail[]
      dataSources.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据源列表失败'
    } finally {
      loading.value = false
    }
  }

  // 处理 SSE pipeline_update 事件
  function handlePipelineEvent(event: { stage: string; status: string; progress: number; message: string; current_activity?: string; recent_samples?: Array<Record<string, unknown>>; sub_breakdown?: Record<string, number>; elapsed_ms?: number; records_processed?: number }) {
    liveEvents.value.push(event)
    if (liveEvents.value.length > 50) liveEvents.value = liveEvents.value.slice(-50)

    // Phase 3.7: 捕获每个阶段的实时活动 + 样本 + 子项分解
    const liveEvent: LiveActivityEvent = {
      ...event,
      records_processed: event.records_processed ?? 0,
      timestamp: Date.now(),
    }
    if (event.current_activity || event.recent_samples || event.sub_breakdown) {
      liveActivity.value[event.stage] = liveEvent
      activityHistory.value.push(liveEvent)
      if (activityHistory.value.length > 80) {
        activityHistory.value = activityHistory.value.slice(-80)
      }
    }

    // Auto-refresh stages on stage status change
    if (['running', 'completed', 'failed'].includes(event.status)) {
      fetchStages()
      fetchStatus()
    }
  }

  /** Phase 3.7: 重置实时活动 (开始新 run 时调用) */
  function resetLiveActivity() {
    liveActivity.value = {}
    activityHistory.value = []
  }

  // Phase 1 SSE-04 / SSE-05: 3 个新事件 handler（D-07）
  function handleQualityAlert(data: QualityAlert) {
    // Ensure created_at is populated from timestamp if missing
    if (!data.created_at && data.timestamp) {
      data.created_at = data.timestamp
    }
    qualityAlerts.value.push(data)
    // Keep only last 50 (FIFO)
    if (qualityAlerts.value.length > 50) {
      qualityAlerts.value = qualityAlerts.value.slice(-50)
    }
  }

  function handleMilestone(data: DataMilestone) {
    milestones.value.push(data)
    if (milestones.value.length > 50) {
      milestones.value = milestones.value.slice(-50)
    }
  }

  function handleExtractionComplete(data: ExtractionComplete) {
    recentExtractions.value.push(data)
    if (recentExtractions.value.length > 50) {
      recentExtractions.value = recentExtractions.value.slice(-50)
    }
  }

  // Phase 1 CANCEL-02: cancelRun action
  async function cancelRun(runId: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await request.post(`/pipeline/runs/${runId}/cancel`)
      // Refresh status + stages after successful cancel
      await fetchStatus()
      await fetchStages()
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '取消流水线失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // Phase 3.8.5: forceAdvance — 强制推进卡死的 run
  async function forceAdvance(runId: string): Promise<boolean> {
    loading.value = true
    try {
      await request.post(`/pipeline/runs/${runId}/force-advance`, {})
      await fetchStatus()
      await fetchStages()
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '强制推进失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // Phase 3.8.5: forceReset — 强制重置卡死的 run
  async function forceReset(runId: string): Promise<boolean> {
    loading.value = true
    try {
      await request.post(`/pipeline/runs/${runId}/force-reset`, {})
      await fetchStatus()
      await fetchStages()
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '强制重置失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    pipelineStatus,
    runs,
    stages,
    dataQuality,
    dataSources,
    loading,
    error,
    liveEvents,
    // Phase 3.7: 实时活动上下文
    liveActivity,
    activityHistory,
    resetLiveActivity,
    // Phase 1 SSE-04/05 新增 state
    qualityAlerts,
    milestones,
    recentExtractions,
    fetchStatus,
    fetchRuns,
    fetchRunDetail,
    triggerPipeline,
    retryStage,
    resumeRun,
    fetchStages,
    fetchDataQuality,
    fetchDataSources,
    handlePipelineEvent,
    // Phase 1 SSE-04/05 新增 actions
    handleQualityAlert,
    handleMilestone,
    handleExtractionComplete,
    // Phase 1 CANCEL-02
    cancelRun,
    forceAdvance,
    forceReset,
  }
})
