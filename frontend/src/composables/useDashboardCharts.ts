/**
 * DataDashboard chart option computeds — extracted from DataDashboard.vue (M15)
 * All chart options are pure computeds reading from the dashboard store.
 */
import { computed } from 'vue'
import type { ComputedRef } from 'vue'
import { chartColors, tooltipStyle } from '@/utils/chartTheme'
import { ECHARTS_PALETTE } from '@/utils/graphColors'
import type { useDashboardStore, SkillDomain, QualityTrend } from '@/stores/dashboard'
import type { EmergingSkill } from '@/types/evolution'

type DashboardStore = ReturnType<typeof useDashboardStore>

export function useDashboardCharts(store: DashboardStore) {
  const cc = chartColors()

  // ── Data source pie chart (dark theme) ──
  const darkPieOption = computed(() => {
    const data = store.sourceDistribution
    if (!data?.length) {
      return undefined
    }
    const palette = [cc.chart[0], cc.chart[2], cc.success, cc.danger, cc.warning, cc.info, cc.primary, cc.chart[4]]
    return {
      tooltip: {
        trigger: 'item',
        ...tooltipStyle(),
        formatter: '{b}: {c} 条 ({d}%)',
      },
      legend: {
        bottom: 4,
        textStyle: { color: cc.muted, fontSize: 10 },
        itemWidth: 10,
        itemHeight: 10,
      },
      animationDuration: 1200,
      animationEasing: 'cubicOut' as const,
      animationDelay: (_idx: number) => _idx * 80,
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: ECHARTS_PALETTE.PIE_BORDER,
          borderWidth: 2,
        },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 13, fontWeight: 'bold', color: cc.foreground },
          itemStyle: {
            shadowBlur: 20,
            shadowColor: cc.chart[0] + '66',
          },
        },
        data: data.map((s: { name: string; count: number }, i: number) => ({
          name: s.name,
          value: s.count,
          itemStyle: { color: palette[i % palette.length] },
        })),
      }],
    }
  })

  // ── Skill domain treemap ──
  const treemapOption = computed(() => {
    const data = store.skillDomains
    if (!data?.length) {
      return undefined
    }
    return {
      tooltip: {
        backgroundColor: cc.card + 'E6',
        borderColor: cc.chart[0] + '4D',
        textStyle: { color: cc.foreground, fontSize: 12 },
        formatter: '{b}: {c}',
      },
      series: [{
        type: 'treemap',
        data: data.map((d: SkillDomain) => ({
          name: d.name,
          value: d.value,
          children: d.children?.map((c: SkillDomain) => ({
            name: c.name,
            value: c.value,
          })),
        })),
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: '{b}',
          fontSize: 11,
          color: ECHARTS_PALETTE.LABEL,
          textShadowColor: 'rgba(0,0,0,0.6)',
          textShadowBlur: 4,
        },
        itemStyle: {
          borderColor: ECHARTS_PALETTE.PIE_BORDER,
          borderWidth: 2,
          gapWidth: 2,
        },
        levels: [{
          itemStyle: {
            borderColor: ECHARTS_PALETTE.PIE_BORDER,
            borderWidth: 3,
            gapWidth: 3,
          },
        }, {
          colorSaturation: [0.35, 0.5],
          itemStyle: {
            borderColorSaturation: 0.6,
            gapWidth: 1,
            borderWidth: 1,
          },
        }],
        color: [cc.chart[0], cc.chart[2], cc.success, cc.danger, cc.warning, cc.info, cc.primary, cc.chart[4]],
      }],
    }
  })

  // ── Quality trend dual-axis line chart ──
  const trendOption = computed(() => {
    const trends = store.qualityTrends
    if (!trends?.length) return undefined
    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: cc.card + 'E6',
        borderColor: cc.chart[0] + '4D',
        textStyle: { color: cc.foreground, fontSize: 12 },
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: cc.muted, fontSize: 10 },
        itemWidth: 12,
        itemHeight: 2,
      },
      grid: { top: 30, bottom: 24, left: 40, right: 40 },
      xAxis: {
        type: 'category',
        data: trends.map((t: QualityTrend) => t.date.slice(5)),
        axisLine: { lineStyle: { color: cc.foreground + '26' } },
        axisLabel: { color: cc.muted, fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: 'value',
          name: '分值',
          nameTextStyle: { color: cc.muted, fontSize: 10 },
          axisLabel: { color: cc.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: cc.foreground + '0F' } },
        },
        {
          type: 'value',
          name: '采集量',
          nameTextStyle: { color: cc.muted, fontSize: 10 },
          axisLabel: { color: cc.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '质量分',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { color: cc.chart[0], width: 2 },
          itemStyle: { color: cc.chart[0] },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: cc.chart[0] + '33' },
                { offset: 1, color: cc.chart[0] + '00' },
              ],
            },
          },
          data: trends.map((t: QualityTrend) => t.quality_score),
        },
        {
          name: '信任分',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { color: cc.success, width: 2 },
          itemStyle: { color: cc.success },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: cc.success + '26' },
                { offset: 1, color: cc.success + '00' },
              ],
            },
          },
          data: trends.map((t: QualityTrend) => t.trust_score),
        },
        {
          name: '采集量',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: cc.warning, width: 1.5, type: 'dashed' },
          itemStyle: { color: cc.warning },
          data: trends.map((t: QualityTrend) => t.crawl_volume),
        },
      ],
    }
  })

  // ── Emerging skills radar ──
  const radarOption = computed(() => {
    const skills = store.emergingSkills
    if (!skills?.length) return undefined
    const top = skills.slice(0, 6)
    // Map backend field names to display names for radar indicators
    const displayNames = top.map((s: EmergingSkill) => s.skill_name ?? s.name ?? 'unknown')
    return {
      tooltip: {
        backgroundColor: cc.card + 'E6',
        borderColor: cc.chart[0] + '4D',
        textStyle: { color: cc.foreground, fontSize: 12 },
      },
      radar: {
        indicator: displayNames.map((name: string) => ({
          name,
          max: 100,
        })),
        shape: 'polygon',
        splitNumber: 4,
        axisName: {
          color: cc.muted,
          fontSize: 10,
        },
        splitLine: {
          lineStyle: { color: cc.foreground + '14' },
        },
        splitArea: {
          areaStyle: {
            color: [cc.chart[0] + '05', cc.chart[0] + '0A', cc.chart[0] + '05', cc.chart[0] + '0A'],
          },
        },
        axisLine: {
          lineStyle: { color: cc.foreground + '1A' },
        },
      },
      series: [{
        type: 'radar',
        data: [
          {
            // z_score normalized to 0-100 scale; fallback to growth_rate
            value: top.map((s: EmergingSkill) => Math.round(Math.min(100, Math.abs(s.z_score ?? (s.growth_rate ?? 0)) * 20))),
            name: 'Z-score',
            lineStyle: { color: cc.chart[0], width: 2 },
            itemStyle: { color: cc.chart[0] },
            areaStyle: { color: cc.chart[0] + '26' },
          },
          {
            // source_count normalized; fallback to relevance
            value: top.map((s: EmergingSkill) => Math.round(Math.min(100, ((s.source_count ?? 0) / 10) * 100 || (s.relevance ?? 0) * 100))),
            name: '来源数',
            lineStyle: { color: cc.chart[2], width: 2 },
            itemStyle: { color: cc.chart[2] },
            areaStyle: { color: cc.chart[2] + '1F' },
          },
        ],
      }],
    }
  })

  return { darkPieOption, treemapOption, trendOption, radarOption }
}
