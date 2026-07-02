<script setup lang="ts">
/**
 * 数据流水线监控页 — 完整批量爬虫流
 * 展示 ETL DAG：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
 * 支持：阶段选择触发、实时SSE进度、失败重试/断点续跑、定时调度、配置调整
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight, Setting, Timer, VideoPlay } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import MainLayout from '@/layouts/MainLayout.vue'
import { usePipelineStore } from '@/stores/pipeline'
import type { PipelineStage, PipelineSchedule } from '@/stores/pipeline'
import { STAGE_LABELS, ALL_STAGE_NAMES } from '@/stores/pipeline'
import PipelineStageCard from '@/components/PipelineStageCard.vue'
import DataSourceCard from '@/components/DataSourceCard.vue'
import DataQualityGauge from '@/components/DataQualityGauge.vue'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'
import { useSSE } from '@/composables/useSSE'

use([LineChart, TooltipComponent, GridComponent, MarkLineComponent])

const pipeline = usePipelineStore()

// ── 自动刷新 ──
const autoRefresh = ref(true)
const refreshInterval = ref(10) // 10s for real-time feel
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
  pipeline.fetchSchedules()
  pipeline.fetchConfig()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  sseDisconnect()
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

// ── SSE 实时进度 ──
const { connected: sseConnected, mode: sseMode, disconnect: sseDisconnect } = useSSE(
  '/api/v1/pipeline/events',
  {
    onMessage: (event: MessageEvent) => {
      // SSE events from sse_broadcaster come as named events
      // pipeline_update events contain stage progress data
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pipeline_update' && data.data) {
          pipeline.handlePipelineEvent(data.data)
        }
      } catch { /* ignore parse errors */ }
    },
  },
)

// ── KPI 卡片 ──
const kpiCards = computed(() => {
  const s = pipeline.pipelineStatus
  const colors = chartColors()
  return [
    {
      label: '今日采集量',
      value: s && s.last_run ? s.last_run.total_records.toLocaleString() : '--',
      sub: '条记录',
      color: colors.primary,
      icon: 'Download',
    },
    {
      label: '处理成功率',
      value: s && typeof s.success_rate === 'number' ? `${(s.success_rate * 100).toFixed(1)}%` : '--',
      sub: s && s.success_rate && s.success_rate >= 0.95 ? '运行正常' : '需关注',
      color: s && s.success_rate && s.success_rate >= 0.95 ? colors.success : colors.warning,
      icon: 'CircleCheck',
      trend: s && s.success_rate && s.success_rate >= 0.95 ? 'up' : 'down',
    },
    {
      label: '数据质量分',
      value: s && s.last_run && typeof s.last_run.quality_score === 'number' ? (s.last_run.quality_score * 100).toFixed(1) : '--',
      sub: s && s.avg_quality_score && s.avg_quality_score >= 80 ? '质量优秀' : '有提升空间',
      color: s && s.avg_quality_score && s.avg_quality_score >= 80 ? colors.success : colors.warning,
      icon: 'DataLine',
      trend: s && s.avg_quality_score && s.avg_quality_score >= 80 ? 'up' : 'down',
    },
    {
      label: '活跃数据源',
      value: s && typeof s.active_data_sources === 'number' ? String(s.active_data_sources) : '--',
      sub: '个数据源',
      color: colors.info,
      icon: 'Connection',
      trend: 'stable',
    },
  ]
})

// ── 流水线阶段时间线 (DAG) ──
const timelineStages = computed<PipelineStage[]>(() => {
  if (pipeline.stages.length > 0) return pipeline.stages
  return ALL_STAGE_NAMES.map(name => ({
    name,
    status: 'waiting' as const,
    duration_ms: 0,
    records_processed: 0,
    errors: 0,
    progress: 0,
    retry_count: 0,
    depends_on: [],
  }))
})

const stageColorMap: Record<string, string> = {
  running: chartColors().info,
  completed: chartColors().success,
  failed: chartColors().danger,
  waiting: chartColors().muted,
  pending: chartColors().muted,
  skipped: '#d1d5db',
}

// DAG 分支指示：去重和清洗并行
const isDagBranch = (idx: number) => idx === 1 || idx === 2 // dedup, clean
const isDagMerge = (idx: number) => idx === 3 // import

