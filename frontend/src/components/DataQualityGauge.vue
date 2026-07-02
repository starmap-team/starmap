<script setup lang="ts">
/**
 * 鏁版嵁璐ㄩ噺浠〃鐩樼粍浠? * ECharts gauge 浠〃鐩橈紝甯﹂鑹插尯闂村拰瓒嬪娍绠ご
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent, GraphicComponent } from 'echarts/components'
import { chartColors } from '@/utils/chartTheme'

use([GaugeChart, TooltipComponent, GraphicComponent])

const props = withDefaults(defineProps<{
  score: number
  label?: string
  trend?: 'up' | 'down' | 'stable'
}>(), {
  label: '鏁版嵁璐ㄩ噺',
  trend: 'stable',
})

const gaugeOption = computed(() => {
  const colors = chartColors()
  const val = Math.round(props.score)

  let trendColor = colors.muted
  if (props.trend === 'up') trendColor = colors.success
  else if (props.trend === 'down') trendColor = colors.danger

  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      radius: '85%',
      center: ['50%', '58%'],
      min: 0,
      max: 100,
      splitNumber: 10,
      axisLine: {
        lineStyle: {
          width: 20,
          color: [
            [0.6, colors.danger],
            [0.8, colors.warning],
            [1, colors.success],
          ],
        },
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '55%',
        width: 8,
        offsetCenter: [0, '-10%'],
        itemStyle: { color: 'auto' },
      },
      axisTick: {
        distance: -20,
        length: 6,
        lineStyle: { color: '#fff', width: 1.5 },
      },
      splitLine: {
        distance: -24,
        length: 14,
        lineStyle: { color: '#fff', width: 2 },
      },
      axisLabel: {
        color: colors.muted,
        distance: 30,
        fontSize: 10,
      },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 32,
        fontWeight: 800,
        color: colors.foreground,
        offsetCenter: [0, '30%'],
      },
      title: {
        show: true,
        offsetCenter: [0, '55%'],
        fontSize: 12,
        color: colors.muted,
        fontWeight: 500,
      },
      data: [{ value: val, name: props.label }],
    }],
    graphic: [{
      type: 'text',
      left: 'center',
      bottom: '5%',
      style: {
        text: props.trend === 'up' ? '鈫?涓婂崌' : props.trend === 'down' ? '鈫?涓嬮檷' : '鈫?骞崇ǔ',
        fill: trendColor,
        fontSize: 12,
        fontWeight: 600,
      },
    }],
  }
})
</script>

<template>
  <div class="quality-gauge">
    <VChart
      :option="gaugeOption"
      style="height: 260px; width: 100%;"
      autoresize
    />
  </div>
</template>

<style scoped>
.quality-gauge {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
