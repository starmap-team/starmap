/**
 * QualityDashboard page-level orchestration — extracted from QualityDashboard.vue
 * (Phase 7 D round 11). Owns: activeTab ref + onMounted initial data fetch +
 * toggleAutoRefresh wrapper that bridges UI value to composable API.
 */
import { onMounted, ref, type Ref } from 'vue'
import type { useQualityStore } from '@/stores/quality'
import { useQualityAutoRefresh } from '@/composables/useQualityDashboardCharts'
import { useQualityActions } from '@/composables/useQualityActions'

type QualityStore = ReturnType<typeof useQualityStore>

export interface QualityDashboardApi {
  activeTab: Ref<string>
  autoRefresh: Ref<boolean>
  refreshInterval: Ref<number>
  lastRefresh: Ref<string>
  toggleAutoRefresh: (val: boolean) => void
  startAutoRefresh: () => void
}

export function useQualityDashboard(store: QualityStore): QualityDashboardApi {
  const activeTab: Ref<string> = ref('overview')
  const autoRefresh: Ref<boolean> = ref(true)
  const refreshInterval: Ref<number> = ref(30) // seconds

  const { lastRefresh, start: startAutoRefresh } = useQualityAutoRefresh(
    store,
    refreshInterval,
    autoRefresh,
  )

  const { toggleAutoRefresh: rawToggleAutoRefresh } = useQualityActions(store)

  function toggleAutoRefresh(val: boolean): void {
    autoRefresh.value = val
    rawToggleAutoRefresh(val, refreshInterval.value)
  }

  onMounted(() => {
    void store.fetchQuality().then(() => {
      lastRefresh.value = new Date().toLocaleTimeString()
    }).catch((err: unknown) => console.error('[useQualityDashboard] fetchQuality failed', err))
    void store.fetchTrends('7d')
    void store.fetchAlerts()
    startAutoRefresh()
  })

  return { activeTab, autoRefresh, refreshInterval, lastRefresh, toggleAutoRefresh, startAutoRefresh }
}
