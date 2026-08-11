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
  /** Phase 11 D-03: 口径拆解行（沿 M10 KPI breakdown）*/
  caption: string
  trend: KpiTrend
  color: string
  icon: string
}

export function useQualityDashboardCharts(store: QualityStore) {
  const cc = chartColors()

  const kpiCardsEnhanced: ComputedRef<KpiCardEnhanced[]> = computed(() => {
    const m = store.metrics
    if (!m) return []
    // QA P3-C: when the audit queue is empty, the static "0%" subtitle is
    // misleading — render an honest "— 暂无审核" placeholders instead.
    const auditRateLabel =
      m.pending_review === 0
        ? '— 暂无审核'
        : `审核通过率 ${(m.audit_pass_rate * 100).toFixed(0)}%`
    // Phase 11 D-03: 口径拆解行（沿 M10 KPI breakdown 原则——计算依据可感知）
    // 幻觉率三段式（D-05）：X / Y = Z%——前端不再重新算率，避免口径漂移
    const hallucinationCaption =
      m.hallucination_denominator === 0
        ? '— 未评估'
        : `${m.hallucination_numerator} / ${m.hallucination_denominator} = ${(m.hallucination_rate * 100).toFixed(1)}%（窗口 ${m.hallucination_window_days}d）`
    return [
      {
        label: '总节点数',
        value: m.total_nodes.toLocaleString(),
        sub: m.total_extractions === 0
          ? '— 待运行抽取'
          : `周新增 +${m.weekly_new_nodes}`,
        caption: `Position + Skill 节点数（来源: ${m.total_positions} 岗位 / ${m.total_skills} 技能）`,
        trend: 'up',
        color: cc.primary,
        icon: 'Grid',
      },
      {
        label: '平均信任度',
        value: (m.avg_trust_score * 100).toFixed(1) + '%',
        sub: m.total_extractions === 0
          ? '— 待评估'
          : `高信任占比 ${(m.high_trust_ratio * 100).toFixed(0)}%`,
        caption: `Neo4j Skill.trust_score 均值（来源: avg_skill_trust 共享指标模块）`,
        trend: m.avg_trust_score >= 0.75 ? 'up' : 'down',
        color: cc.success,
        icon: 'DataLine',
      },
      {
        label: '幻觉率',
        value: (m.hallucination_rate * 100).toFixed(1) + '%',
        sub: auditRateLabel,
        caption: hallucinationCaption,
        trend: m.hallucination_rate <= 0.08 ? 'down' : 'up',
        color: cc.warning,
        icon: 'WarningFilled',
      },
      {
        label: '待审核',
        value: m.pending_review === 0 ? '—' : String(m.pending_review),
        sub: m.pending_review === 0 ? '暂无记录' : '条记录待处理',
        caption: `JDExtractionRecord.confidence < ${0.5 * 100}% 阈值命中数（来源: ReviewAuditLog）`,
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
