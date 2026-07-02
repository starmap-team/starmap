/**
 * 数据源管理 Store — Sprint 1.2
 * 管理多源数据融合：BOSS/拉勾/51Job/GitHub/ESCO
 * 提供数据源 CRUD、统计查询、同步触发
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

// ── 类型定义 ──

export interface DataSourceDetail {
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
  daily_crawl_volume: number[]
  config?: Record<string, unknown>
}

export interface DataSourceStats {
  source_id: string
  daily_volume: Array<{ date: string; count: number }>
  weekly_volume: Array<{ week: string; count: number }>
  monthly_volume: Array<{ month: string; count: number }>
  quality_trend: Array<{ date: string; score: number }>
  avg_daily_count: number
  total_count: number
}

// ── Store 定义 ──

export const useDataSourceStore = defineStore('datasource', () => {
  const sources = ref<DataSourceDetail[]>([])
  const selectedSource = ref<DataSourceDetail | null>(null)
  const stats = ref<DataSourceStats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSources() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/datasources') as DataSourceDetail[]
      sources.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据源列表失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchSourceDetail(id: string) {
    loading.value = true
    error.value = null
    try {
      const data = await request.get(`/datasources/${id}`) as DataSourceDetail
      selectedSource.value = data
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据源详情失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateSource(id: string, config: Record<string, unknown>) {
    loading.value = true
    error.value = null
    try {
      const data = await request.put(`/datasources/${id}`, config) as DataSourceDetail
      // 更新列表中的对应项
      const idx = sources.value.findIndex(s => s.id === id)
      if (idx !== -1) sources.value[idx] = data
      if (selectedSource.value?.id === id) selectedSource.value = data
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新数据源配置失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(id: string) {
    loading.value = true
    error.value = null
    try {
      const data = await request.get(`/datasources/${id}/stats`) as DataSourceStats
      stats.value = data
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据源统计失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function triggerSync(id: string) {
    loading.value = true
    error.value = null
    try {
      await request.post(`/datasources/${id}/sync`)
      // 同步后刷新该数据源详情
      await fetchSourceDetail(id)
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '触发同步失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    sources,
    selectedSource,
    stats,
    loading,
    error,
    fetchSources,
    fetchSourceDetail,
    updateSource,
    fetchStats,
    triggerSync,
  }
})