// ── 阶段选择触发 ──
const selectedStages = ref<string[]>(ALL_STAGE_NAMES)
const triggerDialogVisible = ref(false)
const triggerRunType = ref<'full' | 'incremental'>('full')

function openTriggerDialog() {
  selectedStages.value = ALL_STAGE_NAMES
  triggerRunType.value = 'full'
  triggerDialogVisible.value = true
}

async function handleTrigger() {
  try {
    await pipeline.triggerPipeline(triggerRunType.value, selectedStages.value)
    triggerDialogVisible.value = false
    ElMessage.success('流水线已触发')
    // Switch to faster refresh during execution
    refreshInterval.value = 5
    startAutoRefresh()
  } catch {
    ElMessage.error('触发失败，请稍后重试')
  }
}

// ── 失败重试/断点续跑 ──
const currentRunId = computed(() => pipeline.pipelineStatus?.current_run?.id)

async function handleRetryStage(stageName: string) {
  if (!currentRunId.value) return
  try {
    await pipeline.retryStage(currentRunId.value, stageName)
    ElMessage.success(`阶段 ${STAGE_LABELS[stageName] || stageName} 已重试`)
  } catch {
    ElMessage.error('重试失败')
  }
}

async function handleResume() {
  if (!currentRunId.value) return
  try {
    await pipeline.resumeRun(currentRunId.value)
    ElMessage.success('断点续跑已启动')
  } catch {
    ElMessage.error('断点续跑失败')
  }
}

// ── 定时调度 ──
const scheduleDialogVisible = ref(false)
const scheduleForm = ref({
  name: '',
  cron_expression: '0 2 * * *',
  run_type: 'incremental' as 'full' | 'incremental',
  selected_stages: null as string[] | null,
  enabled: true,
})

function openScheduleDialog() {
  scheduleForm.value = { name: '', cron_expression: '0 2 * * *', run_type: 'incremental', selected_stages: null, enabled: true }
  scheduleDialogVisible.value = true
}

