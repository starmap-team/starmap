/**
 * 数据流水线监控页 composable
 * 提取自 PipelineMonitor.vue — 管理全部响应式状态与业务逻辑
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePipelineStore } from '@/stores/pipeline'
import type { PipelineStage, PipelineSchedule, DataMilestone, ExtractionComplete } from '@/stores/pipeline'
import type { QualityAlert } from '@/types/quality'
import { STAGE_LABELS, ALL_STAGE_NAMES } from '@/stores/pipeline'
import { useSSE } from '@/composables/useSSE'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'

/** Default auto-refresh interval in seconds */
const DEFAULT_REFRESH_INTERVAL_SEC = 10

export function usePipelineMonitor() {
  const pipeline = usePipelineStore()

  // ── 自动刷新 ──
  const autoRefresh = ref(true)
  const refreshInterval = ref(DEFAULT_REFRESH_INTERVAL_SEC)
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
  // Phase 1 D-09: 多事件类型分发到 pipeline store actions
  const { connected: sseConnected, mode: sseMode, disconnect: sseDisconnect } = useSSE(
    '/api/v1/pipeline/events',
    {
      storeHandlers: {
        pipeline_update: (data) => pipeline.handlePipelineEvent(data as { stage: string; status: string; progress: number; message: string }),
        quality_alert: (data) => pipeline.handleQualityAlert(data as QualityAlert),
        data_milestone: (data) => pipeline.handleMilestone(data as DataMilestone),
        extraction_complete: (data) => pipeline.handleExtractionComplete(data as ExtractionComplete),
      },
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

  // ── Phase 1 CANCEL-03: 取消当前 running run ──
  async function handleCancelRun() {
    const runId = pipeline.pipelineStatus?.current_run?.id
    if (!runId) return
    try {
      await ElMessageBox.confirm(
        '确认取消当前正在运行的流水线？此操作不可撤销。',
        '取消流水线',
        { confirmButtonText: '确认取消', cancelButtonText: '不取消', type: 'warning' }
      )
      const ok = await pipeline.cancelRun(runId)
      if (ok) {
        ElMessage.success('流水线已取消')
      }
    } catch { /* user cancelled or api error */ }
  }

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
      status: 'pending' as const,
      duration_ms: 0,
      records_processed: 0,
      errors: [] as string[],
      errors_count: 0,
      progress: 0,
      retry_count: 0,
      depends_on: [],
      started_at: null,
      completed_at: null,
    }))
  })

  const stageColorMap: Record<string, string> = {
    running: chartColors().info,
    completed: chartColors().success,
    failed: chartColors().danger,
    pending: chartColors().muted,
    skipped: '#d1d5db',
    cancelled: '#f59e0b',
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
  const retryingStages = ref<Set<string>>(new Set())

  async function handleRetryStage(stageName: string) {
    if (!currentRunId.value) return
    retryingStages.value.add(stageName)
    try {
      await pipeline.retryStage(currentRunId.value, stageName)
      ElMessage.success(`阶段 ${STAGE_LABELS[stageName] || stageName} 已重试`)
    } catch {
      ElMessage.error('重试失败')
    } finally {
      retryingStages.value.delete(stageName)
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

  async function handleTriggerSchedule(schedule: PipelineSchedule) {
    try {
      await pipeline.triggerSchedule(schedule.id)
      ElMessage.success(`调度「${schedule.name}」已触发执行`)
    } catch {
      ElMessage.error('触发调度失败')
    }
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
      ElMessage.success('保存成功，下一个 run 生效')
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

  // ── 生命周期 ──
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

  return {
    // Store
    pipeline,
    // 自动刷新
    autoRefresh,
    refreshInterval,
    lastRefresh,
    loadAll,
    toggleAutoRefresh,
    // SSE
    sseConnected,
    sseMode,
    // 取消运行
    handleCancelRun,
    // KPI
    kpiCards,
    // DAG 时间线
    timelineStages,
    stageColorMap,
    isDagBranch,
    isDagMerge,
    // 触发流水线
    selectedStages,
    triggerDialogVisible,
    triggerRunType,
    openTriggerDialog,
    handleTrigger,
    // 重试/断点续跑
    retryingStages,
    handleRetryStage,
    handleResume,
    // 定时调度
    scheduleDialogVisible,
    scheduleForm,
    openScheduleDialog,
    handleCreateSchedule,
    handleDeleteSchedule,
    handleTriggerSchedule,
    handleToggleSchedule,
    // 配置
    configDialogVisible,
    openConfigDialog,
    handleSaveConfig,
    // 数据质量
    qualityTrendOption,
    qualityTrendDir,
  }
}
