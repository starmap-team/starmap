<script setup lang="ts">
/**
 * 市场竞争力分析图表 — ECharts 条形图
 * 对比你的技能水平 vs 市场平均水平 vs 市场需求
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { chartColors, tooltipStyle, splitLineStyle, legendStyle } from '@/utils/chartTheme'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface CompetitivenessItem {
  skill: string
  market_demand: number
  your_level: number
  avg_level: number
}

const props = defineProps<{
  data: CompetitivenessItem[]
}>()

const chartOption = computed(() => {
  if (!props.data.length) return null

  const skills = props.data.map(d => d.skill)
  const colors = chartColors()

  return {
    color: [colors.primary, colors.danger, colors.warning],
    tooltip: {
      ...tooltipStyle(),
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: ['你的水平', '市场平均', '市场需求'],
      bottom: 0,
      textStyle: legendStyle(),
    },
    grid: {
      left: 100,
      right: 30,
      top: 20,
      bottom: 50,
    },
    xAxis: {
      type: 'value',
      max: 100,
      name: '水平/需求指数',
      splitLine: splitLineStyle(),
    },
    yAxis: {
      type: 'category',
      data: skills,
      axisLabel: {
        color: colors.muted,
        fontSize: 12,
      },
    },
    series: [
      {
        name: '你的水平',
        type: 'bar',
        data: props.data.map(d => d.your_level),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
        },
      },
      {
        name: '市场平均',
        type: 'bar',
        data: props.data.map(d => d.avg_level),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
        },
      },
      {
        name: '市场需求',
        type: 'bar',
        data: props.data.map(d => d.market_demand),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="competitiveness-chart">
    <VChart
      v-if="chartOption"
      :option="chartOption"
      autoresize
      class="chart-instance"
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
          <rect
            x="3"
            y="3"
            width="18"
            height="18"
            rx="2"
          />
          <path d="M3 9h18" />
          <path d="M9 21V9" />
        </svg>
      </div>
      <p class="empty-text">
        暂无竞争力数据
      </p>
      <p class="empty-hint-text">
        选择目标岗位后将展示技能竞争力分析
      </p>
    </div>
  </div>
</template>

<style scoped>
.competitiveness-chart {
  width: 100%;
}
.chart-instance {
  height: 400px;
}
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-4);
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
