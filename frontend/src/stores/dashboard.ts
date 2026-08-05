/**
 * 数据大屏 Pinia store — Sprint 3.1
 * 聚合所有系统指标：图谱统计 + 来源分布 + 质量指标 + 实时处理量
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import type { EmergingSkill } from '@/types/evolution'
import { useResponseValidation } from '@/validation/useResponseValidation'
import dashboardSchema from '../../../starmap-contracts/schemas/dashboard.schema.json'

// Re-export for backward compatibility
export type { EmergingSkill } from '@/types/evolution'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateDashboard } = useResponseValidation()

// ── 类型定义 ──

export interface DashboardOverview {
  total_nodes: number
  total_edges: number
  total_domains: number
  total_positions: number
  total_skills: number
  trust_score: number
  hallucination_rate: number
  total_extractions: number
  data_volume: number
  today_extractions: number
  pipeline_status: string
  active_data_sources: number
  weekly_new_nodes: number
  stale: boolean
  stale_since: number | null
  timestamp: number
}

export interface SourceDistribution {
  name: string
  count: number
  percentage: number
  trust: number
  color?: string
}

export interface SkillDomain {
  name: string
  value: number
  children?: SkillDomain[]
  trend?: 'up' | 'down' | 'stable'
}

export interface QualityTrend {
  date: string
  quality_score: number
  trust_score: number | null
  crawl_volume: number
  match_success_rate: number | null
  hallucination_rate: number | null
}

export interface RealtimeEvent {
  id: string
  type: 'skill_update' | 'match_event' | 'graph_update' | 'pipeline_event' | 'extraction'
  title: string
  detail: string
  timestamp: string
  icon?: string
  severity?: 'info' | 'success' | 'warning' | 'error'
}

export interface PipelineTimelineItem {
  stage: string
  status: 'running' | 'completed' | 'failed' | 'waiting'
  started_at: string
  completed_at: string | null
  records_processed: number
  progress: number
}

// ponytail: EmergingSkill removed — canonical type in types/evolution.ts

// ── Store 定义 ──

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview | null>(null)
  const sourceDistribution = ref<SourceDistribution[]>([])
  const skillDomains = ref<SkillDomain[]>([])
  const qualityTrends = ref<QualityTrend[]>([])
  const realtimeEvents = ref<RealtimeEvent[]>([])
  const pipelineTimeline = ref<PipelineTimelineItem[]>([])
  const emergingSkills = ref<EmergingSkill[]>([])
  const sseConnected = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── Actions ──

  async function fetchOverview() {
    loading.value = true
    error.value = null
    try {
      const raw = validateDashboard(
        await request.get('/dashboard/overview') as Record<string, unknown>,
        dashboardSchema, '/dashboard/overview', 'OverviewResponse',
      ) as Record<string, unknown>
      // Direct mapping — frontend DashboardOverview matches backend OverviewResponse 1:1
      overview.value = {
        total_nodes: (raw.total_nodes as number) ?? 0,
        total_edges: (raw.total_edges as number) ?? 0,
        total_domains: (raw.total_domains as number) ?? 0,
        total_positions: (raw.total_positions as number) ?? 0,
        total_skills: (raw.total_skills as number) ?? 0,
        trust_score: (raw.trust_score as number) ?? 0,
        hallucination_rate: (raw.hallucination_rate as number) ?? 0,
        total_extractions: (raw.total_extractions as number) ?? 0,
        data_volume: (raw.data_volume as number) ?? 0,
        today_extractions: (raw.today_extractions as number) ?? 0,
        pipeline_status: (raw.pipeline_status as string) ?? 'idle',
        active_data_sources: (raw.active_data_sources as number) ?? 0,
        weekly_new_nodes: (raw.weekly_new_nodes as number) ?? 0,
        stale: (raw.stale as boolean) ?? false,
        stale_since: (raw.stale_since as number | null) ?? null,
        timestamp: (raw.timestamp as number) ?? 0,
      }
    } catch (e: unknown) {
      // fix: HTTPException.detail 在 axios 错误对象里位于 response.data.detail，message 字段是 axios 默认文案
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = detail ?? (e instanceof Error ? e.message : '获取概览数据失败')
    } finally {
      loading.value = false
    }
  }

  async function fetchTrends() {
    try {
      const resp = validateDashboard(
        await request.get('/dashboard/trends') as Record<string, unknown>,
        dashboardSchema, '/dashboard/trends', 'TrendsResponse',
      ) as {
        period: string
        data_points: Array<{
          date: string
          total_records: number
          new_records: number
          quality_score: number
          extractions: number
          trust_score?: number
          match_success_rate?: number
          hallucination_rate?: number
        }>
        summary: Record<string, unknown>
      }
      // Map backend TrendPoint to frontend QualityTrend
      qualityTrends.value = (resp.data_points || []).map(dp => ({
        date: dp.date,
        quality_score: dp.quality_score,
        trust_score: dp.trust_score ?? null,
        crawl_volume: dp.extractions,
        match_success_rate: dp.match_success_rate ?? null,
        hallucination_rate: dp.hallucination_rate ?? null,
      }))
    } catch {
      qualityTrends.value = []
    }
  }

  async function fetchDistribution() {
    try {
      // Backend source_distribution: {name, source_type, total_records, valid_records, authority_score, duplicate_rate}
      // Backend domain_distribution: {name, count}
      // Frontend SourceDistribution: {name, count, percentage, trust, color?}
      // Frontend SkillDomain: {name, value, children?, trend?}
      const data = validateDashboard(
        await request.get('/dashboard/distribution') as Record<string, unknown>,
        dashboardSchema, '/dashboard/distribution', 'DistributionResponse',
      ) as {
        source_distribution: Array<{
          name: string
          source_type?: string
          total_records?: number
          valid_records?: number
          count?: number
          percentage?: number
          authority_score?: number
          trust?: number
          duplicate_rate?: number
        }>
        domain_distribution: Array<{ name: string; count?: number; value?: number }>
        skill_category_distribution: { name: string; count: number; percentage?: number }[]
      }
      const srcs = data.source_distribution || []
      const totalSrcCount = srcs.reduce((s, x) => s + (x.total_records ?? x.count ?? 0), 0) || 1
      sourceDistribution.value = srcs.map(s => ({
        name: getSourceNameLabel(s.name),
        count: s.total_records ?? s.count ?? 0,
        percentage: s.percentage ?? Math.round(((s.total_records ?? s.count ?? 0) / totalSrcCount) * 1000) / 10,
        trust: s.authority_score ?? s.trust ?? 0,
        color: undefined,
      }))
      const domains = data.domain_distribution || []
      skillDomains.value = domains.map(d => ({
        name: d.name,
        value: d.count ?? d.value ?? 0,
      }))
    } catch {
      sourceDistribution.value = []
    }
  }

  async function fetchEmergingSkills() {
    try {
      // Try the dedicated endpoint first, fallback to graph overview
      const data = await request.get('/evolution/emerging-skills') as EmergingSkill[]
      emergingSkills.value = data
    } catch {
      emergingSkills.value = []
    }
  }

  async function fetchPipelineTimeline() {
    try {
      const data = await request.get('/pipeline/stages') as { stages: PipelineTimelineItem[] }
      pipelineTimeline.value = data.stages || []
    } catch {
      pipelineTimeline.value = []
    }
  }

  /** Add a real-time event from SSE stream */
  function addRealtimeEvent(event: RealtimeEvent) {
    realtimeEvents.value.unshift(event)
    // Keep last 100 events
    if (realtimeEvents.value.length > 100) {
      realtimeEvents.value = realtimeEvents.value.slice(0, 100)
    }
  }

  /** Load all dashboard data in parallel */
  async function fetchAll() {
    loading.value = true
    try {
      await Promise.allSettled([
        fetchOverview(),
        fetchTrends(),
        fetchDistribution(),
        fetchEmergingSkills(),
        fetchPipelineTimeline(),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    overview,
    sourceDistribution,
    skillDomains,
    qualityTrends,
    realtimeEvents,
    pipelineTimeline,
    emergingSkills,
    sseConnected,
    loading,
    error,
    // Actions
    fetchOverview,
    fetchTrends,
    fetchDistribution,
    fetchEmergingSkills,
    fetchPipelineTimeline,
    fetchAll,
    addRealtimeEvent,
  }
})

