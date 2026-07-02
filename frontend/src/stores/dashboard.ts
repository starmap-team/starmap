/**
 * 数据大屏 Pinia store — Sprint 3.1
 * 聚合所有系统指标：图谱统计 + 来源分布 + 质量指标 + 实时处理量
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

// ── 类型定义 ──

export interface DashboardOverview {
  total_nodes: number
  total_edges: number
  total_domains: number
  total_positions: number
  total_skills: number
  avg_trust_score: number
  today_crawl_volume: number
  today_matches: number
  today_extractions: number
  active_sources: number
  pipeline_status: string
  quality_score: number
  weekly_new_nodes: number
  weekly_new_edges: number
  hallucination_rate: number
  stale?: boolean
  stale_since?: string | null
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
  trust_score: number
  crawl_volume: number
  match_success_rate: number
  hallucination_rate: number
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

export interface EmergingSkill {
  name: string
  frequency: number
  growth_rate: number
  relevance: number
  novelty: number
  domain: string
}

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
      const raw = await request.get('/dashboard/overview') as Record<string, unknown>
      // Map backend fields to frontend DashboardOverview
      overview.value = {
        total_nodes: (raw.total_nodes as number) ?? 0,
        total_edges: (raw.total_edges as number) ?? 0,
        total_domains: (raw.total_domains as number) ?? 0,
        total_positions: (raw.total_positions as number) ?? 0,
        total_skills: (raw.total_skills as number) ?? 0,
        avg_trust_score: (raw.trust_score as number) ?? 0,
        today_crawl_volume: (raw.data_volume as number) ?? 0,
        today_matches: 0,
        today_extractions: (raw.today_extractions as number) ?? 0,
        active_sources: (raw.active_data_sources as number) ?? 0,
        pipeline_status: (raw.pipeline_status as string) ?? 'idle',
        quality_score: (raw.trust_score as number) ?? 0,
        weekly_new_nodes: 0,
        weekly_new_edges: 0,
        hallucination_rate: (raw.hallucination_rate as number) ?? 0,
        stale: (raw.stale as boolean) ?? false,
        stale_since: raw.stale_since as string | null ?? null,
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取概览数据失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchTrends() {
    try {
      const resp = await request.get('/dashboard/trends') as {
        period: string
        data_points: Array<{
          date: string
          total_records: number
          new_records: number
          quality_score: number
          extractions: number
        }>
        summary: Record<string, unknown>
      }
      // Map backend TrendPoint to frontend QualityTrend
      qualityTrends.value = (resp.data_points || []).map(dp => ({
        date: dp.date,
        quality_score: dp.quality_score,
        trust_score: dp.quality_score,  // reuse quality as trust proxy
        crawl_volume: dp.extractions,
        match_success_rate: 0,
        hallucination_rate: 0,
      }))
    } catch {
      qualityTrends.value = []
    }
  }

  async function fetchDistribution() {
    try {
      const data = await request.get('/dashboard/distribution') as {
        source_distribution: SourceDistribution[]
        domain_distribution: SkillDomain[]
        skill_category_distribution: { name: string; count: number; percentage?: number }[]
      }
      sourceDistribution.value = data.source_distribution || []
      skillDomains.value = data.domain_distribution || []
    } catch {
      sourceDistribution.value = []
    }
  }

  async function fetchSkillDomains() {
    // Now fetched together with fetchDistribution from /dashboard/distribution
    // This function is kept for backwards compatibility but is a no-op
    if (skillDomains.value.length === 0) {
      await fetchDistribution()
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
        fetchSkillDomains(),
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
    fetchSkillDomains,
    fetchEmergingSkills,
    fetchPipelineTimeline,
    fetchAll,
    addRealtimeEvent,
  }
})
