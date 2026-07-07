/**
 * Evolution chart options — extracted from EvolutionDashboard.vue (audit M16)
 */
import { computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { chartColors, tooltipStyle, splitLineStyle, gaugeColor, legendStyle } from '@/utils/chartTheme'
import type { TrendItem } from '@/stores/evolution'

export function useEvolutionCharts(
  items: ComputedRef<TrendItem[]>,
  quarters: ComputedRef<string[]>,
  selectedSkill: Ref<string>,
  compareSkillA: Ref<string>,
  compareSkillB: Ref<string>,
) {
  const SERIES_COLORS = chartColors().chart

  // Top 10 CII time-series line chart
  const chartOption = computed(() => {
    const filtered = selectedSkill.value
      ? items.value.filter(i => i.skill_name === selectedSkill.value)
      : items.value.slice(0, 10)

    return {
      color: SERIES_COLORS,
      tooltip: {
        trigger: 'axis',
        // eslint-disable-next-line @typescript-eslint/no-explicit-any — echarts callback type
        formatter: (params: any[]) => {
          return params.map(p =>
            `${p.marker} ${p.seriesName}: <b>${p.value}</b>`
          ).join('<br/>')
        },
      },
      legend: {
        bottom: 0,
        data: filtered.map(i => i.skill_name),
        textStyle: { fontSize: 13 },
      },
      grid: { left: 50, right: 30, top: 30, bottom: 50 },
      xAxis: {
        type: 'category',
        data: quarters.value,
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        name: 'CII',
        min: 60,
        max: 220,
        splitLine: splitLineStyle(),
      },
      series: filtered.map(i => ({
        name: i.skill_name,
        type: 'line',
        data: i.points,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 3 },
        emphasis: { focus: 'series' },
      })),
    }
  })

  // Emerging skills (rising + high confidence)
  const emergingSkills = computed(() => {
    return items.value
      .filter(i => i.trend === 'rising')
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 6)
  })

  // CII gauge (average CII of all rising skills)
  const ciiGaugeOption = computed(() => {
    if (!items.value.length) return {}
    const latestValues = items.value.map(i => i.points?.[i.points.length - 1] ?? 100)
    const avgCii = latestValues.reduce((s, v) => s + v, 0) / latestValues.length
    return {
      series: [{
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 60,
        max: 200,
        progress: { show: true, width: 18, itemStyle: { color: gaugeColor(avgCii) } },
        axisLine: { lineStyle: { width: 18, color: [[0.3, chartColors().success], [0.7, chartColors().warning], [1, chartColors().danger]] } },
        axisTick: { show: false },
        splitLine: { length: 10, lineStyle: { width: 2, color: chartColors().muted } },
        axisLabel: { distance: 25, color: chartColors().muted, fontSize: 11 },
        pointer: { itemStyle: { color: 'auto' } },
        title: { show: true, offsetCenter: [0, '70%'], fontSize: 14, color: chartColors().muted },
        detail: { valueAnimation: true, formatter: '{value}', fontSize: 28, offsetCenter: [0, '40%'], color: 'inherit' },
        data: [{ value: Math.round(avgCii * 10) / 10, name: '平均 CII 指数' }],
      }],
    }
  })

  // Skill comparison chart
  const compareOption = computed(() => {
    if (!compareSkillA.value || !compareSkillB.value) return null
    const itemA = items.value.find(i => i.skill_name === compareSkillA.value)
    const itemB = items.value.find(i => i.skill_name === compareSkillB.value)
    if (!itemA || !itemB) return null
    return {
      tooltip: { ...tooltipStyle(), trigger: 'axis' },
      legend: { data: [compareSkillA.value, compareSkillB.value], bottom: 0, textStyle: legendStyle() },
      grid: { left: 50, right: 30, top: 30, bottom: 40 },
      xAxis: { type: 'category', data: quarters.value, boundaryGap: false },
      yAxis: { type: 'value', name: 'CII', splitLine: splitLineStyle() },
      series: [
        { name: compareSkillA.value, type: 'line', data: itemA.points, smooth: true, lineStyle: { width: 3, color: chartColors().primary }, itemStyle: { color: chartColors().primary } },
        { name: compareSkillB.value, type: 'line', data: itemB.points, smooth: true, lineStyle: { width: 3, color: chartColors().danger }, itemStyle: { color: chartColors().danger } },
      ],
    }
  })

  return { chartOption, emergingSkills, ciiGaugeOption, compareOption }
}
