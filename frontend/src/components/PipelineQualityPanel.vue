<script setup lang="ts">
/**
 * 数据质量监控面板
 * 展示综合质量仪表盘、质量趋势折线图、质量维度进度条
 */
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import DataQualityGauge from '@/components/DataQualityGauge.vue'
import { chartColors } from '@/utils/chartTheme'
import type { DataQualityMetrics } from '@/stores/pipeline'

use([LineChart, TooltipComponent, GridComponent, MarkLineComponent])

defineProps<{
  dataQuality: DataQualityMetrics | null
  qualityTrendOption: Record<string, any>
  qualityTrendDir: 'up' | 'down' | 'stable'
  loading: boolean
}>()
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="quality-panel"
  >
    <template #header>
      <span>数据质量监控</span>
    </template>
    <DataQualityGauge
      :score="dataQuality?.overall_score ?? 0"
      label="综合质量"
      :trend="qualityTrendDir"
    />
    <div class="quality-trend-section">
      <div class="section-title">
        质量趋势
      </div>
      <VChart
        v-if="dataQuality?.trend?.length"
        :option="qualityTrendOption"
        style="height: 220px;"
        autoresize
      />
      <div
        v-else
        class="custom-empty"
      >
        <p class="empty-hint-text">
          质量趋势数据将在采集后展示
        </p>
      </div>
    </div>
    <div
      v-if="dataQuality"
      class="quality-dimensions"
    >
      <div
        v-for="dim in [
          { label: '完整性', value: dataQuality.completeness, color: dataQuality.completeness >= 0.8 ? chartColors().success : chartColors().warning },
          { label: '准确性', value: dataQuality.accuracy, color: dataQuality.accuracy >= 0.8 ? chartColors().success : chartColors().warning },
          { label: '一致性', value: dataQuality.consistency, color: dataQuality.consistency >= 0.8 ? chartColors().success : chartColors().warning },
          { label: '时效性', value: dataQuality.timeliness, color: dataQuality.timeliness >= 0.8 ? chartColors().success : chartColors().warning },
        ]"
        :key="dim.label"
        class="dim-item"
      >
        <div class="dim-label">
          {{ dim.label }}
        </div>
        <el-progress
          :percentage="Math.round(dim.value * 100)"
          :stroke-width="8"
          :color="dim.color"
        />
      </div>
    </div>
  </el-card>
</template>

<style scoped>
/* 质量趋势区间 */
.quality-trend-section {
  margin-top: var(--space-4);
}
.section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: var(--space-2);
}

/* 质量子指标 */
.quality-dimensions {
  margin-top: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.dim-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.dim-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  width: 48px;
  flex-shrink: 0;
}
.dim-item :deep(.el-progress) {
  flex: 1;
}

/* 空状态 */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
</style>
