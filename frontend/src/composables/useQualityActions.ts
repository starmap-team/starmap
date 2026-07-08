/**
 * QualityDashboard user actions — trend period, alert resolve/ignore, auto-refresh toggle.
 * Extracted from QualityDashboard.vue (Phase 7 D round 4).
 * Toast messages owned by ElMessage — kept inline for ops visibility.
 */
import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { useQualityStore } from '@/stores/quality'

type QualityStore = ReturnType<typeof useQualityStore>
export type TrendPeriod = '7d' | '30d' | '90d'

export interface QualityActionsApi {
  trendPeriod: Ref<TrendPeriod>
  handleTrendPeriodChange: (period: TrendPeriod) => void
  handleResolveAlert: (id: string | number) => void
  handleIgnoreAlert: (id: string | number) => void
  toggleAutoRefresh: (enabled: boolean, intervalSeconds: number) => void
}

export function useQualityActions(store: QualityStore): QualityActionsApi {
  const trendPeriod: Ref<TrendPeriod> = ref<TrendPeriod>('7d')

  function handleTrendPeriodChange(period: TrendPeriod): void {
    trendPeriod.value = period
    void store.fetchTrends(period)
  }

  function handleResolveAlert(id: string | number): void {
    const alert = store.alerts.find(a => a.id === id)
    if (alert) {
      alert.status = 'resolved'
      ElMessage.success('告警已标记为解决')
    }
  }

  function handleIgnoreAlert(id: string | number): void {
    const alert = store.alerts.find(a => a.id === id)
    if (alert) {
      alert.status = 'ignored'
      ElMessage.info('告警已忽略')
    }
  }

  function toggleAutoRefresh(enabled: boolean, intervalSeconds: number): void {
    if (enabled) {
      ElMessage.success(`已开启自动刷新（每${intervalSeconds}秒）`)
    } else {
      ElMessage.info('已关闭自动刷新')
    }
  }

  return { trendPeriod, handleTrendPeriodChange, handleResolveAlert, handleIgnoreAlert, toggleAutoRefresh }
}
