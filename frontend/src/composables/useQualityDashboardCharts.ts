/**
 * QualityDashboard chart options + KPI cards + auto-refresh — extracted from QualityDashboard.vue ( D)
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
 /**: 口径拆解行（沿 KPI breakdown）*/
  caption: string
 /** 新手友好 tooltip：完整说明这个数是什么 + 怎么算 + 解读阈值 */
  tooltip: string
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
 //: 口径拆解行（沿 KPI breakdown 原则——计算依据可感知）
 // 幻觉率三段式（）：X / Y = Z%——前端不再重新算率，避免口径漂移
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
        tooltip: `📊 图谱规模：当前 StarMap 数据库中岗位 + 技能节点总数。\n\n` +
          `• 数字越大 = 覆盖面越广\n` +
          `• 「周新增 +N」反映本周增量\n` +
          `• 健康标准：周新增 > 0 表示系统在持续抽取\n` +
          `• 数据源：Neo4j Skill/Position 节点`,
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
        caption: `四因子综合信任度均值（来源多样性 / 抽取置信 / 多源验证 / 时间衰减）`,
        tooltip: `🎯 数据可信度：所有技能节点信任度的平均值（0-100%）。\n\n` +
          `• ≥ 75% = 健康（绿）\n` +
          `• 50-75% = 中等（黄）\n` +
          `• < 50% = 需关注（红）\n\n` +
          `⚠️ 本页与「演化分析」页中的信任均值口径不同：此处为技能节点的实时均值，「演化分析」为变更事件的均值。`,
        trend: m.avg_trust_score >= 0.75 ? 'up' : 'down',
        color: cc.success,
        icon: 'DataLine',
      },
      {
        label: '幻觉率',
        value: (m.hallucination_rate * 100).toFixed(1) + '%',
        sub: auditRateLabel,
        caption: hallucinationCaption,
        tooltip: `🌀 抽取可靠性：抽取结果中"幻觉技能"的占比。\n\n` +
          `• ≤ 8% = 健康\n` +
          `• 8-15% = 需关注\n` +
          `• > 15% = 严重，建议触发质量评估重新校准\n\n` +
          `公式：近 30 天窗口内，幻觉技能数 ÷ 总抽取数`,
        // 2026-08-20 (debug 修复 Q1): 原 `<=0.08 ? 'down'` 被模板渲染为红色 ▼，
        // 低幻觉率(好事)显示红↓、高幻觉率(坏事)显示绿↑ —— 好坏与红绿完全反转。
        // 改为 up=好(绿▲)、down=坏(红▼)，与 avg_trust_score 卡语义一致。
        trend: m.hallucination_rate <= 0.08 ? 'up' : 'down',
        color: cc.warning,
        icon: 'WarningFilled',
      },
      {
        label: '待审核',
        value: m.pending_review === 0 ? '—' : String(m.pending_review),
        sub: m.pending_review === 0 ? '暂无记录' : '条记录待处理',
 // 2026-08-14: 口径对齐 admin 内容审核（review_service 状态机）——pending_review
 // 计数 = position_records + skill_records。修复前文案误标 JDExtractionRecord.confidence
        caption: `岗位与技能待审核计数（与管理后台的内容审核同源）`,
        tooltip: `👥 人工监督：等待人工审核的岗位与技能记录数。\n\n` +
          `• 0 = 无需人工干预（绿）\n` +
          `• 1-5 = 可逐条审核（黄）\n` +
          `• > 5 = 队列拥堵，建议批量审核或调整抽取策略\n\n` +
          `下方队列展示最近 20 条，完整队列请在「管理后台 → 内容审核」处理`,
        // 2026-08-20 (debug 修复 Q1): 原 `>5 ? 'up'` 使队列拥堵(坏事)显示绿↑、
        // 队列清空(好事)显示红↓ —— 反转。改为 up=好(绿▲)、down=坏(红▼)。
        trend: m.pending_review > 5 ? 'down' : 'up',
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
 // Y 轴上限动态: 保底 20%(维持 10% 预警线的健康分级视觉), 但容纳真实数据峰值
 // (修复前硬编码 max:20 —— 一旦某天幻觉率 >20% 会被裁剪成"顶格", 掩盖真实告警)
    const peak = Math.max(...trend.map(t => t.rate * 100), 0)
    const yMax = Math.max(20, Math.ceil(peak * 1.2 / 5) * 5)
    return {
      tooltip: { trigger: 'axis' },
      grid: { top: 20, bottom: 28, left: 50, right: 20 },
      xAxis: { type: 'category', data: trend.map(t => t.date) },
      yAxis: { type: 'value', name: '幻觉率 (%)', min: 0, max: yMax },
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

  watch(enabled, () => {
    if (enabled.value) start()
    else stop()
  })

  onUnmounted(stop)

  return { lastRefresh, start, stop }
}
