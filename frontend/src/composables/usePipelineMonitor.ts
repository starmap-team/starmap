/**
 * 数据流水线监控页 composable（Phase 03 Plan 03 Task 8 拆分后瘦身 < 400 行）。
 * 保留核心：pipeline 兼容对象 / SSE / 自动刷新 / KPI / 阶段摘要 / 卡死检测 /
 * DAG 时间线 / 配置弹窗 / 待审核计数。触发/取消/重试 → useTriggerPipeline；调度 → useSchedules。
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'

import { ElMessage } from 'element-plus'
import { usePipelineRunStore } from '@/stores/pipelineRun'
import { usePipelineConfigStore } from '@/stores/pipelineConfig'
import { useReviewStore } from '@/stores/review'
import { useUserStore } from '@/stores/user'
import type { PipelineStage, DataMilestone, ExtractionComplete } from '@/stores/pipelineRun'
import type { QualityAlert } from '@/types/quality'
import { ALL_STAGE_NAMES } from '@/stores/pipelineConfig'
import { useSSE } from '@/composables/useSSE'
import { API_BASE } from '@/config/apiBase'
import { setBackgroundPollMode } from '@/api/request'
import { chartColors } from '@/utils/chartTheme'
import type { PipelineConfig } from '@/stores/pipelineConfig'
// Default auto-refresh interval in seconds
const DEFAULT_REFRESH_INTERVAL_SEC = 10

// Phase 3.8.8: 内联 deps（串行 DAG，不含 timeseries）
const _DEPS: Record<string, string[]> = { crawl: [], dedup: ['crawl'], clean: ['dedup'], import: ['clean'], graph_sync: ['import'] }

export function usePipelineMonitor() {
  const runStore = usePipelineRunStore()
  const configStore = usePipelineConfigStore()
  const userStore = useUserStore()
  // pipeline 兼容对象（用于模板中的 pipeline.xxx 访问）
  const pipeline = {
    get pipelineStatus() { return runStore.pipelineStatus },
    get is_running() { return runStore.pipelineStatus?.is_running ?? false },
    get current_run() { return runStore.pipelineStatus?.current_run ?? null },
    get loading() { return runStore.loading || configStore.configLoading },
    get stages() { return runStore.stages },
    get dataQuality() { return runStore.dataQuality },
    get dataSources() { return runStore.dataSources },
    get runs() { return runStore.runs },
    get schedules() { return configStore.schedules },
    get config() { return configStore.config },
    fetchStatus: runStore.fetchStatus,
    fetchStages: runStore.fetchStages,
    fetchDataQuality: runStore.fetchDataQuality,
    fetchDataSources: runStore.fetchDataSources,
    fetchRuns: runStore.fetchRuns,
    fetchConfig: configStore.fetchConfig,
    handlePipelineEvent: runStore.handlePipelineEvent,
    handleQualityAlert: runStore.handleQualityAlert,
    handleMilestone: runStore.handleMilestone,
    handleExtractionComplete: runStore.handleExtractionComplete,
    // Phase 3.7: 实时活动
    liveActivity: runStore.liveActivity,
    resetLiveActivity: runStore.resetLiveActivity,
  }

  // ── 独立操作加载状态（配置保存） ──
  const configSaving = ref(false)

  // ── 自动刷新 ──
  const autoRefresh = ref(true)
  const refreshInterval = ref(DEFAULT_REFRESH_INTERVAL_SEC)
  let timer: ReturnType<typeof setInterval> | null = null
  const lastRefresh = ref('')

  // 2026-08-11: 自动刷新属于后台轮询, 失败时静默降级不弹"请求超时"toast 刷屏
  // (request.ts 的 setBackgroundPollMode 在请求前置位; 手动刷新按钮仍走正常 toast)
  async function loadAll({ background = false }: { background?: boolean } = {}) {
    if (background) setBackgroundPollMode(true)
    try {
      await Promise.all([
        pipeline.fetchStatus(),
        pipeline.fetchStages(),
        pipeline.fetchDataQuality(),
        pipeline.fetchDataSources(),
        // fix: 加载历史运行记录，否则刷新后 runs 列表为空
        pipeline.fetchRuns(),
      ])
      lastRefresh.value = new Date().toLocaleTimeString()
    } finally {
      if (background) setBackgroundPollMode(false)
    }
  }

  function startAutoRefresh() {
    if (timer) clearInterval(timer)
    if (autoRefresh.value) {
      timer = setInterval(() => loadAll({ background: true }), refreshInterval.value * 1000)
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
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pipeline_update' && data.data) {
            pipeline.handlePipelineEvent(data.data)
          }
        } catch { /* ignore parse errors */ }
      },
    },
  )

  // ── 阶段进度摘要 (Phase 3.8.2: 解决"17% 看不出含义"问题) ──
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
    // 2026-08-12 (pipeline 联调): 当采集>0 但入库=0 时，说明本批与库中内容重复，
    // 追加解释（crawl 阶段持久化 records_new/records_duplicate）。
    let importNote = ''
    let progressMessage = `${completed}已完成 / ${total}总阶段, 采集${crawlRecords.toLocaleString()}条/入库${importRecords.toLocaleString()}条, 累计 ${(totalDuration / 1000).toFixed(0)}s`
    if (crawlRecords > 0 && importRecords === 0) {
      const crawlStage = stages.find(s => s.name === 'crawl')
      const dup = crawlStage?.records_duplicate ?? 0
      const fresh = crawlStage?.records_new ?? 0
      if (fresh === 0 && dup > 0) {
        importNote = '（本批全部与库中已有记录重复，未新增）'
        progressMessage += importNote
      } else if (fresh === 0) {
        importNote = '（未产生新增，可能全部重复）'
        progressMessage += importNote
      }
    }
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
      importNote,
      progressMessage,
    }
  })

  // ── Phase 3.8.5: 卡死检测 (is_running=true 但唯一 running 阶段无进展) ──
  const isStuck = computed(() => {
    const ps = runStore.pipelineStatus
    if (!ps?.is_running) return false
    const activeStages = (ps.current_run?.stages || []).filter((s: { status: string }) => s.status !== 'skipped')
    if (!activeStages.length) return false
    const TERMINAL = new Set(['completed', 'failed'])
    if (activeStages.every((s: { status: string }) => TERMINAL.has(s.status))) return true
    const runningStages = activeStages.filter((s: { status: string }) => s.status === 'running')
    if (runningStages.length === 0) {
      return activeStages.some((s: { status: string }) => s.status === 'pending')
    }
    for (const rs of runningStages) {
      const dur = (rs.duration_ms || 0)
      const records = rs.records_processed || 0
      if (dur > 5 * 60 * 1000 && records === 0) return true
      if (dur > 30 * 60 * 1000) return true
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
      if ((rs.duration_ms || 0) > 30 * 60 * 1000) return `${rs.name} 阶段已运行 > 30 分钟, 可能永久卡死`
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
    // 2026-08-12 (pipeline 联调): 今日采集量 = 今日各 run crawl 处理量之和（含重复）；
    // 今日新增 = jd_raw 今日新行；历史累计 = jd_raw 全表行数。三者口径在 status
    // 聚合器统一，避免"DAG 显示采集 70 但今日 0"的矛盾。
    const todayVolume = s && typeof s.today_crawl_volume === 'number' ? s.today_crawl_volume : null
    const todayNew = s?.today_crawl_new ?? 0
    const totalJdRaw = s?.total_jd_raw ?? 0
    // Phase 4 P3: 显示最近采集时间，让用户知道数据是否陈旧
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lastCrawlAt = (s as any)?.last_crawl_at as string | undefined
    const lastCrawlLabel = lastCrawlAt
      ? new Date(lastCrawlAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      : null
    const successRate = typeof s?.success_rate === 'number' ? s.success_rate : null
    return [
      {
        label: '今日采集量',
        value: todayVolume !== null ? todayVolume.toLocaleString() : '--',
        sub: todayVolume !== null
          ? `今日新增 ${todayNew} · 历史累计 ${totalJdRaw.toLocaleString()} 条${lastCrawlLabel ? ` · 最近 ${lastCrawlLabel}` : ''}`
          : '条 (今日处理量)',
        color: todayVolume !== null && todayVolume > 0 ? colors.primary : colors.muted,
        icon: 'Download',
      },
      {
        label: '采集成功率',
        // 2026-08-12: 恒显近 7 天成功率（原逻辑要求今日采集量>0 才显示，导致 "--"）
        value: successRate !== null ? `${(successRate * 100).toFixed(1)}%` : '--',
        sub: `近7天成功/运行总数${todayNew === 0 ? ' · 今日无新增' : ` · 今日新增 ${todayNew}`}`,
        color: successRate !== null && successRate > 0 ? colors.primary : colors.muted,
        icon: 'CircleCheck',
        trend: 'stable',
      },
      {
        label: '活跃数据源',
        // 2026-08-12: 标签由"自动爬虫"改为"活跃数据源"，避免与下方"可用爬虫源"混淆
        value: typeof s?.active_data_sources === 'number' ? String(s.active_data_sources) : '--',
        sub: typeof s?.active_data_sources === 'number'
          ? `${s.active_data_sources} 个 active（共 ${pipeline.dataSources.length} 个）`
          : '加载中...',
        color: colors.info,
        icon: 'Connection',
        trend: 'stable',
      },
      {
        // 2026-08-14: 跨模块联动——数据产出后的去向（与 admin 内容审核同口径）
        label: '待审内容',
        value: typeof s?.pending_review_positions === 'number'
          ? `${s.pending_review_positions} 岗位`
          : '--',
        sub: typeof s?.pending_review_skills === 'number'
          ? `${s.pending_review_skills} 技能待审核 · 新抽取内容进入内容审核队列`
          : '加载中...',
        color: colors.warning,
        icon: 'DocumentChecked',
        trend: 'stable',
      },
    ]
  })

  // ── 流水线阶段时间线 (DAG) ──
  const timelineStages = computed<PipelineStage[]>(() => {
    // 将 API 返回的阶段映射到 5 个标准阶段名，缺失的用 pending 补齐
    const stageMap = new Map<string, PipelineStage>()
    for (const s of pipeline.stages) {
      stageMap.set(s.name, s)
    }
    const consumed = new Set<string>()
    const takeByName = (name: string): PipelineStage | undefined => {
      const direct = stageMap.get(name)
      if (direct && !consumed.has(name)) {
        consumed.add(name)
        return { ...direct, name }
      }
      for (const [k, v] of stageMap) {
        if (consumed.has(k)) continue
        if (k === name || k.startsWith(name + '_')) {
          consumed.add(k)
          return { ...v, name }
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
      if (deps.some(d => statusMap[d] === 'failed')) blocked.add(s.name)
    }
    return blocked
  })

  // ── 配置弹窗 ──
  const configDialogVisible = ref(false)

  function openConfigDialog() {
    pipeline.fetchConfig?.()
    configDialogVisible.value = true
  }

  async function handleSaveConfig(config?: PipelineConfig) {
    const target = config ?? pipeline.config
    if (!target) return
    configSaving.value = true
    try {
      await configStore.updateConfig(target)
      configDialogVisible.value = false
      ElMessage.success('配置已保存，将在下一个流水线运行时生效')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '保存失败'
      ElMessage.error(`更新配置失败：${msg}`)
    } finally {
      configSaving.value = false
    }
  }

  // ── Phase 16 数据审核闭环: 待审核计数 ──
  const pendingReviewCount = ref(0)
  async function fetchPendingReview() {
    try {
      const data = await useReviewStore().fetchStats()
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
    configStore.fetchSchedules()
    configStore.fetchConfig()
    fetchPendingReview()
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
    sseDisconnect()
  })

  return {
    // Store 兼容对象
    pipeline,
    // User role (LOOP-08: admin check for Pipeline management controls)
    isAdmin: userStore.isAdmin,
    // 配置保存 loading
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
    // KPI
    kpiCards,
    // 阶段摘要
    stageSummary,
    isStuck,
    stuckReason,
    // DAG 时间线
    timelineStages,
    blockedStages,
    // 配置
    configDialogVisible,
    openConfigDialog,
    handleSaveConfig,
    // Phase 16 数据审核闭环
    pendingReviewCount,
    // Phase 3.7: 实时活动上下文
    liveActivity: pipeline.liveActivity,
  }
}
