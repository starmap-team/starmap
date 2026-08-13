/**
 * QualityDashboard user actions — trend period, alert resolve/ignore, auto-refresh toggle.
 * Extracted from QualityDashboard.vue (Phase 7 D round 4).
 * Toast messages owned by ElMessage — kept inline for ops visibility.
 *
 * 2026-08-13 (全盘友好性): 告警"解决/忽略"原只改前端内存（刷新即失效）→ 改调后端
 * POST /quality/alerts/handle 持久化到 Redis，跨刷新保留后重新拉取。
 */
import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
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

  async function handleAlert(id: string | number, action: 'resolve' | 'ignore'): Promise<void> {
    try {
      await request.post('/quality/alerts/handle', { id: String(id), action })
      await store.fetchAlerts()
      ElMessage.success(action === 'resolve' ? '告警已解决' : '告警已忽略')
    } catch {
      ElMessage.error('告警处理失败，请重试')
    }
  }

  function handleResolveAlert(id: string | number): void {
    void handleAlert(id, 'resolve')
  }

  function handleIgnoreAlert(id: string | number): void {
    void handleAlert(id, 'ignore')
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
