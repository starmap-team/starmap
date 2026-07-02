<script setup lang="ts">
/**
 * 数据源状态卡片
 * 展示数据源名称、权威度仪表盘、状态徽章、采集信息
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { chartColors, tooltipStyle } from '@/utils/chartTheme'

use([GaugeChart, TooltipComponent])

export interface DataSourceInfo {
  name: string
  source_type: 'crawler' | 'api' | 'manual' | 'import'
  authority_score: number
  status: 'active' | 'paused' | 'error'
  last_crawl_at: string
  total_records: number
  valid_records: number
  duplicate_rate: number
  avg_quality_score: number
}

const props = defineProps<{
  source: DataSourceInfo
}>()

const statusBadge = computed(() => {
  switch (props.source.status) {
    case 'active':
      return { type: 'success', label: '运行中' }
    case 'paused':
      return { type: 'warning', label: '已暂停' }
    case 'error':
      return { type: 'danger', label: '异常' }
    default:
      return { type: 'info', label: '未知' }
  }
})

const sourceTypeLabel = computed(() => {
  const map: Record<string, string> = {
    crawler: '爬虫',
    api: 'API',
    manual: '手动',
    import: '导入',
  }
  return map[props.source.source_type] ?? props.source.source_type
})

const formattedLastCrawl = computed(() => {
  if (!props.source.last_crawl_at) return '--'
  const d = new Date(props.source.last_crawl_at)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}小时前`
  const day = Math.floor(hr / 24)
  return `${day}天前`
})

const formattedRecords = computed(() => {
  const n = props.source.total_records
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
})

const gaugeOption = computed(() => {
  const score = Math.round(props.source.authority_score * 100)
  const colors = chartColors()
  let color = colors.danger
  if (score >= 80) color = colors.success
  else if (score >= 60) color = colors.warning

  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      radius: '90%',
      center: ['50%', '55%'],
      min: 0,
      max: 100,
      progress: { show: true, width: 8, roundCap: true, itemStyle: { color } },
      axisLine: { lineStyle: { width: 8, color: [[1, colors.border]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 18,
        fontWeight: 700,
        color: colors.foreground,
        offsetCenter: [0, '10%'],
      },
      title: {
        show: true,
        offsetCenter: [0, '40%'],
        fontSize: 10,
        color: colors.muted,
      },
      data: [{ value: score, name: '权威度' }],
    }],
  }
})
</script>

<template>
  <el-card
    shadow="hover"
    class="source-card"
  >
    <div class="source-header">
      <div class="source-title-group">
        <span class="source-name">{{ source.name }}</span>
        <el-tag
          :type="statusBadge.type as any"
          size="small"
          effect="light"
          round
        >
          {{ statusBadge.label }}
        </el-tag>
      </div>
      <el-tag
        size="small"
        effect="plain"
        round
      >
        {{ sourceTypeLabel }}
      </el-tag>
    </div>

    <div class="source-body">
      <div class="source-gauge">
        <VChart
          :option="gaugeOption"
          style="width: 120px; height: 100px;"
          autoresize
        />
      </div>

      <div class="source-stats">
        <div class="stat-row">
          <span class="stat-label">记录总量</span>
          <span class="stat-value">{{ formattedRecords }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">有效记录</span>
          <span class="stat-value">{{ source.valid_records.toLocaleString() }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">重复率</span>
          <span
            class="stat-value"
            :style="{ color: source.duplicate_rate > 0.2 ? chartColors().danger : chartColors().success }"
          >{{ (source.duplicate_rate * 100).toFixed(1) }}%</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">平均质量</span>
          <span class="stat-value">{{ (source.avg_quality_score * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>

    <div class="source-footer">
      <span class="crawl-time">最后采集：{{ formattedLastCrawl }}</span>
    </div>
  </el-card>
</template>

<style scoped>
.source-card {
  transition: all var(--duration-normal) var(--ease-out);
}
.source-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}
.source-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.source-name {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}
.source-body {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.source-gauge {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.source-stats {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.stat-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}
.source-footer {
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.crawl-time {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
</style>