async function handleCreateSchedule() {
  try {
    await pipeline.createSchedule(scheduleForm.value)
    scheduleDialogVisible.value = false
    ElMessage.success('定时调度已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleDeleteSchedule(id: string) {
  try {
    await ElMessageBox.confirm('确定删除此定时调度？', '确认')
    await pipeline.deleteSchedule(id)
    ElMessage.success('已删除')
  } catch { /* cancelled */ }
}

async function handleToggleSchedule(schedule: PipelineSchedule) {
  await pipeline.updateSchedule(schedule.id, { ...schedule, enabled: !schedule.enabled })
}

// ── 配置弹窗 ──
const configDialogVisible = ref(false)

function openConfigDialog() {
  pipeline.fetchConfig()
  configDialogVisible.value = true
}

async function handleSaveConfig() {
  if (!pipeline.config) return
  try {
    await pipeline.updateConfig(pipeline.config)
    configDialogVisible.value = false
    ElMessage.success('配置已更新')
  } catch {
    ElMessage.error('更新配置失败')
  }
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
      areaStyle: { opacity: 0.15, color: colors.primary },
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

const qualityTrendDir = computed<'up' | 'down' | 'stable'>(() => {
  const trend = pipeline.dataQuality?.trend
  if (!trend || trend.length < 2) return 'stable'
  const last = trend[trend.length - 1].score
  const prev = trend[trend.length - 2].score
  if (last > prev + 1) return 'up'
  if (last < prev - 1) return 'down'
  return 'stable'
})
</script>

<template>
  <MainLayout>
    <div class="pipeline-page animate-fade-in">
      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据流水线监控</h2>
          <p class="page-desc">
            ETL DAG 全链路：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
            <el-tag
              v-if="sseConnected"
              size="small"
              type="success"
              effect="plain"
              class="ml-2"
            >
              SSE 实时
            </el-tag>
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
            :icon="VideoPlay"
            :loading="pipeline.loading"
            @click="openTriggerDialog"
          >
            触发流水线
          </el-button>
          <el-button
            v-if="pipeline.pipelineStatus?.current_run?.status === 'failed'"
            size="small"
            type="warning"
            @click="handleResume"
          >
            断点续跑
          </el-button>
          <el-button
            size="small"
            :icon="Timer"
            @click="openScheduleDialog"
          >
            定时调度
          </el-button>
          <el-button
            size="small"
            :icon="Setting"
            @click="openConfigDialog"
          >
            配置
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

      <!-- 流水线 DAG 时间线视图 -->
      <el-card
        v-loading="pipeline.loading"
        shadow="never"
        class="mb-4 timeline-card"
      >
        <template #header>
          <div class="panel-header">
            <span>流水线时间线 (DAG)</span>
            <el-tag
              v-if="pipeline.pipelineStatus?.is_running"
              size="small"
              type="warning"
              effect="plain"
            >
              执行中
            </el-tag>
          </div>
        </template>
        <div class="pipeline-dag">
          <!-- Row 1: crawl -->
          <div class="dag-row dag-row-center">
            <div class="timeline-node">
              <PipelineStageCard
                :stage="timelineStages[0]"
                @retry="handleRetryStage(timelineStages[0].name)"
              />
            </div>
          </div>
          <!-- Arrow: crawl → (dedup + clean) -->
          <div class="dag-row dag-row-center">
            <div class="dag-fork">
              <div class="fork-line fork-left" />
              <div class="fork-line fork-right" />
            </div>
          </div>
          <!-- Row 2: dedup ∥ clean (parallel) -->
          <div class="dag-row dag-row-parallel">
            <div class="timeline-node">
              <PipelineStageCard
                :stage="timelineStages[1]"
                @retry="handleRetryStage(timelineStages[1].name)"
              />
            </div>
            <div class="parallel-label">并行</div>
            <div class="timeline-node">
              <PipelineStageCard
                :stage="timelineStages[2]"
                @retry="handleRetryStage(timelineStages[2].name)"
              />
            </div>
          </div>
          <!-- Arrow: (dedup + clean) → import -->
          <div class="dag-row dag-row-center">
            <div class="dag-merge">
              <div class="merge-line merge-left" />
              <div class="merge-line merge-right" />
            </div>
          </div>
          <!-- Row 3: import -->
          <div class="dag-row dag-row-center">
            <div class="timeline-node">
              <PipelineStageCard
                :stage="timelineStages[3]"
                @retry="handleRetryStage(timelineStages[3].name)"
              />
            </div>
          </div>
          <!-- Arrow: import → graph_sync -->
          <div class="dag-row dag-row-center">
            <div class="dag-arrow-down">
              <span class="arrow-line" />
              <span class="arrow-head">›</span>
            </div>
          </div>
          <!-- Row 4: graph_sync -->
          <div class="dag-row dag-row-center">
            <div class="timeline-node">
              <PipelineStageCard
                :stage="timelineStages[4]"
                @retry="handleRetryStage(timelineStages[4].name)"
              />
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
            <DataQualityGauge
              :score="pipeline.dataQuality?.overall_score ?? 0"
              label="综合质量"
              :trend="qualityTrendDir"
            />
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

      <!-- 定时调度列表 -->
      <el-card
        v-if="pipeline.schedules.length"
        shadow="never"
        class="mb-4"
      >
        <template #header>
          <div class="panel-header">
            <span>定时调度</span>
            <el-button
              size="small"
              :icon="Timer"
              @click="openScheduleDialog"
            >
              新增
            </el-button>
          </div>
        </template>
        <el-table
          :data="pipeline.schedules"
          size="small"
          stripe
        >
          <el-table-column
            prop="name"
            label="名称"
            width="140"
          />
          <el-table-column
            prop="cron_expression"
            label="Cron 表达式"
            width="140"
          />
          <el-table-column
            prop="run_type"
            label="类型"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.run_type === 'full' ? '' : 'info'"
                size="small"
              >
                {{ row.run_type === 'full' ? '全量' : '增量' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="启用"
            width="80"
          >
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                size="small"
                @change="handleToggleSchedule(row)"
              />
            </template>
          </el-table-column>
          <el-table-column
            label="上次运行"
            width="160"
          >
            <template #default="{ row }">
              {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '--' }}
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="80"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                type="danger"
                link
                @click="handleDeleteSchedule(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- ── 触发流水线弹窗 ── -->
      <el-dialog
        v-model="triggerDialogVisible"
        title="触发流水线"
        width="480px"
      >
        <el-form label-width="80px">
          <el-form-item label="运行类型">
            <el-radio-group v-model="triggerRunType">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="执行阶段">
            <el-checkbox-group v-model="selectedStages">
              <el-checkbox
                v-for="name in ALL_STAGE_NAMES"
                :key="name"
                :value="name"
              >
                {{ STAGE_LABELS[name] || name }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="triggerDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :disabled="selectedStages.length === 0"
            @click="handleTrigger"
          >
            启动
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 定时调度弹窗 ── -->
      <el-dialog
        v-model="scheduleDialogVisible"
        title="创建定时调度"
        width="480px"
      >
        <el-form
          :model="scheduleForm"
          label-width="100px"
        >
          <el-form-item label="名称">
            <el-input
              v-model="scheduleForm.name"
              placeholder="如：每日增量爬取"
            />
          </el-form-item>
          <el-form-item label="Cron 表达式">
            <el-input
              v-model="scheduleForm.cron_expression"
              placeholder="0 2 * * * (每天凌晨2点)"
            />
          </el-form-item>
          <el-form-item label="运行类型">
            <el-radio-group v-model="scheduleForm.run_type">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="scheduleForm.enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scheduleDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="handleCreateSchedule"
          >
            创建
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 配置弹窗 ── -->
      <el-dialog
        v-model="configDialogVisible"
        title="流水线配置"
        width="480px"
      >
        <el-form
          v-if="pipeline.config"
          label-width="120px"
        >
          <el-form-item label="阶段超时(秒)">
            <el-input-number
              v-model="pipeline.config.stage_timeout"
              :min="60"
              :max="7200"
              :step="60"
            />
          </el-form-item>
          <el-form-item label="Worker并发数">
            <el-input-number
              v-model="pipeline.config.worker_concurrency"
              :min="1"
              :max="16"
            />
          </el-form-item>
          <el-form-item label="爬取并发数">
            <el-input-number
              v-model="pipeline.config.crawl_concurrency"
              :min="1"
              :max="20"
            />
          </el-form-item>
          <el-form-item label="最大重试次数">
            <el-input-number
              v-model="pipeline.config.retry_max"
              :min="0"
              :max="10"
            />
          </el-form-item>
          <el-form-item label="重试间隔(秒)">
            <el-input-number
              v-model="pipeline.config.retry_backoff"
              :min="5"
              :max="300"
              :step="5"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="configDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="handleSaveConfig"
          >
            保存
          </el-button>
        </template>
      </el-dialog>
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
  display: flex;
  align-items: center;
  gap: 4px;
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

/* DAG 时间线 */
.timeline-card :deep(.el-card__header) {
  font-weight: 600;
}
.pipeline-dag {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  padding: var(--space-4) 0;
}
.dag-row {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.dag-row-center {
  justify-content: center;
}
.dag-row-parallel {
  justify-content: center;
  gap: var(--space-8);
}
.timeline-node :deep(.stage-card) {
  min-width: 180px;
  max-width: 200px;
}
.parallel-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-weight: 600;
  align-self: center;
}

/* DAG fork/merge arrows */
.dag-fork,
.dag-merge {
  display: flex;
  justify-content: center;
  width: 400px;
  height: 24px;
  position: relative;
}
.fork-line,
.merge-line {
  width: 2px;
  height: 24px;
  background: var(--muted-foreground);
  opacity: 0.4;
  position: absolute;
}
.fork-line.fork-left,
.merge-line.merge-left {
  left: 30%;
  transform: rotate(15deg);
}
.fork-line.fork-right,
.merge-line.merge-right {
  right: 30%;
  transform: rotate(-15deg);
}
.merge-line.merge-left {
  transform: rotate(-15deg);
}
.merge-line.merge-right {
  transform: rotate(15deg);
}
.dag-arrow-down {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.dag-arrow-down .arrow-line {
  display: block;
  width: 2px;
  height: 16px;
  background: var(--muted-foreground);
  opacity: 0.4;
}
.dag-arrow-down .arrow-head {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted-foreground);
  opacity: 0.4;
  transform: rotate(90deg);
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
.ml-2 { margin-left: var(--space-2); }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
  .dag-row-parallel { flex-direction: column; gap: var(--space-2); }
  .parallel-label { display: none; }
  .dag-fork, .dag-merge { display: none; }
  .timeline-node :deep(.stage-card) { min-width: 100%; max-width: 100%; }
}
</style>
