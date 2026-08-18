/**
 * Evolution store — shared fetch logic for evolution-related pages
 * Replaces direct `request` calls in EvolutionDashboard.vue (audit B5)
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { ChangeType } from '@/types/evolution'

import { useResponseValidation } from '@/validation/useResponseValidation'
import evolutionSchema from '@contracts/schemas/evolution.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateEvolution } = useResponseValidation()

export interface TrendItem {
  skill_name: string
  trend: string
  confidence: number
  points: number[]
  related_positions: string[]
}

export interface SnapshotEntry {
  id: string
  position_name: string
  snapshot_date: string
  required_skills: unknown[]
  preferred_skills?: unknown[]
  source_count: number
}

export interface ChangelogEntry {
  id: string
  skill_name: string
  change_type: ChangeType
 // 字段对齐后端 ChangelogEntry schema（Pydantic ↔ openapi.yaml ↔ evolution.schema.json）
  trust_score: number
  confidence: number
  created_at: string
 // Optional fields returned by the backend schema / used in UI
  position_name?: string
  old_proficiency?: string | null
  new_proficiency?: string | null
  old_requirement?: string | null
  new_requirement?: string | null
  date?: string
  description?: string
 // 10-03 contract sync: status/written_back/evidence_json ( 证据链路)
  status?: 'pending' | 'approved' | 'rejected'
  written_back?: boolean
  evidence_json?: Record<string, unknown>
}

// 10-03: KPI row state — zeros by default, filled by fetchKpi
export interface EvolutionKpi {
  emerging_count: number
  trust_mean: number
 /** D-cross: 与 /quality 共享 avg_skill_trust 对照口径（Neo4j Skill.trust_score 实时均值）*/
  trust_mean_neo4j_skill?: number
  cii_mean: number
  alert_count: number
  days: number
}

export const DEFAULT_KPI: EvolutionKpi = {
  emerging_count: 0,
  trust_mean: 0,
  trust_mean_neo4j_skill: 0,
  cii_mean: 0,
  alert_count: 0,
  days: 90,
}

// LOOP-06: Emerging alert type for evolution alerts
//: Added missing fields from backend (source_count, trend, portability_score)
export interface EmergingAlert {
  skill_name: string
  category: string
  level: 'emerging' | 'rising' | 'stable' | 'declining'
  z_score: number
  current_frequency: number
  mean_frequency: number
  source_count: number
  trend: 'rising' | 'stable' | 'declining'
  portability_score: number
  domains: string[]
  positions: string[]
  alert_message: string
}

// BUG-5 fix: review-queue item shape returned by /evolution/review-queue
export interface ReviewQueueItem {
 // E22 fix: include id so the frontend can dispatch per-row approve/reject
 // via /evolution/review-queue/{id}/action.
  id: string
  skill_name: string | null
  position_name: string | null
  change_type: string
  trust_score: number
  status: string
  created_at: string
}

// 快照联动: /evolution/cii-history/{position} 返回的 CII 历史（E1 快照时间线数据源）
export interface CiiHistoryEntry {
  snapshot_date: string
  cii: number
  total_skills: number
  inflated_skills: number
}

