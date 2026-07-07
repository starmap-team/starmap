/**
 * 数据流水线监控 Store — 完整批量爬虫流
 * 管理 ETL 全链路状态：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
 * 支持：DAG并行、阶段选择、失败重试/断点续跑、定时调度、SSE实时进度
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { QualityAlert } from '@/types/quality'
import type { DataSourceDetail } from '@/types/datasource'

// ── 类型定义 ──

export interface PipelineStage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  progress: number
  duration_ms: number
  records_processed: number
  errors: string[]
  errors_count: number
  retry_count: number
  depends_on: string[]
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
  alerts: Array<{
    level: 'info' | 'warning' | 'error'
    dimension?: string
    message: string
    source?: string
    value?: number
    threshold?: number
    timestamp: string
    time: string  // Pydantic alias of timestamp
  }>
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

export interface PipelineSchedule {
  id: string
  name: string
  cron_expression: string
  run_type: 'full' | 'incremental'
  selected_stages: string[] | null
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_at: string | null
}

export interface PipelineConfig {
  stage_timeout: number
  worker_concurrency: number
  crawl_concurrency: number
  retry_max: number
  retry_backoff: number
}

// ── 阶段名称映射 ──
export const STAGE_LABELS: Record<string, string> = {
  crawl: '爬虫采集',
  dedup: 'SimHash去重',
  clean: '清洗标准化',
  import: '数据入库',
  graph_sync: '图谱构建',
}

export const ALL_STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync']

// ── Store 定义 ──

export const usePipelineStore = defineStore('pipeline', () => {
  const pipelineStatus = ref<PipelineStatus | null>(null)
  const runs = ref<PipelineRun[]>([])
  const stages = ref<PipelineStage[]>([])
  const dataQuality = ref<DataQualityMetrics | null>(null)
  const dataSources = ref<DataSourceDetail[]>([])
  const schedules = ref<PipelineSchedule[]>([])
  const config = ref<PipelineConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // SSE 实时进度事件
  const liveEvents = ref<Array<{ stage: string; status: string; progress: number; message: string }>>([])

  // Phase 1 SSE-04 / SSE-05: 3 个新事件类型 state（D-07）
  const qualityAlerts = ref<QualityAlert[]>([])
  const milestones = ref<DataMilestone[]>([])
  const recentExtractions = ref<ExtractionComplete[]>([])

  async function fetchStatus() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/status') as PipelineStatus
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
      const data = await request.get('/pipeline/runs') as PipelineRun[]
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
      const data = await request.get(`/pipeline/runs/${runId}`) as PipelineRun
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
      const raw = await request.get('/pipeline/data-quality') as any
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

  async function fetchSchedules() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/schedules') as PipelineSchedule[]
      schedules.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取定时调度失败'
    } finally {
      loading.value = false
    }
  }

  async function createSchedule(schedule: Omit<PipelineSchedule, 'id' | 'last_run_at' | 'next_run_at' | 'created_at'>) {
    loading.value = true
    error.value = null
    try {
      await request.post('/pipeline/schedules', schedule)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '创建定时调度失败'
    } finally {
      loading.value = false
    }
  }

  async function updateSchedule(id: string, schedule: Omit<PipelineSchedule, 'id' | 'last_run_at' | 'next_run_at' | 'created_at'>) {
    loading.value = true
    error.value = null
    try {
      await request.put(`/pipeline/schedules/${id}`, schedule)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新定时调度失败'
    } finally {
      loading.value = false
    }
  }

  async function deleteSchedule(id: string) {
    loading.value = true
    error.value = null
    try {
      await request.delete(`/pipeline/schedules/${id}`)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '删除定时调度失败'
    } finally {
      loading.value = false
    }
  }

  async function triggerSchedule(id: string) {
    loading.value = true
    error.value = null
    try {
      await request.post(`/pipeline/schedules/${id}/trigger`)
      await fetchSchedules()
      await fetchStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '执行调度失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchConfig() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/config') as PipelineConfig
      config.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取流水线配置失败'
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(newConfig: Partial<PipelineConfig>) {
    loading.value = true
    error.value = null
    try {
      const data = await request.put('/pipeline/config', newConfig) as PipelineConfig
      config.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新流水线配置失败'
    } finally {
      loading.value = false
    }
  }

  // 处理 SSE pipeline_update 事件
  function handlePipelineEvent(event: { stage: string; status: string; progress: number; message: string }) {
    liveEvents.value.push(event)
    // Keep only last 50 events
    if (liveEvents.value.length > 50) liveEvents.value = liveEvents.value.slice(-50)
    // Auto-refresh stages on stage status change
    if (['running', 'completed', 'failed'].includes(event.status)) {
      fetchStages()
      fetchStatus()
    }
  }

  // Phase 1 SSE-04 / SSE-05: 3 个新事件 handler（D-07）
  function handleQualityAlert(data: QualityAlert) {
    // 自动用 timestamp 填充 time 别名（如缺失）
    if (!data.time && data.timestamp) {
      data.time = data.timestamp
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
      // Refresh status after successful cancel
      await fetchStatus()
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '取消流水线失败'
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
    schedules,
    config,
    loading,
    error,
    liveEvents,
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
    fetchSchedules,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    triggerSchedule,
    fetchConfig,
    updateConfig,
    handlePipelineEvent,
    // Phase 1 SSE-04/05 新增 actions
    handleQualityAlert,
    handleMilestone,
    handleExtractionComplete,
    // Phase 1 CANCEL-02
    cancelRun,
  }
})
