/**
 * DataDashboard 6 KPI card definitions — extracted from DataDashboard.vue (Phase 7 D, post-M15)
 * Pure computed over the dashboard store. No timers, no SSE.
 */
import { computed, type ComputedRef } from 'vue'
import { chartColors } from '@/utils/chartTheme'
import type { useDashboardStore } from '@/stores/dashboard'

type DashboardStore = ReturnType<typeof useDashboardStore>

export interface KpiCardDef {
  label: string
  target: number
  suffix: string
  decimals: number
  icon: string
  color: string
  glow: string
  route: string
}

export function useDashboardKpiCards(store: DashboardStore): ComputedRef<KpiCardDef[]> {
  return computed(() => {
    const cc = chartColors()
    return [
      {
        label: '总节点数',
        target: store.overview?.total_nodes ?? 0,
        suffix: '',
        decimals: 0,
        icon: '⬡',
        color: cc.chart[0],
        glow: cc.chart[0] + '40',
        route: '/',
      },
      {
        label: '总关系数',
        target: store.overview?.total_edges ?? 0,
        suffix: '',
        decimals: 0,
        icon: '◇',
        color: cc.chart[2],
        glow: cc.chart[2] + '40',
        route: '/',
      },
      {
        label: '技能域',
        target: store.overview?.total_domains ?? 0,
        suffix: '',
        decimals: 0,
        icon: '◈',
        color: cc.success,
        glow: cc.success + '40',
        route: '/learning',
      },
      {
        label: '岗位数',
        target: store.overview?.total_positions ?? 0,
        suffix: '',
        decimals: 0,
        icon: '◉',
        color: cc.danger,
        glow: cc.danger + '40',
        route: '/positions',
      },
      {
        label: '技能数',
        target: store.overview?.total_skills ?? 0,
        suffix: '',
        decimals: 0,
        icon: '◆',
        color: cc.warning,
        glow: cc.warning + '40',
        route: '/quality',
      },
      {
        label: '信任评分',
        target: (store.overview?.trust_score ?? 0) * 100,
        suffix: '%',
        decimals: 1,
        icon: '★',
        color: cc.info,
        glow: cc.info + '40',
        route: '/quality',
      },
    ]
  })
}
