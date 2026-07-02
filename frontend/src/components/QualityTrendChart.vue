<script setup lang="ts">
/**
 * 质量趋势折线图组件 — Sprint 1.2
 * 双 Y 轴：左侧信任度评分，右侧幻觉率
 * 支持 7d/30d/90d 周期切换
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle, legendStyle } from '@/utils/chartTheme'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, MarkLineComponent])

export interface TrendDataPoint {
  date: string
  trust_score: number
  hallucination_rate: number
  review_count: number
}

const props = defineProps<{
  data: TrendDataPoint[]
  period: '7d' | '30d' | '90d'
}>()

const periodLabel = computed(() => {
  const map: Record<string, string> = { '7d': '近7天', '30d': '近30天', '90d': '近90天' }
  return map[props.period] ?? props.period
})

const chartOption = computed(() => {
  if (!props.data?.length) return {}
  const colors = chartColors()
  return {
    tooltip: {
      ...tooltipStyle(),
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: colors.muted } },
    },
    legend: {
      data: ['信任度', '幻觉率', '审核量'],
      ...legendStyle(),
      top: 0,
    },
    grid: { top: 36, bottom: 32, left: 56, right: 56 },
    xAxis: {
      type: 'category',
      data: props.data.map(d => d.date),
      axisLabel: { ...axisLabelStyle(), rotate: props.data.length > 15 ? 30 : 0 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: [
      {
        type: 'value',
        name: '信任度',
        position: 'left',
        min: 0,
        max: 100,
        axisLabel: { ...axisLabelStyle(), formatter: '{value}%' },
        splitLine: splitLineStyle(),
      },
      {
        type: 'value',
        name: '幻觉率',
        position: 'right',
        min: 0,
        max: 20,
        axisLabel: { ...axisLabelStyle(), formatter: '{value}%' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '信任度',
        type: 'line',
        yAxisIndex: 0,
        data: props.data.map(d => +(d.trust_score * 100).toFixed(1)),
        smooth: true,
        lineStyle: { color: colors.primary, width: 2.5 },
        itemStyle: { color: colors.primary },
        areaStyle: { opacity: 0.08, color: colors.primary },
        symbolSize: 5,
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{
            yAxis: 80,
            label: { formatter: '优秀 80%', fontSize: 10 },
            lineStyle: { color: colors.success, type: 'dashed', width: 1.5 },
          }],
        },
      },
      {
        name: '幻觉率',
        type: 'line',
        yAxisIndex: 1,
        data: props.data.map(d => +(d.hallucination_rate * 100).toFixed(1)),
        smooth: true,
        lineStyle: { color: colors.warning, width: 2.5 },
        itemStyle: { color: colors.warning },
        areaStyle: { opacity: 0.08, color: colors.warning },
        symbolSize: 5,
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{
            yAxis: 10,
            label: { formatter: '预警 10%', fontSize: 10 },
            lineStyle: { color: colors.danger, type: 'dashed', width: 1.5 },
          }],
        },
      },
      {
        name: '审核量',
        type: 'line',
        yAxisIndex: 0,
        data: props.data.map(d => d.review_count),
        smooth: true,
        lineStyle: { color: colors.info, width: 1.5, type: 'dashed' },
        itemStyle: { color: colors.info },
        symbolSize: 4,
      },
    ],
  }
})
</script>

<template>
  <div class="quality-trend-chart">
    <div class="trend-header">
      <span class="trend-title">质量趋势</span>
      <el-tag
        size="small"
        effect="plain"
        round
      >
        {{ periodLabel }}
      </el-tag>
    </div>
    <VChart
      v-if="data?.length"
      :option="chartOption"
      style="height: 320px;"
      autoresize
    />
    <div
      v-else
      class="custom-empty"
    >
      <div class="empty-icon-wrapper">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      </div>
      <p class="empty-text">暂无趋势数据</p>
      <p class="empty-hint-text">质量趋势将在数据采集后展示</p>
    </div>
  </div>
</template>

<style scoped>
.quality-trend-chart {
  width: 100%;
}
.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.trend-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
}
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-3);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
</style>
