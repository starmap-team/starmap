/**
 * QualityDashboard chart options + KPI cards + auto-refresh — extracted from QualityDashboard.vue (Phase 7 D)
 * Pure computeds reading from the quality store.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { chartColors, tooltipStyle, legendStyle } from '@/utils/chartTheme'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import type { useQualityStore } from '@/stores/quality'

type QualityStore = ReturnType<typeof useQualityStore>

export type KpiTrend = 'up' | 'down'
export interface KpiCardEnhanced {
  label: string
  value: string
  sub: string
  trend: KpiTrend
  color: string
  icon: string
}

export function useQualityDashboardCharts(store: QualityStore) {
  const cc = chartColors()

  const kpiCardsEnhanced: ComputedRef<KpiCardEnhanced[]> = computed(() => {
    const m = store.metrics
    if (!m) return []
    return [
      {
        label: '总节点数',
        value: m.total_nodes.toLocaleString(),
        sub: `周新增 +${m.weekly_new_nodes}`,
        trend: 'up',
        color: cc.primary,
        icon: 'Grid',
      },
      {
        label: '平均信任度',
        value: (m.avg_trust_score * 100).toFixed(1) + '%',
        sub: `高信任占比 ${(m.high_trust_ratio * 100).toFixed(0)}%`,
        trend: m.avg_trust_score >= 0.75 ? 'up' : 'down',
        color: cc.success,
        icon: 'DataLine',
      },
      {
        label: '幻觉率',
        value: (m.hallucination_rate * 100).toFixed(1) + '%',
        sub: `审核通过率 ${(m.audit_pass_rate * 100).toFixed(0)}%`,
        trend: m.hallucination_rate <= 0.08 ? 'down' : 'up',
        color: cc.warning,
        icon: 'WarningFilled',
      },
      {
        label: '待审核',
        value: String(m.pending_review),
        sub: '条记录待处理',
        trend: m.pending_review > 5 ? 'up' : 'down',
        color: cc.danger,
        icon: 'Clock',
      },
    ]
  })

  const histogramOption: ComputedRef<Record<string, unknown>> = computed(() => {
    const dist = store.metrics?.trust_distribution
    if (!dist) return {}
    return {
      tooltip: { ...tooltipStyle(), trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { top: 16, bottom: 36, left: 48, right: 16 },
      xAxis: { type: 'category', name: '信任度区间', data: dist.map(d => d.range), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '节点数' },
      series: [{
        type: 'bar',
        data: dist.map((d, i) => ({
          value: d.count,
          itemStyle: {
            color: [cc.danger, cc.warning + '88', cc.warning, cc.success, cc.primary, cc.primary][i],
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barWidth: '65%',
        label: { show: true, position: 'top', fontSize: 11, color: cc.muted },
      }],
    }
  })

  const trendChartOption: ComputedRef<Record<string, unknown>> = computed(() => {
    const trend = store.metrics?.hallucination_trend
    if (!trend) return {}
    return {
      tooltip: { trigger: 'axis' },
      grid: { top: 20, bottom: 28, left: 50, right: 20 },
      xAxis: { type: 'category', data: trend.map(t => t.date) },
      yAxis: { type: 'value', name: '幻觉率 (%)', min: 0, max: 20 },
      series: [{
        type: 'line',
        data: trend.map(t => ({ value: +(t.rate * 100).toFixed(1) })),
        smooth: true,
        areaStyle: { opacity: 0.12, color: cc.warning },
        lineStyle: { color: cc.warning, width: 2.5 },
        itemStyle: { color: cc.warning },
        symbolSize: 6,
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{
            yAxis: 10,
            label: { formatter: '预警线 10%', fontSize: 11 },
            lineStyle: { color: cc.danger, type: 'dashed', width: 2 },
          }],
        },
      }],
    }
  })

  const sourceChartOption: ComputedRef<Record<string, unknown>> = computed(() => {
    const dist = store.metrics?.source_distribution
    if (!dist) return {}
    return {
      tooltip: { ...tooltipStyle(), trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
      legend: { bottom: 0, textStyle: legendStyle() },
      series: [{
        type: 'pie',
        radius: ['48%', '75%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: cc.card, borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
          itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.25)' },
        },
        data: dist.map(s => ({ name: getSourceNameLabel(s.name), value: s.count })),
      }],
    }
  })

  return { kpiCardsEnhanced, histogramOption, trendChartOption, sourceChartOption }
}

/** Auto-refresh loop. Returns lastRefresh timestamp and a stopper handle. */
export function useQualityAutoRefresh(
  store: QualityStore,
  intervalSeconds: Ref<number>,
  enabled: Ref<boolean>,
) {
  const lastRefresh: Ref<string> = ref('')
  let timer: ReturnType<typeof setInterval> | null = null

  function start() {
    stop()
    if (!enabled.value) return
    timer = setInterval(() => {
      void store.fetchQuality().then(() => {
        lastRefresh.value = new Date().toLocaleTimeString()
      })
    }, intervalSeconds.value * 1000)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  // ponytail: caller must invoke start() on mount; watch handles toggle changes.
  watch(enabled, () => {
    if (enabled.value) start()
    else stop()
  })

  onUnmounted(stop)

  return { lastRefresh, start, stop }
}
