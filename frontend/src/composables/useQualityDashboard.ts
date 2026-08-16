/**
 * QualityDashboard page-level orchestration — extracted from QualityDashboard.vue
 *. Owns: activeTab ref + onMounted initial data fetch +
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
  // P2 fix (functional-review 2026-08-13): 默认 activeTab 此前为 'overview'，
  // 而 QualityDashboard.vue 的 el-tab-pane 只有 'trend'/'alert' 两个 → 首屏
  // 无激活 pane，质量趋势/异常告警区域空白，需用户点击后才显示。改为 'trend'。
  const activeTab: Ref<string> = ref('trend')
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
