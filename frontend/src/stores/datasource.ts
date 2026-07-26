/**
 * 数据源管理 Store — Sprint 1.2
 * 管理多源数据融合：BOSS/拉勾/51Job/GitHub/ESCO
 * 提供数据源 CRUD、统计查询、同步触发
 *
 * Phase 7 refactor: audit queue and graph node management have been
 * extracted to useAuditStore and useGraphNodeStore respectively.
 * This store now focuses solely on data source operations.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { DataSourceDetail } from '@/types/datasource'

// Re-export for backward compatibility
export type { DataSourceDetail } from '@/types/datasource'

// ── 类型定义 ──

export interface SourceHealthEntry {
  id: string
  name: string
  status: string
  last_crawl_at: string | null
  total_records: number
  recent_run_status: string | null
}

export interface DatasourcesHealthResponse {
  sources: SourceHealthEntry[]
  total_sources: number
  active_sources: number
  error_sources: number
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
  const health = ref<DatasourcesHealthResponse | null>(null)

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
      // fix: 后端 PUT 端点在公共 router（/datasources/{id}），非 admin_router；该端点自带 require_admin，权限不降级
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
      // fix: 后端 sync 端点在公共 router（/datasources/{id}/sync），非 admin_router；该端点自带 require_admin，权限不降级
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

  async function fetchHealth() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/datasources/health') as DatasourcesHealthResponse
      health.value = data
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取健康检查失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    sources,
    selectedSource,
    stats,
    health,
    loading,
    error,
    fetchSources,
    fetchSourceDetail,
    updateSource,
    fetchStats,
    triggerSync,
    fetchHealth,
  }
})