export const useEvolutionStore = defineStore('evolution', () => {
  const loading = ref(false)
  const trendItems = ref<TrendItem[]>([])

  const snapshotsLoading = ref(false)
  const snapshots = ref<SnapshotEntry[]>([])

  const changelogLoading = ref(false)
  const changelogData = ref<ChangelogEntry[]>([])

 // LOOP-06: Emerging alerts state
  const emergingAlerts = ref<EmergingAlert[]>([])
  const alertsLoading = ref(false)

 // 10-03 : KPI row state — zeros until fetchKpi resolves
  const kpi = ref<EvolutionKpi>({ ...DEFAULT_KPI })
  const kpiLoading = ref(false)

  async function fetchTrends(days?: number) {
    loading.value = true
    try {
      const params = days ? { days } : undefined
      const data = validateEvolution(
        await request.get<{ items?: TrendItem[] }>('/evolution/trends', { params }) as Record<string, unknown>,
        evolutionSchema, '/evolution/trends', 'EvolutionTrendsResponse',
      ) as { items?: TrendItem[] }
      trendItems.value = data.items ?? []
    } finally {
      loading.value = false
    }
    return { items: trendItems.value }
  }

 // 10-03 : KPI row fetch — mirrors fetchTrends pattern
  async function fetchKpi(days?: number) {
    kpiLoading.value = true
    try {
      const params = days ? { days } : undefined
      const data = validateEvolution(
        await request.get<{ emerging_count?: number; trust_mean?: number; trust_mean_neo4j_skill?: number; cii_mean?: number; alert_count?: number; days?: number }>(
          '/evolution/kpi', { params },
        ) as Record<string, unknown>,
        evolutionSchema, '/evolution/kpi', 'EvolutionKpiResponse',
      ) as { emerging_count?: number; trust_mean?: number; trust_mean_neo4j_skill?: number; cii_mean?: number; alert_count?: number; days?: number }
      kpi.value = {
        emerging_count: data.emerging_count ?? DEFAULT_KPI.emerging_count,
        trust_mean: data.trust_mean ?? DEFAULT_KPI.trust_mean,
        trust_mean_neo4j_skill: data.trust_mean_neo4j_skill ?? DEFAULT_KPI.trust_mean_neo4j_skill,
        cii_mean: data.cii_mean ?? DEFAULT_KPI.cii_mean,
        alert_count: data.alert_count ?? DEFAULT_KPI.alert_count,
        days: data.days ?? DEFAULT_KPI.days,
      }
    } finally {
      kpiLoading.value = false
    }
    return kpi.value
  }

 // 触发演化分析（原 EvolutionDashboard.vue 直调 request.post('/evolution/analyze')）
  async function analyze(days?: number): Promise<{ message?: string; task_id?: string; days?: number }> {
    const res = await request.post<{ message?: string; task_id?: string; days?: number }>(
      '/evolution/analyze', undefined, { params: days ? { days } : undefined },
    ) as { message?: string; task_id?: string; days?: number }
    return res
  }

  async function fetchSnapshots(limit = 50) {
    snapshotsLoading.value = true
    try {
 // P2 fix (functional-review 2026-08-13): 后端 /evolution/snapshots 返回
 // SnapshotEntry 数组，此前把整数组当单条 SnapshotEntry 校验 → schema 名
 // 错位，校验实际未生效（DEV warn 不报）。改为逐条校验。
      const data = await request.get(`/evolution/snapshots?limit=${limit}`) as SnapshotEntry[]
      const list = Array.isArray(data)
        ? data.map((item) => validateEvolution(item, evolutionSchema, '/evolution/snapshots', 'SnapshotEntry') as SnapshotEntry)
        : []
      snapshots.value = [...list].sort((a, b) =>
        String(a.snapshot_date).localeCompare(String(b.snapshot_date))
      ) as SnapshotEntry[]
    } catch {
      snapshots.value = []
    } finally {
      snapshotsLoading.value = false
    }
    return snapshots.value
  }

 // UX-04: Renamed parameter — backend 'identifier' accepts both position and skill names
  async function fetchChangelog(identifier: string) {
    changelogLoading.value = true
    try {
      const raw = validateEvolution(
        await request.get(`/evolution/changelog/${encodeURIComponent(identifier)}`) as Record<string, unknown>,
        evolutionSchema, `/evolution/changelog/${encodeURIComponent(identifier)}`, 'ChangelogEntry',
      ) as unknown
      if (raw === null || raw === undefined) {
        changelogData.value = []
        return changelogData.value
      }
      const data = raw as Record<string, unknown>
      changelogData.value = (Array.isArray(raw)
        ? raw
        : data.changelog ?? data.items ?? []) as ChangelogEntry[]
    } finally {
      changelogLoading.value = false
    }
    return changelogData.value
  }

 // LOOP-06: Fetch emerging skill alerts
  async function fetchEmergingAlerts(level?: string) {
    alertsLoading.value = true
    try {
      const params = level ? { level } : {}
      const data = validateEvolution(
        await request.get('/evolution/emerging-alerts', { params }) as { alerts: EmergingAlert[]; total: number; summary: string },
        evolutionSchema, '/evolution/emerging-alerts', 'EmergingAlertsResponse',
      ) as { alerts: EmergingAlert[]; total: number; summary: string }
      emergingAlerts.value = data.alerts ?? []
    } catch (e: unknown) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch alerts:', e)
 // fix: HTTPException.detail 在 axios 错误对象里位于 response.data.detail
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (detail) console.error('[Evolution] Detail:', detail)
      emergingAlerts.value = []
    } finally {
      alertsLoading.value = false
    }
  }

 // BUG-5 fix: low-trust EvolutionChangelog review queue
  const reviewQueue = ref<ReviewQueueItem[]>([])
  const reviewQueueLoading = ref(false)
  async function fetchReviewQueue(status: string = 'pending') {
    reviewQueueLoading.value = true
    try {
      const data = validateEvolution(
        await request.get(`/evolution/review-queue`, { params: { status } }) as ReviewQueueItem[],
        evolutionSchema, '/evolution/review-queue', 'ReviewQueueItem',
      ) as ReviewQueueItem[]
      reviewQueue.value = Array.isArray(data) ? data : []
    } catch (e: unknown) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch review queue:', e)
      reviewQueue.value = []
    } finally {
      reviewQueueLoading.value = false
    }
    return reviewQueue.value
  }

 // 快照联动 (E1): 指定岗位的 CII 历史（真实快照数据，非估算）
  const ciiHistory = ref<CiiHistoryEntry[]>([])
  const ciiHistoryLoading = ref(false)
  const ciiHistoryPosition = ref('')
  async function fetchCiiHistory(position: string) {
    if (!position) { ciiHistory.value = []; ciiHistoryPosition.value = ''; return ciiHistory.value }
    ciiHistoryLoading.value = true
    ciiHistoryPosition.value = position
    try {
      const data = await request.get<{ position?: string; history?: CiiHistoryEntry[] }>(
        `/evolution/cii-history/${encodeURIComponent(position)}`,
      ) as { position?: string; history?: CiiHistoryEntry[] }
      ciiHistory.value = data.history ?? []
    } catch (e: unknown) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch CII history:', e)
      ciiHistory.value = []
    } finally {
      ciiHistoryLoading.value = false
    }
    return ciiHistory.value
  }

 // 10-03 : manual refresh — fire all dashboard fetches concurrently
  async function refreshAll() {
    await Promise.all([
      fetchTrends(),
      fetchSnapshots(),
      fetchEmergingAlerts(),
      fetchKpi(),
    ])
  }

  return {
    loading,
    trendItems,
    snapshotsLoading,
    snapshots,
    changelogLoading,
    changelogData,
    emergingAlerts,
    alertsLoading,
    kpi,
    kpiLoading,
    reviewQueue,
    reviewQueueLoading,
    ciiHistory,
    ciiHistoryLoading,
    ciiHistoryPosition,
    fetchTrends,
    fetchKpi,
    analyze,
    fetchSnapshots,
    fetchChangelog,
    fetchEmergingAlerts,
    fetchReviewQueue,
    fetchCiiHistory,
    refreshAll,
  }
})
