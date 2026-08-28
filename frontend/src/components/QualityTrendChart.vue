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
      data: ['质量分', '幻觉率', '审核量'],
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
        name: '质量分',
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
        // 2026-08-28 (质量趋势根因修复): max 20 硬编码会在数据 > 20% 时把线画出轴
        // (44.6% 显示在 100% 处看起来爆表)。改为动态: max(数据最大值*1.2, 20)。
        max: Math.max(20, ...props.data.map(d => +(d.hallucination_rate * 100).toFixed(1) * 1.2)),
        axisLabel: { ...axisLabelStyle(), formatter: '{value}%' },
        splitLine: { show: false },
      },
      {
        type: 'value',
        name: '审核量',
        position: 'right',
        offset: 52,
        min: 0,
        axisLabel: { ...axisLabelStyle(), formatter: '{value}' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '质量分',
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
        // 2026-08-28 (质量趋势根因修复): 独立右轴(yAxisIndex:2) —— 审核量是
        // 0-1000s 的计数, 原绘于 0-100% 左轴导致数值贴底 ≈0 误导。
        yAxisIndex: 2,
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
    <!-- 2026-08-28 (UI 重叠修复): 移除组件内 trend-header —— "质量趋势"标题与
         周期 tag 由父级 QualityDashboard 的 .trend-controls(radio 7/30/90天) 承担,
         两层右端控件垂直挤叠。组件只渲染图表。 -->
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
      <p class="empty-text">
        暂无趋势数据
      </p>
      <p class="empty-hint-text">
        质量趋势将在数据采集后展示
      </p>
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
