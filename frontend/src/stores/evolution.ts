/**
 * Evolution store — shared fetch logic for evolution-related pages
 * Replaces direct `request` calls in EvolutionDashboard.vue (audit B5)
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { ChangeType } from '@/types/evolution'

import { useResponseValidation } from '@/validation/useResponseValidation'
import evolutionSchema from '../../../starmap-contracts/schemas/evolution.schema.json'

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
  before_value: string | null
  after_value: string | null
  confidence: number
  detected_at: string
  // Optional fields returned by some API endpoints / used in UI
  date?: string
  created_at?: string
  old_proficiency?: string
  new_proficiency?: string
  old_requirement?: string
  new_requirement?: string
  description?: string
  trust_score?: number
}

// LOOP-06: Emerging alert type for evolution alerts
// ALIGN-05: Added missing fields from backend (source_count, trend, portability_score)
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

  async function fetchTrends(days?: number) {
    loading.value = true
    try {
      const params = days ? { days } : undefined
      const data = await request.get<{ items?: TrendItem[] }>('/evolution/trends', { params })
      trendItems.value = data.items ?? []
    } finally {
      loading.value = false
    }
    return { items: trendItems.value }
  }

  async function fetchSnapshots(limit = 50) {
    snapshotsLoading.value = true
    try {
      const data = await request.get(`/evolution/snapshots?limit=${limit}`)
      const list = Array.isArray(data) ? data : []
      snapshots.value = [...list].sort((a, b) =>
        String(a.snapshot_date).localeCompare(String(b.snapshot_date))
      ) as SnapshotEntry[]
    } finally {
      snapshotsLoading.value = false
    }
    return snapshots.value
  }

  // UX-04: Renamed parameter — backend 'identifier' accepts both position and skill names
  async function fetchChangelog(identifier: string) {
    changelogLoading.value = true
    try {
      const raw = await request.get(`/evolution/changelog/${encodeURIComponent(identifier)}`) as unknown
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

  return {
    loading,
    trendItems,
    snapshotsLoading,
    snapshots,
    changelogLoading,
    changelogData,
    emergingAlerts,
    alertsLoading,
    fetchTrends,
    fetchSnapshots,
    fetchChangelog,
    fetchEmergingAlerts,
  }
})
