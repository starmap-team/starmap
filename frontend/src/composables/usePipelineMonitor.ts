/**
 * 数据流水线监控页 composable
 * 提取自 PipelineMonitor.vue — 管理全部响应式状态与业务逻辑
 * Phase 3.8.8: added STAGE_DEPS + blockedStages for correct retry UX
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'

// Phase 3.8.8: 内联 deps (Ponytail — no extra module)
// ponytail: timeseries stage was removed from the active pipeline; the _DEPS entry
// is a vestige. The DAG has 5 stages (crawl, dedup, clean, import, graph_sync).
const _DEPS: Record<string, string[]> = {
  crawl: [],
  dedup: ['crawl'],
  // Phase 3 Plan 02 Task 2: clean 依赖 dedup (串行), not just crawl
  clean: ['dedup'],
  import: ['clean'],
  graph_sync: ['import'],
}
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
// Phase 3.6 FIX: 直接导入真实 stores，绕开 barrel re-export 包装导致的
// ref-as-value bug (usePipelineStore 返回普通对象，pipelineStatus 是 ref，
// 但 kpiCards 等 computed 在 JS 上下文不会自动 unwrap，导致 s.today_crawl_volume = undefined)
import { usePipelineRunStore } from '@/stores/pipelineRun'
import { usePipelineConfigStore } from '@/stores/pipelineConfig'
import { useUserStore } from '@/stores/user'
import type { PipelineStage, DataMilestone, ExtractionComplete } from '@/stores/pipelineRun'
import type { PipelineSchedule } from '@/stores/pipelineConfig'
import type { QualityAlert } from '@/types/quality'
import { STAGE_LABELS, ALL_STAGE_NAMES } from '@/stores/pipelineConfig'
import { useSSE } from '@/composables/useSSE'
import { API_BASE } from '@/config/apiBase'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'

/** Default auto-refresh interval in seconds */
const DEFAULT_REFRESH_INTERVAL_SEC = 10

