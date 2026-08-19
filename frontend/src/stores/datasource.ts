/**
 * 数据源管理 Store — Sprint 1.2
 * 管理多源数据融合：BOSS/拉勾/51Job/GitHub/ESCO
 * 提供数据源 CRUD、统计查询、同步触发
 *
 * refactor: audit queue and graph node management have been
 * extracted to useAuditStore and useGraphNodeStore respectively.
 * This store now focuses solely on data source operations.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { DataSourceDetail } from '@/types/datasource'

import { useResponseValidation } from '@/validation/useResponseValidation'
import datasourceSchema from '@contracts/schemas/datasource.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateDatasource } = useResponseValidation()

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

// 对齐后端 SyncTriggerResponse（openapi schema）：触发单源同步返回的任务信息
export interface SyncTriggerResponse {
  run_id: string
  source_name: string
  status: string
  message: string
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
      const data = validateDatasource(
        await request.get('/datasources') as DataSourceDetail[],
        datasourceSchema, '/datasources', 'DataSourceResponse',
      ) as DataSourceDetail[]
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
      const data = validateDatasource(
        await request.get(`/datasources/${id}`) as DataSourceDetail,
        datasourceSchema, `/datasources/${id}`, 'DataSourceResponse',
      ) as DataSourceDetail
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
      const data = validateDatasource(
        await request.put(`/datasources/${id}`, config) as DataSourceDetail,
        datasourceSchema, `/datasources/${id}`, 'DataSourceResponse',
      ) as DataSourceDetail
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

  // D5: 软删除（停用）数据源 —— DELETE /datasources/{id} → status='inactive'，保留采集历史
  async function deactivateSource(id: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await request.delete(`/datasources/${id}`)
      await fetchSources()
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '停用数据源失败'
      return false
    } finally {
      loading.value = false
    }
  }

  // 2026-08-14: 重新启用停用/暂停的数据源（功能缺口修复——此前停用后 UI 无法再启用）
  async function activateSource(id: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const src = sources.value.find(s => s.id === id)
      // 保留现有 config（platform/max_count 等），仅把 disabled 置 false + status=active
      const config = { ...(src?.config || {}), disabled: false }
      const data = await request.put(`/datasources/${id}`, { status: 'active', config }) as DataSourceDetail
      const idx = sources.value.findIndex(s => s.id === id)
      if (idx !== -1) sources.value[idx] = data
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '启用数据源失败'
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(id: string) {
    loading.value = true
    error.value = null
    try {
      // E20 fix: backend returns `crawl_volume` / `quality_trend` / `avg_records_per_run`
      // while the DataSourceStats type expects `daily_volume` / `quality_trend` / `avg_daily_count`.
      // Map field names so the stats drawer renders the bar chart instead of empty.
      const raw = await request.get(`/datasources/${id}/stats?period=30d`) as {
        crawl_volume?: Array<{ date: string; count: number }>
        quality_trend?: Array<{ date: string; score: number }>
        total_runs?: number
        successful_runs?: number
        failed_runs?: number
        avg_records_per_run?: number
      }
      const daily_volume = raw.crawl_volume ?? []
      const total_count = daily_volume.reduce((s, d) => s + (d.count || 0), 0)
      const days = daily_volume.length || 1
      const mapped: DataSourceStats = {
        source_id: id,
        daily_volume,
        weekly_volume: [],
        monthly_volume: [],
        quality_trend: raw.quality_trend ?? [],
        avg_daily_count: Math.round((total_count / days) * 10) / 10,
        total_count,
      }
      stats.value = mapped
      return mapped
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取数据源统计失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function triggerSync(id: string): Promise<SyncTriggerResponse | false> {
    loading.value = true
    error.value = null
    try {
      // fix: 后端 sync 端点在公共 router（/datasources/{id}/sync），非 admin_router；该端点自带 require_admin，权限不降级
      // 返回后端 SyncTriggerResponse（run_id/source_name/status/message），供 Admin 页展示真实任务信息
      const data = validateDatasource(
        await request.post(`/datasources/${id}/sync`) as SyncTriggerResponse,
        datasourceSchema, `/datasources/${id}/sync`, 'SyncTriggerResponse',
      ) as SyncTriggerResponse
      // 同步后刷新该数据源详情
      await fetchSourceDetail(id)
      return data
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
      const data = validateDatasource(
        await request.get('/datasources/health') as DatasourcesHealthResponse,
        datasourceSchema, '/datasources/health', 'DatasourcesHealthResponse',
      ) as DatasourcesHealthResponse
      health.value = data
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取健康检查失败'
      return null
    } finally {
      loading.value = false
    }
  }

  /** / T2.3: 按需触发单源采集 */
  async function triggerCrawl(source: string) {
    // D5: /crawl-source 是同步爬取（spider 全程 + 限速 2s/请求），沙盒网络差时可达 30-60s。
    // 默认 axios 30s 会先超时误报，这里单独给 90s 超时（仅此请求，不污染全局）。
    return request.post(
      `/pipeline/crawl-source?source=${encodeURIComponent(source)}`,
      undefined,
      { timeout: 90000 },
    ) as Promise<unknown>
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
    deactivateSource,
    activateSource,
    fetchStats,
    triggerSync,
    triggerCrawl,
    fetchHealth,
  }
})