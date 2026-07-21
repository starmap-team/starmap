<script setup lang="ts">
/**
 * 数据质量监控面板 (Phase 3.8.4 增强版)
 *
 * 展示综合质量仪表盘、质量趋势折线图、质量维度进度条
 * 每个维度都有清晰的功能说明和颜色阈值
 */
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import { QuestionFilled } from '@element-plus/icons-vue'
import DataQualityGauge from '@/components/DataQualityGauge.vue'
import { chartColors } from '@/utils/chartTheme'
import type { DataQualityMetrics } from '@/stores/pipeline'

use([LineChart, TooltipComponent, GridComponent, MarkLineComponent])

defineProps<{
  dataQuality: DataQualityMetrics | null
  qualityTrendOption: Record<string, unknown>
  qualityTrendDir: 'up' | 'down' | 'stable'
  loading: boolean
}>()

// 维度说明 (Phase 3.8.4: 让用户理解每个指标)
const DIMENSION_HINTS: Record<string, { label: string; hint: string; threshold: number }> = {
  completeness: { label: '完整性', hint: '必填字段是否填写 (职位/公司/薪资/描述)', threshold: 0.8 },
  accuracy: { label: '准确性', hint: '数据是否符合预期格式 (URL/手机号/邮箱)', threshold: 0.8 },
  consistency: { label: '一致性', hint: '跨数据源/跨字段的标准化程度', threshold: 0.8 },
  timeliness: { label: '时效性', hint: '数据新鲜度 (距离最近一次爬取的时间)', threshold: 0.8 },
}
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="quality-panel"
  >
    <template #header>
      <div class="panel-header">
        <span class="panel-title">数据质量监控</span>
        <el-tooltip
          content="综合评估最近一次流水线产出的数据质量。4 个维度按权重 0.25 合成综合分，每个维度 ≥80% 算合格。"
          placement="top"
        >
          <el-icon class="help-icon">
            <QuestionFilled />
          </el-icon>
        </el-tooltip>
      </div>
    </template>
    <DataQualityGauge
      :score="dataQuality?.overall_score ?? 0"
      label="综合质量"
      :trend="qualityTrendDir"
    />
    <div class="quality-trend-section">
      <div class="section-title">
        质量趋势 (最近 14 天)
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
        v-for="key in ['completeness', 'accuracy', 'consistency', 'timeliness']"
        :key="key"
        class="dim-item"
      >
        <div class="dim-label">
          {{ DIMENSION_HINTS[key].label }}
          <el-tooltip
            :content="DIMENSION_HINTS[key].hint"
            placement="top"
          >
            <el-icon class="dim-hint">
              <QuestionFilled />
            </el-icon>
          </el-tooltip>
        </div>
        <el-progress
          :percentage="Math.round((dataQuality[key as keyof DataQualityMetrics] as number || 0) * 100)"
          :stroke-width="8"
          :color="(dataQuality[key as keyof DataQualityMetrics] as number) >= DIMENSION_HINTS[key].threshold ? chartColors().success : chartColors().warning"
        />
      </div>
    </div>
  </el-card>
</template>

<style scoped>
/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.panel-title {
  font-weight: 600;
}
.help-icon {
  color: var(--muted-foreground);
  cursor: help;
  font-size: 14px;
}
.help-icon:hover { color: var(--primary); }

/* 维度 */
.dim-hint {
  color: var(--muted-foreground);
  font-size: 11px;
  margin-left: 2px;
  cursor: help;
}
.dim-hint:hover { color: var(--primary); }

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
  width: 64px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
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
