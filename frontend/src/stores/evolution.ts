/**
 * Evolution store — shared fetch logic for evolution-related pages
 * Replaces direct `request` calls in EvolutionDashboard.vue (audit B5)
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

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
  change_type: string
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

export const useEvolutionStore = defineStore('evolution', () => {
  const loading = ref(false)
  const quarters = ref<string[]>([])
  const trendItems = ref<TrendItem[]>([])

  const snapshotsLoading = ref(false)
  const snapshots = ref<SnapshotEntry[]>([])

  const changelogLoading = ref(false)
  const changelogData = ref<ChangelogEntry[]>([])

  async function fetchTrends(days?: number) {
    loading.value = true
    try {
      const params = days ? { days } : undefined
      const data = await request.get('/evolution/trends', { params }) as unknown as Record<string, unknown>
      quarters.value = data.quarters as string[] ?? []
      trendItems.value = data.items as TrendItem[] ?? []
    } finally {
      loading.value = false
    }
    return { quarters: quarters.value, items: trendItems.value }
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

  async function fetchChangelog(skillName: string) {
    changelogLoading.value = true
    try {
      const raw = await request.get(`/evolution/changelog/${encodeURIComponent(skillName)}`) as unknown
      const data = raw as Record<string, unknown>
      changelogData.value = (Array.isArray(raw)
        ? raw
        : data.changelog ?? data.items ?? []) as ChangelogEntry[]
    } finally {
      changelogLoading.value = false
    }
    return changelogData.value
  }

  return {
    loading,
    quarters,
    trendItems,
    snapshotsLoading,
    snapshots,
    changelogLoading,
    changelogData,
    fetchTrends,
    fetchSnapshots,
    fetchChangelog,
  }
})
