<script setup lang="ts">
/**
 * 数据流水线监控页 — Sprint 1.1
 * 展示 ETL 全链路：爬虫采集 → SimHash去重 → 清洗标准化 → 入库 → 图谱构建
 * 顶部 KPI + 中部时间线 + 左下数据源 + 右下质量监控
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import MainLayout from '@/layouts/MainLayout.vue'
import { usePipelineStore } from '@/stores/pipeline'
import type { PipelineStage } from '@/stores/pipeline'
import PipelineStageCard from '@/components/PipelineStageCard.vue'
import DataSourceCard from '@/components/DataSourceCard.vue'
import DataQualityGauge from '@/components/DataQualityGauge.vue'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'

use([LineChart, TooltipComponent, GridComponent, MarkLineComponent])

const pipeline = usePipelineStore()

// ── 自动刷新 ──
const autoRefresh = ref(true)
const refreshInterval = ref(30)
let timer: ReturnType<typeof setInterval> | null = null
const lastRefresh = ref('')

async function loadAll() {
  await Promise.all([
    pipeline.fetchStatus(),
    pipeline.fetchStages(),
    pipeline.fetchDataQuality(),
    pipeline.fetchDataSources(),
  ])
  lastRefresh.value = new Date().toLocaleTimeString()
}

function startAutoRefresh() {
  if (timer) clearInterval(timer)
  if (autoRefresh.value) {
    timer = setInterval(loadAll, refreshInterval.value * 1000)
  }
}

onMounted(() => {
  loadAll()
  startAutoRefresh()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function toggleAutoRefresh(val: boolean) {
  autoRefresh.value = val
  if (val) {
    startAutoRefresh()
    ElMessage.success(`已开启自动刷新（每${refreshInterval.value}秒）`)
  } else {
    if (timer) clearInterval(timer)
    ElMessage.info('已关闭自动刷新')
  }
}

// ── KPI 卡片 ──
const kpiCards = computed(() => {
  const s = pipeline.pipelineStatus
  const colors = chartColors()
  return [
    {
      label: '今日采集量',
      value: s && typeof s.today_crawl_volume === 'number' ? s.today_crawl_volume.toLocaleString() : '--',
      sub: '条记录',
      color: colors.primary,
      icon: 'Download',
    },
    {
      label: '处理成功率',
      value: s ? `${(s.success_rate * 100).toFixed(1)}%` : '--',
      sub: s && s.success_rate >= 0.95 ? '运行正常' : '需关注',
      color: s && s.success_rate >= 0.95 ? colors.success : colors.warning,
      icon: 'CircleCheck',
      trend: s && s.success_rate >= 0.95 ? 'up' : 'down',
    },
    {
      label: '数据质量分',
      value: s ? s.avg_quality_score.toFixed(1) : '--',
      sub: s && s.avg_quality_score >= 80 ? '质量优秀' : '有提升空间',
      color: s && s.avg_quality_score >= 80 ? colors.success : colors.warning,
      icon: 'DataLine',
      trend: s && s.avg_quality_score >= 80 ? 'up' : 'down',
    },
    {
      label: '活跃数据源',
      value: s ? String(s.active_sources) : '--',
      sub: '个数据源',
      color: colors.info,
      icon: 'Connection',
      trend: 'stable',
    },
  ]
})

// ── 流水线阶段时间线 ──
const timelineStages = computed<PipelineStage[]>(() => {
  if (pipeline.stages.length > 0) return pipeline.stages
  // 默认5阶段骨架（无数据时展示）
  return [
    { name: '爬虫采集', status: 'waiting', duration_ms: 0, records_processed: 0, errors: 0, progress: 0 },
    { name: 'SimHash去重', status: 'waiting', duration_ms: 0, records_processed: 0, errors: 0, progress: 0 },
    { name: '清洗标准化', status: 'waiting', duration_ms: 0, records_processed: 0, errors: 0, progress: 0 },
    { name: '数据入库', status: 'waiting', duration_ms: 0, records_processed: 0, errors: 0, progress: 0 },
    { name: '图谱构建', status: 'waiting', duration_ms: 0, records_processed: 0, errors: 0, progress: 0 },
  ]
})

const stageColorMap: Record<string, string> = {
  running: chartColors().info,
  completed: chartColors().success,
  failed: chartColors().danger,
  waiting: chartColors().muted,
}

// ── 数据质量趋势折线图 ──
const qualityTrendOption = computed(() => {
  const trend = pipeline.dataQuality?.trend
  if (!trend?.length) return {}
  const colors = chartColors()
  return {
    tooltip: { ...tooltipStyle(), trigger: 'axis' },
    grid: { top: 16, bottom: 32, left: 48, right: 16 },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.date),
      axisLabel: { ...axisLabelStyle(), rotate: 30 },
    },
    yAxis: {
      type: 'value',
      name: '质量分',
      min: 50,
      max: 100,
      splitLine: splitLineStyle(),
      axisLabel: axisLabelStyle(),
    },
    series: [{
      type: 'line',
      data: trend.map(t => t.score),
      smooth: true,
      areaStyle: {
        opacity: 0.15,
        color: colors.primary,
      },
      lineStyle: { color: colors.primary, width: 2.5 },
      itemStyle: { color: colors.primary },
      symbolSize: 6,
      markLine: {
        silent: true,
        symbol: 'none',
        data: [{
          yAxis: 80,
          label: { formatter: '优秀线 80', fontSize: 10 },
          lineStyle: { color: colors.success, type: 'dashed', width: 1.5 },
        }, {
          yAxis: 60,
          label: { formatter: '警戒线 60', fontSize: 10 },
          lineStyle: { color: colors.danger, type: 'dashed', width: 1.5 },
        }],
      },
    }],
  }
})

// ── 趋势方向 ──
const qualityTrendDir = computed<'up' | 'down' | 'stable'>(() => {
  const trend = pipeline.dataQuality?.trend
  if (!trend || trend.length < 2) return 'stable'
  const last = trend[trend.length - 1].score
  const prev = trend[trend.length - 2].score
  if (last > prev + 1) return 'up'
  if (last < prev - 1) return 'down'
  return 'stable'
})

// ── 触发流水线 ──
async function handleTrigger() {
  try {
    await pipeline.triggerPipeline()
    ElMessage.success('流水线已触发')
  } catch {
    ElMessage.error('触发失败，请稍后重试')
  }
}
</script>

<template>
  <MainLayout>
    <div class="pipeline-page animate-fade-in">
      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据流水线监控</h2>
          <p class="page-desc">
            实时监控 ETL 全链路：爬虫采集 → 去重 → 清洗 → 入库 → 图谱构建
          </p>
        </div>
        <div class="header-actions">
          <span
            v-if="lastRefresh"
            class="last-refresh"
          >最近刷新：{{ lastRefresh }}</span>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            size="small"
            @change="toggleAutoRefresh"
          />
          <el-button
            size="small"
            type="primary"
            :loading="pipeline.loading"
            @click="handleTrigger"
          >
            触发流水线
          </el-button>
          <el-button
            size="small"
            :icon="RefreshRight"
            @click="loadAll"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 4 个 KPI 卡片 -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          v-for="card in kpiCards"
          :key="card.label"
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: card.color + '18', color: card.color }"
              >
                <el-icon size="22">
                  <component :is="card.icon" />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  {{ card.label }}
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: card.color }"
                >
                  {{ card.value }}
                </div>
                <div class="kpi-sub">
                  <span v-if="card.trend === 'up'" class="trend-up">▲</span>
                  <span v-else-if="card.trend === 'down'" class="trend-down">▼</span>
                  {{ card.sub }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 流水线时间线视图 -->
      <el-card
        v-loading="pipeline.loading"
        shadow="never"
        class="mb-4 timeline-card"
        header="流水线时间线"
      >
        <div class="pipeline-timeline">
          <div
            v-for="(stage, idx) in timelineStages"
            :key="stage.name"
            class="timeline-node"
          >
            <PipelineStageCard :stage="stage" />
            <div
              v-if="idx < timelineStages.length - 1"
              class="timeline-arrow"
              :style="{ color: stageColorMap[stage.status] || chartColors().muted }"
            >
              <span class="arrow-line" />
              <span class="arrow-head">›</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 底部：数据源面板 + 数据质量监控 -->
      <el-row :gutter="16">
        <!-- 左：数据源管理面板 -->
        <el-col
          :lg="14"
          :md="24"
          class="mb-4"
        >
          <el-card
            v-loading="pipeline.loading"
            shadow="never"
            class="sources-panel"
          >
            <template #header>
              <div class="panel-header">
                <span>数据源管理</span>
                <el-tag
                  size="small"
                  effect="plain"
                  round
                >
                  {{ pipeline.dataSources.length }} 个数据源
                </el-tag>
              </div>
            </template>
            <el-row
              v-if="pipeline.dataSources.length"
              :gutter="12"
            >
              <el-col
                v-for="source in pipeline.dataSources"
                :key="source.id"
                :xl="12"
                :lg="12"
                :md="12"
                :sm="24"
                class="mb-4"
              >
                <DataSourceCard :source="source" />
              </el-col>
            </el-row>
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
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
                  <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
                </svg>
              </div>
              <p class="empty-text">数据源待加载</p>
              <p class="empty-hint-text">数据源信息将在首次同步后展示</p>
            </div>
          </el-card>
        </el-col>

        <!-- 右：数据质量实时监控 -->
        <el-col
          :lg="10"
          :md="24"
          class="mb-4"
        >
          <el-card
            v-loading="pipeline.loading"
            shadow="never"
            class="quality-panel"
          >
            <template #header>
              <span>数据质量监控</span>
            </template>
            <!-- 仪表盘 -->
            <DataQualityGauge
              :score="pipeline.dataQuality?.overall_score ?? 0"
              label="综合质量"
              :trend="qualityTrendDir"
            />
            <!-- 趋势折线图 -->
            <div class="quality-trend-section">
              <div class="section-title">
                质量趋势
              </div>
              <VChart
                v-if="pipeline.dataQuality?.trend?.length"
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
            <!-- 质量子指标 -->
            <div
              v-if="pipeline.dataQuality"
              class="quality-dimensions"
            >
              <div
                v-for="dim in [
                  { label: '完整性', value: pipeline.dataQuality.completeness, color: pipeline.dataQuality.completeness >= 0.8 ? chartColors().success : chartColors().warning },
                  { label: '准确性', value: pipeline.dataQuality.accuracy, color: pipeline.dataQuality.accuracy >= 0.8 ? chartColors().success : chartColors().warning },
                  { label: '一致性', value: pipeline.dataQuality.consistency, color: pipeline.dataQuality.consistency >= 0.8 ? chartColors().success : chartColors().warning },
                  { label: '时效性', value: pipeline.dataQuality.timeliness, color: pipeline.dataQuality.timeliness >= 0.8 ? chartColors().success : chartColors().warning },
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
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.pipeline-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0 0 var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.last-refresh {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

/* KPI 卡片 */
.kpi-card {
  cursor: default;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  position: relative;
  z-index: 1;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kpi-body {
  flex: 1;
  min-width: 0;
}
.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-sub {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}
.trend-down {
  color: var(--destructive);
  font-weight: 600;
}

/* 流水线时间线 */
.timeline-card :deep(.el-card__header) {
  font-weight: 600;
}
.pipeline-timeline {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding: var(--space-2) 0;
}
.timeline-node {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.timeline-node :deep(.stage-card) {
  min-width: 180px;
  max-width: 200px;
}
.timeline-arrow {
  display: flex;
  align-items: center;
  padding: 0 var(--space-1);
  flex-shrink: 0;
}
.arrow-line {
  display: block;
  width: 24px;
  height: 2px;
  background: currentColor;
  opacity: 0.5;
}
.arrow-head {
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  opacity: 0.5;
}

/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

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

.mb-4 { margin-bottom: var(--space-4); }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
  .pipeline-timeline { flex-wrap: wrap; gap: var(--space-2); }
  .timeline-arrow { display: none; }
  .timeline-node :deep(.stage-card) { min-width: 100%; max-width: 100%; }
}
</style>
