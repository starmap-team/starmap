<script setup lang="ts">
/**
 * 双层技能雷达图组件 — 岗位要求 vs 我的技能
 * 对应任务文档：匹配诊断第3步
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { chartColors, legendStyle } from '@/utils/chartTheme'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'

// 确保雷达图相关组件已注册（main.ts 已注册，此处为组件独立使用补充）
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent])

export interface RadarItem {
  skill: string
  required: number   // 岗位要求 0-1
  user: number       // 用户掌握 0-1
}

const props = defineProps<{
  data: RadarItem[]
  positionName: string
}>()

const radarOption = computed(() => {
  if (!props.data.length) return {}

  const indicators = props.data.map(d => ({
    name: d.skill,
    max: 1,
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        if (p.seriesName === '岗位要求') {
          return `${p.name}<br/>岗位要求：${(p.value * 100).toFixed(0)}%`
        }
        return `${p.name}<br/>我的掌握：${(p.value * 100).toFixed(0)}%`
      },
    },
    legend: { bottom: 0, textStyle: legendStyle() },
    radar: {
      center: ['50%', '48%'],
      radius: '65%',
      indicator: indicators,
      axisName: {
        color: chartColors().muted,
        fontSize: 12,
      },
    },
    series: [
      {
        type: 'radar',
        name: '岗位要求',
        data: [{
          value: props.data.map(d => d.required),
          name: '岗位要求',
        }],
        lineStyle: { color: chartColors().danger, width: 2 },
        areaStyle: { color: chartColors().danger + '33' },
        itemStyle: { color: chartColors().danger },
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        type: 'radar',
        name: '我的技能',
        data: [{
          value: props.data.map(d => d.user),
          name: '我的技能',
        }],
        lineStyle: { color: chartColors().primary, width: 2 },
        areaStyle: { color: chartColors().primary + '33' },
        itemStyle: { color: chartColors().primary },
        symbol: 'circle',
        symbolSize: 5,
      },
    ],
  }
})
</script>

<template>
  <div class="skill-radar">
    <div class="radar-title">
      {{ positionName }} — 技能雷达对比
    </div>
    <VChart
      v-if="data.length"
      :option="radarOption"
      style="height: 400px"
      autoresize
    />
    <div class="custom-empty">
      <div class="empty-icon-wrapper">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
        ><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
      </div>
      <p class="empty-text">
        雷达图数据不足
      </p>
      <p class="empty-hint-text">
        需要至少 3 项技能才能生成雷达图
      </p>
    </div>
  </div>
</template>

<style scoped>
.skill-radar {
  width: 100%;
}

.radar-title {
  text-align: center;
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
  margin-bottom: var(--space-3);
  letter-spacing: var(--tracking-tight);
}

.custom-empty { display: flex; flex-direction: column; align-items: center; padding: var(--space-8) var(--space-4); text-align: center; }
.empty-icon-wrapper { color: var(--muted-foreground); opacity: 0.4; margin-bottom: var(--space-3); }
.empty-text { font-size: var(--font-size-base); font-weight: 600; color: var(--foreground); margin: 0; }
.empty-hint-text { font-size: var(--font-size-sm); color: var(--muted-foreground); margin: var(--space-1) 0 0; }
</style>