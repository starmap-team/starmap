/**
 * 数据流水线配置 Store — 定时调度 & 全局配置
 * 管理 Pipeline 定时调度 CRUD 和运行时配置
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

// ── 类型定义 ──

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
  import: 'LLM抽取+入库',
  graph_sync: '图谱构建',
  timeseries: '时间序列',
}

// Phase 17-01: timeseries 移出核心 DAG (设计文档明确它不属于 ETL)
// 它由 evolution 服务单独触发, 留 OPTIONAL_STAGES 供向后兼容
export const ALL_STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync']
export const OPTIONAL_STAGES = ['timeseries', 'graph_sync']

// ── Store 定义 ──

export const usePipelineConfigStore = defineStore('pipelineConfig', () => {
  const schedules = ref<PipelineSchedule[]>([])
  const config = ref<PipelineConfig | null>(null)
  const scheduleLoading = ref(false)
  const configLoading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSchedules() {
    scheduleLoading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/schedules') as PipelineSchedule[]
      schedules.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取定时调度失败'
    } finally {
      scheduleLoading.value = false
    }
  }

  async function createSchedule(schedule: Omit<PipelineSchedule, 'id' | 'last_run_at' | 'next_run_at' | 'created_at'>) {
    scheduleLoading.value = true
    error.value = null
    try {
      await request.post('/pipeline/schedules', schedule)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '创建定时调度失败'
    } finally {
      scheduleLoading.value = false
    }
  }

  async function updateSchedule(id: string, schedule: Omit<PipelineSchedule, 'id' | 'last_run_at' | 'next_run_at' | 'created_at'>) {
    scheduleLoading.value = true
    error.value = null
    try {
      await request.put(`/pipeline/schedules/${id}`, schedule)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新定时调度失败'
    } finally {
      scheduleLoading.value = false
    }
  }

  async function deleteSchedule(id: string) {
    scheduleLoading.value = true
    error.value = null
    try {
      await request.delete(`/pipeline/schedules/${id}`)
      await fetchSchedules()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '删除定时调度失败'
    } finally {
      scheduleLoading.value = false
    }
  }

  async function triggerSchedule(id: string) {
    scheduleLoading.value = true
    error.value = null
    try {
      await request.post(`/pipeline/schedules/${id}/trigger`)
      await fetchSchedules()
      // Cross-store: refresh pipeline status after triggering a schedule
      const { usePipelineRunStore } = await import('./pipelineRun')
      await usePipelineRunStore().fetchStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '执行调度失败'
    } finally {
      scheduleLoading.value = false
    }
  }

  async function fetchConfig() {
    configLoading.value = true
    error.value = null
    try {
      const data = await request.get('/pipeline/config') as PipelineConfig
      config.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取流水线配置失败'
    } finally {
      configLoading.value = false
    }
  }

  async function updateConfig(newConfig: Partial<PipelineConfig>) {
    configLoading.value = true
    error.value = null
    try {
      const data = await request.put('/pipeline/config', newConfig) as PipelineConfig
      config.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新流水线配置失败'
    } finally {
      configLoading.value = false
    }
  }

  return {
    schedules,
    config,
    scheduleLoading,
    configLoading,
    error,
    fetchSchedules,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    triggerSchedule,
    fetchConfig,
    updateConfig,
  }
})