export function usePipelineMonitor() {
  // Phase 3.6 FIX: 直接使用真实 stores，pipelineStatus 等字段直接是响应式 ref
  const runStore = usePipelineRunStore()
  const configStore = usePipelineConfigStore()
  // pipeline 兼容对象（用于模板中的 pipeline.xxx 访问）
  const pipeline = {
    get pipelineStatus() { return runStore.pipelineStatus },
    get is_running() { return runStore.pipelineStatus?.is_running ?? false },
    get current_run() { return runStore.pipelineStatus?.current_run ?? null },
    get today_crawl_volume() { return runStore.pipelineStatus?.today_crawl_volume },
    get success_rate() { return runStore.pipelineStatus?.success_rate },
    get avg_quality_score() { return runStore.pipelineStatus?.avg_quality_score },
    get active_data_sources() { return runStore.pipelineStatus?.active_data_sources },
    get run_counts() { return runStore.pipelineStatus?.run_counts ?? {} },
    get loading() { return runStore.loading || configStore.configLoading },
    get error() { return runStore.error || configStore.error },
    get stages() { return runStore.stages },
    get dataQuality() { return runStore.dataQuality },
    get dataSources() { return runStore.dataSources },
    get schedules() { return configStore.schedules },
    get config() { return configStore.config },
    liveEvents: runStore.liveEvents,
    qualityAlerts: runStore.qualityAlerts,
    milestones: runStore.milestones,
    recentExtractions: runStore.recentExtractions,
    fetchStatus: runStore.fetchStatus,
    fetchRuns: runStore.fetchRuns,
    fetchRunDetail: runStore.fetchRunDetail,
    fetchStages: runStore.fetchStages,
    fetchDataQuality: runStore.fetchDataQuality,
    fetchDataSources: runStore.fetchDataSources,
    fetchSchedules: configStore.fetchSchedules,
    fetchConfig: configStore.fetchConfig,
    triggerPipeline: runStore.triggerPipeline,
    cancelRun: runStore.cancelRun,
    forceAdvance: runStore.forceAdvance,
    forceReset: runStore.forceReset,
    retryStage: runStore.retryStage,
    resumeRun: runStore.resumeRun,
    createSchedule: configStore.createSchedule,
    deleteSchedule: configStore.deleteSchedule,
    updateSchedule: configStore.updateSchedule,
    triggerSchedule: configStore.triggerSchedule,
    updateConfig: configStore.updateConfig,
    handlePipelineEvent: runStore.handlePipelineEvent,
    handleQualityAlert: runStore.handleQualityAlert,
    handleMilestone: runStore.handleMilestone,
    handleExtractionComplete: runStore.handleExtractionComplete,
    // Phase 3.7: 实时活动
    liveActivity: runStore.liveActivity,
    activityHistory: runStore.activityHistory,
    resetLiveActivity: runStore.resetLiveActivity,
  }
  const userStore = useUserStore()

  // ── 独立操作加载状态（避免所有按钮共用一个 loading） ──
  const actionLoading = ref(false)        // 触发/取消/续跑等操作
  const scheduleLoading = ref(false)      // 调度操作
  const configSaving = ref(false)         // 配置保存

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
      // fix: 加载历史运行记录，否则刷新后 runs 列表为空
      pipeline.fetchRuns(),
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
  // SSE-05: Use API_BASE from apiBase.ts SSoT
  const sseBase = API_BASE
  const { connected: sseConnected, mode: sseMode, disconnect: sseDisconnect } = useSSE(
    `${sseBase}/pipeline/events`,
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
    if (!runId) {
      ElMessage.warning('没有正在运行的流水线')
      return
    }
    try {
      await ElMessageBox.confirm(
        '确认取消当前正在运行的流水线？此操作不可撤销。',
        '取消流水线',
        { confirmButtonText: '确认取消', cancelButtonText: '不取消', type: 'warning' }
      )
      actionLoading.value = true
      const ok = await pipeline.cancelRun(runId)
      if (ok) {
        // 立即刷新全页面：KPI/DAG/质量面板都需要反映取消状态
        await loadAll()
        ElMessage.success('流水线已取消，所有运行中阶段已停止')
      } else {
        ElMessage.error('取消失败，请查看控制台错误信息')
      }
    } catch {
      /* user cancelled or api error; loadAll to sync state in case of partial success */
      await loadAll().catch(() => {})
    } finally {
      actionLoading.value = false
    }
  }

  // ── 阶段进度摘要 (Phase 3.8.2: 解决"17% 看不出含义"问题) ──
  // Phase 16 Issue J: 区分 crawlRecords(输入) / importRecords(入库) 避免 sum 重复计数误导
  // Phase 16 残留闭环: 仅统计 ALL_STAGE_NAMES 中的核心阶段, 排除已移除的 timeseries
  const stageSummary = computed(() => {
    const coreNames = new Set(ALL_STAGE_NAMES)
    const stages = pipeline.stages.filter(s => coreNames.has(s.name))
    const total = stages.length || ALL_STAGE_NAMES.length
    let completed = 0
    let running = 0
    let failed = 0
    let cancelled = 0
    let skipped = 0
    let totalRecords = 0
    let totalDuration = 0
    let crawlRecords = 0
    let importRecords = 0
    for (const s of stages) {
      const rp = s.records_processed || 0
      totalRecords += rp
      totalDuration += s.duration_ms || 0
      // 按阶段名识别输入/输出口径
      if (s.name === 'crawl' || s.name.startsWith('crawl')) crawlRecords = Math.max(crawlRecords, rp)
      if (s.name === 'import' || s.name.startsWith('import')) importRecords = Math.max(importRecords, rp)
      switch (s.status) {
        case 'completed': completed++; break
        case 'running': running++; break
        case 'failed': failed++; break
        case 'cancelled': cancelled++; break
        case 'skipped': skipped++; break
      }
    }
    const processed = completed + running + failed + cancelled
    const remaining = total - processed - skipped
    return {
      total,
      completed,
      running,
      failed,
      cancelled,
      skipped,
      remaining: Math.max(0, remaining),
      processed,
      totalRecords,
      crawlRecords,
      importRecords,
      totalDurationMs: totalDuration,
      overallPercent: total > 0 ? Math.round((completed / total) * 100) : 0,
      progressMessage: `${completed}已完成 / ${total}总阶段, 采集${crawlRecords.toLocaleString()}条/入库${importRecords.toLocaleString()}条, 累计 ${(totalDuration / 1000).toFixed(0)}s`,
    }
  })

  // ── Phase 3.8.5: 卡死检测 (is_running=true 但唯一 running 阶段无进展) ──
  const isStuck = computed(() => {
    const ps = runStore.pipelineStatus
    if (!ps?.is_running) return false
    const activeStages = (ps.current_run?.stages || []).filter((s: { status: string }) => s.status !== 'skipped')
    if (!activeStages.length) return false
    // Phase 7: also stuck when ALL non-skipped stages are terminal (completed/failed) but run still 'running'
    // (orchestrator forgot to mark run complete)
    const TERMINAL = new Set(['completed', 'failed'])
    if (activeStages.every((s: { status: string }) => TERMINAL.has(s.status))) {
      return true
    }
    // 卡死的核心条件: 有 running 阶段但该阶段已运行 > 10 分钟且无任何 records
    // 或者: 没有任何 pending/正在运行 的进展, 唯一 running 已卡住
    const runningStages = activeStages.filter((s: { status: string }) => s.status === 'running')
    if (runningStages.length === 0) {
      // 没有 running 但有 pending — 真的卡死
      return activeStages.some((s: { status: string }) => s.status === 'pending')
    }
    // 有 running stage: 检查是否已运行太久且无 records
    for (const rs of runningStages) {
      const dur = (rs.duration_ms || 0)
      const records = rs.records_processed || 0
      // 阶段已跑 > 5 分钟但 0 条记录 → 卡死
      if (dur > 5 * 60 * 1000 && records === 0) {
        return true
      }
      // 阶段已跑 > 30 分钟即使有少量记录也算卡死
      if (dur > 30 * 60 * 1000) {
        return true
      }
    }
    return false
  })

  const stuckReason = computed(() => {
    if (!isStuck.value) return ''
    const ps = runStore.pipelineStatus
    if (!ps) return ''
    const runningStages = (ps.current_run?.stages || []).filter((s: { status: string }) => s.status === 'running')
    if (runningStages.length === 0) {
      return 'run 处于 running 状态但所有阶段都是 pending (Celery advance_pipeline 未派发任务)'
    }
    for (const rs of runningStages) {
      if ((rs.duration_ms || 0) > 30 * 60 * 1000) {
        return `${rs.name} 阶段已运行 > 30 分钟, 可能永久卡死`
      }
      if ((rs.duration_ms || 0) > 5 * 60 * 1000 && (rs.records_processed || 0) === 0) {
        return `${rs.name} 阶段已运行 ${Math.round((rs.duration_ms || 0) / 60000)} 分钟但 0 条记录, 可能卡死 (反爬/选择器失效/无 spider)`
      }
    }
    return '检测到卡死状态'
  })

  // ── KPI 卡片 ──
  const kpiCards = computed(() => {
    const s = pipeline.pipelineStatus
    const colors = chartColors()
    const today = s && typeof s.today_crawl_volume === 'number' ? s.today_crawl_volume : null
    const lastTotal = s?.last_run?.total_records ?? 0
    // Phase 4 P3: 显示最近采集时间，让用户知道数据是否陈旧
    const lastCrawlAt = (s as any)?.last_crawl_at as string | undefined
    const lastCrawlLabel = lastCrawlAt
      ? new Date(lastCrawlAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      : null
    return [
      {
        label: '今日采集量',
        value: today !== null ? today.toLocaleString() : '--',
        // Phase 16 Issue J: 明确口径 — 今日所有运行累计，区别于 DAG 单次运行数
        sub: today !== null
          ? (today > 0
              ? '条 (今日累计)'
              : `今日 0 / 历史累计 ${lastTotal} · 最近 ${lastCrawlLabel ?? '未知'}`)
          : '条 (今日累计)',
        color: today !== null && today > 0 ? colors.primary : colors.muted,
        icon: 'Download',
      },
      {
        label: '采集成功率',
        // Phase 3.8.8: 0 条采集时标 '--', 不用 success_rate 混淆
        value: (s?.today_crawl_volume ?? 0) > 0 && typeof s?.success_rate === 'number'
          ? `${(s.success_rate * 100).toFixed(1)}%`
          : '--',
        sub: (s?.today_crawl_volume ?? 0) > 0 ? '有效/总计' : '今日无采集',
        color: (s?.today_crawl_volume ?? 0) > 0 ? colors.primary : colors.muted,
        icon: 'CircleCheck',
        trend: 'stable',
      },
      {
        label: '自动爬虫',
        value: typeof s?.active_data_sources === 'number' ? String(s.active_data_sources) : '--',
        // fix: 使用 dataSources 总数作为合计基数
        sub: typeof s?.active_data_sources === 'number'
          ? `${s.active_data_sources}个自动数据源 (共${pipeline.dataSources.length}个)`
          : '加载中...',
        color: colors.info,
        icon: 'Connection',
        trend: 'stable',
      },
    ]
  })

  // ── 流水线阶段时间线 (DAG) ──
  const timelineStages = computed<PipelineStage[]>(() => {
    // 将 API 返回的阶段映射到 5 个标准阶段名，缺失的用 pending 补齐
    // 复合阶段名（dedup_clean → dedup + clean）必须一对一匹配，防止重复消费
    const stageMap = new Map<string, PipelineStage>()
    for (const s of pipeline.stages) {
      stageMap.set(s.name, s)
    }
    const consumed = new Set<string>()  // 已映射到标准阶段的 API 阶段名
    const takeByName = (name: string): PipelineStage | undefined => {
      const direct = stageMap.get(name)
      if (direct && !consumed.has(name)) {
        consumed.add(name)
        return { ...direct, name }  // 用标准阶段名显示，避免 dedup_clean 重复
      }
      // fix: 使用精确匹配避免子串误匹配（如 "crawler" 匹配 "crawl"）
      for (const [k, v] of stageMap) {
        if (consumed.has(k)) continue
        if (k === name || k.startsWith(name + '_')) {
          consumed.add(k)
          return { ...v, name }  // 重命名为标准阶段名
        }
      }
      return undefined
    }
    return ALL_STAGE_NAMES.map((name) => {
      const found = takeByName(name)
      if (found) return found
      return {
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
      }
    })
  })

  // Phase 3.8.8: 阻塞于上游失败 (不显示重试)
  const blockedStages = computed<Set<string>>(() => {
    const blocked = new Set<string>()
    const statusMap = Object.fromEntries(timelineStages.value.map(s => [s.name, s.status]))
    for (const s of timelineStages.value) {
      if (s.status !== 'failed') continue
      const deps = _DEPS[s.name] || []
      if (deps.some(d => statusMap[d] === 'failed')) {
        blocked.add(s.name)
      }
    }
    return blocked
  })

  const stageColorMap: Record<string, string> = {
    running: chartColors().info,
    completed: chartColors().success,
    failed: chartColors().danger,
    pending: chartColors().muted,
    skipped: '#d1d5db',
    cancelled: '#f59e0b',
  }

  // DAG 现在是串行结构（Phase 3 Plan 02 Task 2: clean 依赖 dedup），
  // 不再有并行分支/合并点；旧的 isDagBranch/isDagMerge 已删除。

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
    actionLoading.value = true
    try {
      // Phase 3.7: 触发新 run 时清空实时活动缓存
      pipeline.resetLiveActivity()
      await pipeline.triggerPipeline(triggerRunType.value, selectedStages.value)
      triggerDialogVisible.value = false
      // 立即刷新全页面数据，确保 KPI/DAG/质量面板实时联动
      await loadAll()
      const runTypeLabel = triggerRunType.value === 'full' ? '全量' : '增量'
      const stageCount = selectedStages.value.length
      ElMessage.success(`流水线已触发（${runTypeLabel}，${stageCount} 个阶段）`)
      // 执行期间加速刷新
      refreshInterval.value = 5
      startAutoRefresh()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '触发失败，请检查后端服务状态'
      ElMessage.error(`触发失败：${msg}`)
    } finally {
      actionLoading.value = false
    }
  }

  // ── 失败重试/断点续跑 ──
  // Phase 17-02 (Fix B2): 改用 last_run.id fallback, 让 failed/cancelled run 也能重试
  // (current_run 只在 status=running 时存在, 失败 run 不在其中)
  const currentRunId = computed(() => {
    return pipeline.pipelineStatus?.last_run?.id
      ?? pipeline.pipelineStatus?.current_run?.id
      ?? null
  })
  const retryingStages = ref<Set<string>>(new Set())

  async function handleRetryStage(stageName: string) {
    if (!currentRunId.value) {
      ElMessage.warning('没有可重试的运行')
      return
    }
    retryingStages.value.add(stageName)
    try {
      await pipeline.retryStage(currentRunId.value, stageName)
      // 刷全页面：重试后 DAG 需要反映阶段状态变化
      await loadAll()
      ElMessage.success(`阶段「${STAGE_LABELS[stageName] || stageName}」已重新调度执行`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '重试失败'
      ElMessage.error(`重试失败：${msg}`)
    } finally {
      retryingStages.value.delete(stageName)
    }
  }

  async function handleResume() {
    // Phase 16 B06 fix: 使用 recent_failed_run.id 而非 currentRunId (current_run 永不为 failed)
    const failedRunId = pipeline.pipelineStatus?.recent_failed_run?.id ?? currentRunId.value
    if (!failedRunId) {
      ElMessage.warning('没有可续跑的运行')
      return
    }
    actionLoading.value = true
    try {
      await pipeline.resumeRun(failedRunId)
      // 刷全页面：断点续跑后 status→running，按钮需切换，DAG 需更新
      await loadAll()
      ElMessage.success('断点续跑已启动，将从失败阶段继续执行')
      // 执行期间加速刷新
      refreshInterval.value = 5
      startAutoRefresh()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '续跑失败'
      ElMessage.error(`断点续跑失败：${msg}`)
    } finally {
      actionLoading.value = false
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
    scheduleLoading.value = true
    try {
      await pipeline.createSchedule(scheduleForm.value)
      scheduleDialogVisible.value = false
      ElMessage.success(`定时调度「${scheduleForm.value.name}」已创建`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '创建失败'
      ElMessage.error(`创建失败：${msg}`)
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleDeleteSchedule(id: string) {
    try {
      await ElMessageBox.confirm('确定删除此定时调度？', '确认')
      scheduleLoading.value = true
      await pipeline.deleteSchedule(id)
      ElMessage.success('已删除')
    } catch {
      /* cancelled — schedules list already refreshed by store */
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleTriggerSchedule(schedule: PipelineSchedule) {
    scheduleLoading.value = true
    try {
      await pipeline.triggerSchedule(schedule.id)
      // 调度触发了 pipeline run，需要刷新全页面状态
      await loadAll()
      ElMessage.success(`调度「${schedule.name}」已触发执行`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '触发失败'
      ElMessage.error(`触发调度失败：${msg}`)
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleToggleSchedule(schedule: PipelineSchedule) {
    try {
      await pipeline.updateSchedule(schedule.id, { ...schedule, enabled: !schedule.enabled })
      ElMessage.success(schedule.enabled ? '调度已禁用' : '调度已启用')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '操作失败'
      ElMessage.error(`操作失败：${msg}`)
    }
  }

  // ── 配置弹窗 ──
  const configDialogVisible = ref(false)

  function openConfigDialog() {
    pipeline.fetchConfig()
    configDialogVisible.value = true
  }

  async function handleSaveConfig() {
    if (!pipeline.config) return
    configSaving.value = true
    try {
      await pipeline.updateConfig(pipeline.config)
      configDialogVisible.value = false
      ElMessage.success('配置已保存，将在下一个流水线运行时生效')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '保存失败'
      ElMessage.error(`更新配置失败：${msg}`)
    } finally {
      configSaving.value = false
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

  // ── Phase 16 数据审核闭环: 待审核计数 ──
  const pendingReviewCount = ref(0)
  async function fetchPendingReview() {
    try {
      const data = await request.get('/admin/review-stats') as Record<string, number>
      // review-stats 返回 {position: N, skill: M, position_approved: X, skill_approved: Y}
      // pending = total - approved
      const totalPos = data.position ?? 0
      const totalSkill = data.skill ?? 0
      const approvedPos = data.position_approved ?? 0
      const approvedSkill = data.skill_approved ?? 0
      pendingReviewCount.value = (totalPos - approvedPos) + (totalSkill - approvedSkill)
    } catch { /* non-fatal */ }
  }

  // ── 生命周期 ──
  onMounted(() => {
    loadAll()
    startAutoRefresh()
    pipeline.fetchSchedules()
    pipeline.fetchConfig()
    fetchPendingReview()
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
    sseDisconnect()
  })

  return {
    // Store
    pipeline,
    // User role (LOOP-08: admin check for Pipeline management controls)
    isAdmin: userStore.isAdmin,
    // 独立加载状态
    actionLoading,
    scheduleLoading,
    configSaving,
    // 自动刷新
    autoRefresh,
    refreshInterval,
    lastRefresh,
    loadAll,
    toggleAutoRefresh,
    startAutoRefresh,
    // SSE
    sseConnected,
    sseMode,
    // 取消运行
    handleCancelRun,
    // KPI
    kpiCards,
    // 阶段摘要
    stageSummary,
    isStuck,
    stuckReason,
    // DAG 时间线
    timelineStages,
    blockedStages,
    stageColorMap,
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
    // Phase 16 数据审核闭环
    pendingReviewCount,
    // Phase 3.7: 实时活动上下文
    liveActivity: pipeline.liveActivity,
    activityHistory: pipeline.activityHistory,
  }
}
