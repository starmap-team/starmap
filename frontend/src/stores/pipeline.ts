/**
 * 数据流水线监控 Store — 完整批量爬虫流
 * 管理 ETL 全链路状态：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
 * 支持：DAG并行、阶段选择、失败重试/断点续跑、定时调度、SSE实时进度
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'

// ── 类型定义 ──

export interface PipelineStage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'waiting'
  duration_ms: number
  records_processed: number
  errors: number
  progress: number
  retry_count: number
  depends_on: string[]
}

export interface PipelineRun {
  id: string
  run_type: 'full' | 'incremental' | 'source_sync'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  stages: PipelineStage[]
  total_records: number
  new_records: number
  updated_records: number
  quality_score: number
  error_log: string | null
  selected_stages: string[] | null
}

export interface DataSource {
  id: string
  name: string
  source_type: 'crawler' | 'api' | 'manual' | 'import'
  authority_score: number
  status: 'active' | 'paused' | 'error'
  last_crawl_at: string
  total_records: number
  valid_records: number
  duplicate_rate: number
  avg_quality_score: number
  config?: Record<string, unknown>
}

export interface PipelineStatus {
  is_running: boolean
  current_run: PipelineRun | null
  last_run: PipelineRun | null
  run_counts: Record<string, number>
  active_data_sources: number
  today_crawl_volume?: number
  success_rate?: number
  avg_quality_score?: number
}

export interface DataQualityMetrics {
  overall_score: number
  completeness: number
  accuracy: number
  consistency: number
  timeliness: number
  trend: Array<{ date: string; score: number }>
  alerts: Array<{ level: 'info' | 'warning' | 'error'; message: string; time: string }>
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
  const dataSources = ref<DataSource[]>([])
  const schedules = ref<PipelineSchedule[]>([])
  const config = ref<PipelineConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // SSE 实时进度事件
  const liveEvents = ref<Array<{ stage: string; status: string; progress: number; message: string }>>([])

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
      const data = await request.get('/pipeline/data-quality') as DataQualityMetrics
      dataQuality.value = data
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
      const data = await request.get('/pipeline/datasources') as DataSource[]
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
    fetchConfig,
    updateConfig,
    handlePipelineEvent,
  }
})
