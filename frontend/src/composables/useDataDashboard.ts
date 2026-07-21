/**
 * Unified DataDashboard composable — merges 4 single-caller composables:
 *   useDashboardDisplay (97L) + useDashboardKpiCards (118L)
 *   + useDashboardRealtimeSync (147L) + useDashboardCharts (284L)
 * into a single file (646L → ~550L after import dedup).
 *
 * ponytail: all 4 were single-caller abstractions served only by DataDashboard.vue.
 * Merging removes 3 files + 3 import chains with zero logic change.
 */
import { computed, onMounted, onUnmounted, ref, watch, type Component, type ComputedRef, type Ref } from 'vue'
import {
  Connection, Share, Collection, User, Star, Medal, TrendCharts, Coin,
} from '@element-plus/icons-vue'
import { chartColors, tooltipStyle } from '@/utils/chartTheme'
import { ECHARTS_PALETTE } from '@/utils/graphColors'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import { useSSE } from '@/composables/useSSE'
import type { useDashboardStore, PipelineTimelineItem, RealtimeEvent, SkillDomain, QualityTrend } from '@/stores/dashboard'
import type { EmergingSkill } from '@/types/evolution'

type DashboardStore = ReturnType<typeof useDashboardStore>

// =============================================================================
// 1. Dashboard Display — pipeline stages, status colors, time formatting
// =============================================================================

const DEFAULT_PIPELINE_STAGES: ReadonlyArray<PipelineTimelineItem> = [
  { stage: '采集', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '去重', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '清洗', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '入库', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  { stage: '图谱', status: 'waiting', started_at: '', completed_at: null, records_processed: 0, progress: 0 },
]

export function stageIcon(status: string): string {
  switch (status) {
    case 'running': return '●'
    case 'completed': return '✓'
    case 'failed': return '✗'
    default: return '○'
  }
}

function _useDashboardDisplay(store: DashboardStore) {
  const colors = chartColors()

  const pipelineStages: ComputedRef<PipelineTimelineItem[]> = computed(() => {
    if (store.pipelineTimeline.length) return store.pipelineTimeline as PipelineTimelineItem[]
    return [...DEFAULT_PIPELINE_STAGES]
  })

  const statusColor = computed<Record<string, string>>(() => ({
    running: colors.info,
    completed: colors.success,
    failed: colors.danger,
    waiting: colors.muted + '33',
  }))

  const eventIcon: Record<string, string> = {
    skill_update: '💡',
    match_event: '🎯',
    graph_update: '🔗',
    pipeline_event: '⚙️',
    extraction: '📄',
  }

  const eventSeverityColor: Record<string, string> = {
    info: colors.chart[0] + '99',
    success: colors.success + '99',
    warning: colors.warning + '99',
    error: colors.danger + '99',
  }

  const eventTypeColor = computed<Record<string, string>>(() => ({
    pipeline_update: 'var(--info)',
    quality_alert: 'var(--success)',
    data_milestone: 'var(--warning)',
    extraction_complete: 'var(--chart-3)',
    skill_update: 'var(--chart-2)',
    graph_update: 'var(--chart-1)',
    match_event: 'var(--chart-4)',
    pipeline_event: 'var(--info)',
    extraction: 'var(--chart-3)',
  }))

  function formatTime(ts: string): string {
    if (!ts) return ''
    const d = new Date(ts)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    if (isToday) return `${h}:${m}:${s}`
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${mo}-${day} ${h}:${m}`
  }

  return { pipelineStages, statusColor, eventIcon, eventSeverityColor, eventTypeColor, formatTime, stageIcon }
}

// =============================================================================
// 2. KPI Cards — 8 card definitions as computed
// =============================================================================

export interface KpiCardDef {
  label: string
  target: number
  suffix: string
  decimals: number
  icon: Component
  color: string
  glow: string
  route: string
}

function _useDashboardKpiCards(store: DashboardStore): ComputedRef<KpiCardDef[]> {
  return computed(() => {
    const cc = chartColors()
    return [
      { label: '总节点数', target: store.overview?.total_nodes ?? 0, suffix: '', decimals: 0, icon: Connection, color: cc.chart[0], glow: cc.chart[0] + '40', route: '/' },
      { label: '总关系数', target: store.overview?.total_edges ?? 0, suffix: '', decimals: 0, icon: Share, color: cc.chart[2], glow: cc.chart[2] + '40', route: '/' },
      { label: '技能域', target: store.overview?.total_domains ?? 0, suffix: '', decimals: 0, icon: Collection, color: cc.success, glow: cc.success + '40', route: '/learning' },
      { label: '岗位数', target: store.overview?.total_positions ?? 0, suffix: '', decimals: 0, icon: User, color: cc.danger, glow: cc.danger + '40', route: '/positions' },
      { label: '技能数', target: store.overview?.total_skills ?? 0, suffix: '', decimals: 0, icon: Star, color: cc.warning, glow: cc.warning + '40', route: '/quality' },
      { label: '信任评分', target: (store.overview?.trust_score ?? 0) * 100, suffix: '%', decimals: 1, icon: Medal, color: cc.info, glow: cc.info + '40', route: '/quality' },
      { label: '本周新增', target: store.overview?.weekly_new_nodes ?? 0, suffix: '', decimals: 0, icon: TrendCharts, color: cc.chart[3], glow: cc.chart[3] + '40', route: '/evolution' },
      { label: '数据源', target: store.overview?.active_data_sources ?? 0, suffix: '', decimals: 0, icon: Coin, color: cc.chart[4], glow: cc.chart[4] + '40', route: '/datasources' },
    ]
  })
}

// =============================================================================
// 3. Realtime Sync — SSE + polling + clock tick
// =============================================================================

const REFRESH_DEBOUNCE_MS = 500
const OVERVIEW_REFRESH_MS = 30_000
const CLOCK_TICK_MS = 1_000

const EVENT_REFRESH_MAP: Readonly<Record<RealtimeEvent['type'], (keyof DashboardStore)[]>> = {
  skill_update:       ['fetchOverview', 'fetchDistribution'],
  graph_update:       ['fetchOverview', 'fetchDistribution'],
  match_event:        ['fetchOverview'],
  pipeline_event:     ['fetchPipelineTimeline'],
  extraction:         ['fetchOverview'],
}

export type ConnectionState = 'connecting' | 'connected' | 'polling' | 'disconnected'

export interface DashboardRealtimeSyncApi {
  clockTick: Ref<number>
  sseConnected: Ref<boolean>
  connectionState: Ref<ConnectionState>
}

function _useDashboardRealtimeSync(store: DashboardStore, sseUrl: string, pollUrl: string): DashboardRealtimeSyncApi {
  const clockTick: Ref<number> = ref(0)
  const sseConnected: Ref<boolean> = ref(false)
  const connectionState: Ref<ConnectionState> = ref('connecting')

  let refreshTimer: ReturnType<typeof setInterval> | null = null
  let clockTimer: ReturnType<typeof setInterval> | null = null
  const pendingRefreshTimers = new Map<string, ReturnType<typeof setTimeout>>()

  function scheduleTargetedRefresh(fetchMethods: (keyof DashboardStore)[]): void {
    for (const method of fetchMethods) {
      if (!pendingRefreshTimers.has(method)) {
        const timer = setTimeout(() => {
          pendingRefreshTimers.delete(method)
          const fn = store[method]
          if (typeof fn === 'function') void (fn as () => Promise<void>)()
        }, REFRESH_DEBOUNCE_MS)
        pendingRefreshTimers.set(method, timer)
      }
    }
  }

  function clearPendingRefreshTimers(): void {
    for (const timer of pendingRefreshTimers.values()) clearTimeout(timer)
    pendingRefreshTimers.clear()
  }

  function stopPollingInterval() {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }

  function startPollingInterval() {
    stopPollingInterval()
    refreshTimer = setInterval(() => { void store.fetchOverview() }, OVERVIEW_REFRESH_MS)
  }

  onMounted(async () => {
    await store.fetchAll()
    connectionState.value = 'connecting'
    startPollingInterval()

    const { connected, mode } = useSSE(sseUrl, {
      onMessage: (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent
          if (data?.type) {
            store.addRealtimeEvent(data)
            const targets = EVENT_REFRESH_MAP[data.type]
            if (targets) scheduleTargetedRefresh(targets)
          }
        } catch { /* heartbeat */ }
      },
      onError: () => {
        if (import.meta.env.DEV) console.warn('[Dashboard] SSE connection failed, using polling fallback')
      },
      pollUrl,
    })

    watch(connected, (val) => { sseConnected.value = val; store.sseConnected = val }, { immediate: true })
    watch(mode, (val) => {
      if (val === 'sse') { connectionState.value = 'connected'; stopPollingInterval() }
      else if (val === 'polling') { connectionState.value = 'polling'; startPollingInterval() }
      else { connectionState.value = 'disconnected'; stopPollingInterval() }
    }, { immediate: true })

    clockTimer = setInterval(() => { clockTick.value++ }, CLOCK_TICK_MS)
  })

  onUnmounted(() => {
    stopPollingInterval()
    if (clockTimer) { clearInterval(clockTimer); clockTimer = null }
    clearPendingRefreshTimers()
  })

  return { clockTick, sseConnected, connectionState }
}

// =============================================================================
// 4. Charts — 4 ECharts option computeds (from useDashboardCharts)
// =============================================================================

function _useDashboardCharts(store: DashboardStore) {
  const cc = chartColors()

  // -- Data source pie chart --
  const darkPieOption = computed(() => {
    const data = store.sourceDistribution
    if (!data?.length) return undefined
    const palette = [cc.chart[0], cc.chart[2], cc.success, cc.danger, cc.warning, cc.info, cc.primary, cc.chart[4]]
    return {
      tooltip: { trigger: 'item', ...tooltipStyle(), formatter: '{b}: {c} 条 ({d}%)' },
      legend: { bottom: 4, textStyle: { color: cc.muted, fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
      animationDuration: 1200, animationEasing: 'cubicOut' as const,
      animationDelay: (_idx: number) => _idx * 80,
      series: [{
        type: 'pie', radius: ['40%', '70%'], center: ['50%', '44%'], avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: ECHARTS_PALETTE.PIE_BORDER, borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold', color: cc.foreground }, itemStyle: { shadowBlur: 20, shadowColor: cc.chart[0] + '66' } },
        data: data.map((s: { name: string; count: number }, i: number) => ({ name: getSourceNameLabel(s.name), value: s.count, itemStyle: { color: palette[i % palette.length] } })),
      }],
    }
  })

  // -- Skill domain treemap --
  const treemapOption = computed(() => {
    const data = store.skillDomains
    if (!data?.length) return undefined
    return {
      tooltip: { backgroundColor: cc.card + 'E6', borderColor: cc.chart[0] + '4D', textStyle: { color: cc.foreground, fontSize: 12 }, formatter: '{b}: {c}' },
      series: [{
        type: 'treemap',
        data: data.map((d: SkillDomain) => ({ name: d.name, value: d.value, children: d.children?.map((c: SkillDomain) => ({ name: c.name, value: c.value })) })),
        roam: false, nodeClick: false, breadcrumb: { show: false },
        label: { show: true, formatter: '{b}', fontSize: 11, color: ECHARTS_PALETTE.LABEL, textShadowColor: 'rgba(0,0,0,0.6)', textShadowBlur: 4 },
        itemStyle: { borderColor: ECHARTS_PALETTE.PIE_BORDER, borderWidth: 2, gapWidth: 2 },
        levels: [{ itemStyle: { borderColor: ECHARTS_PALETTE.PIE_BORDER, borderWidth: 3, gapWidth: 3 } }, { colorSaturation: [0.35, 0.5], itemStyle: { borderColorSaturation: 0.6, gapWidth: 1, borderWidth: 1 } }],
        color: [cc.chart[0], cc.chart[2], cc.success, cc.danger, cc.warning, cc.info, cc.primary, cc.chart[4]],
      }],
    }
  })

  // -- Quality trend dual-axis line chart --
  const trendOption = computed(() => {
    const trends = store.qualityTrends
    if (!trends?.length) return undefined
    return {
      tooltip: { trigger: 'axis', backgroundColor: cc.card + 'E6', borderColor: cc.chart[0] + '4D', textStyle: { color: cc.foreground, fontSize: 12 } },
      legend: { top: 0, right: 0, textStyle: { color: cc.muted, fontSize: 10 }, itemWidth: 12, itemHeight: 2 },
      grid: { top: 30, bottom: 24, left: 40, right: 40 },
      xAxis: { type: 'category', data: trends.map((t: QualityTrend) => t.date.slice(5)), axisLine: { lineStyle: { color: cc.foreground + '26' } }, axisLabel: { color: cc.muted, fontSize: 10 }, axisTick: { show: false } },
      yAxis: [
        { type: 'value', name: '分值', nameTextStyle: { color: cc.muted, fontSize: 10 }, axisLabel: { color: cc.muted, fontSize: 10 }, splitLine: { lineStyle: { color: cc.foreground + '0F' } } },
        { type: 'value', name: '采集量', nameTextStyle: { color: cc.muted, fontSize: 10 }, axisLabel: { color: cc.muted, fontSize: 10 }, splitLine: { show: false } },
      ],
      series: [
        { name: '质量分', type: 'line', smooth: true, symbol: 'circle', symbolSize: 4, lineStyle: { color: cc.chart[0], width: 2 }, itemStyle: { color: cc.chart[0] }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: cc.chart[0] + '33' }, { offset: 1, color: cc.chart[0] + '00' }] } }, data: trends.map((t: QualityTrend) => t.quality_score) },
        { name: '信任分', type: 'line', smooth: true, symbol: 'circle', symbolSize: 4, lineStyle: { color: cc.success, width: 2 }, itemStyle: { color: cc.success }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: cc.success + '26' }, { offset: 1, color: cc.success + '00' }] } }, data: trends.map((t: QualityTrend) => t.trust_score ?? '-') },
        { name: '采集量', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: cc.warning, width: 1.5, type: 'dashed' }, itemStyle: { color: cc.warning }, data: trends.map((t: QualityTrend) => t.crawl_volume) },
      ],
    }
  })

  // -- Emerging skills radar --
  const radarOption = computed(() => {
    const skills = store.emergingSkills
    if (!skills?.length) return undefined
    const top = skills.slice(0, 6)
    const displayNames = top.map((s: EmergingSkill) => s.skill_name ?? s.name ?? 'unknown')
    return {
      tooltip: { backgroundColor: cc.card + 'E6', borderColor: cc.chart[0] + '4D', textStyle: { color: cc.foreground, fontSize: 12 } },
      radar: { indicator: displayNames.map((name: string) => ({ name, max: 100 })), shape: 'polygon', splitNumber: 4, axisName: { color: cc.muted, fontSize: 10 }, splitLine: { lineStyle: { color: cc.foreground + '14' } }, splitArea: { areaStyle: { color: [cc.chart[0] + '05', cc.chart[0] + '0A', cc.chart[0] + '05', cc.chart[0] + '0A'] } }, axisLine: { lineStyle: { color: cc.foreground + '1A' } } },
      series: [{
        type: 'radar',
        data: [
          { value: top.map((s: EmergingSkill) => Math.round(Math.min(100, Math.abs(s.z_score ?? 0) * 20))), name: 'Z-score', lineStyle: { color: cc.chart[0], width: 2 }, itemStyle: { color: cc.chart[0] }, areaStyle: { color: cc.chart[0] + '26' } },
          { value: top.map((s: EmergingSkill) => Math.round(Math.min(100, ((s.source_count ?? 0) / 10) * 100))), name: '来源数', lineStyle: { color: cc.chart[2], width: 2 }, itemStyle: { color: cc.chart[2] }, areaStyle: { color: cc.chart[2] + '1F' } },
        ],
      }],
    }
  })

  return { darkPieOption, treemapOption, trendOption, radarOption }
}

// =============================================================================
// 5. Unified entry — DataDashboard.vue uses this single import
// =============================================================================

export function useDataDashboard(store: DashboardStore, sseUrl: string, pollUrl: string) {
  const display = _useDashboardDisplay(store)
  const kpiCards = _useDashboardKpiCards(store)
  const sync = _useDashboardRealtimeSync(store, sseUrl, pollUrl)
  const charts = _useDashboardCharts(store)

  return {
    ...display,
    kpiCards,
    ...sync,
    ...charts,
  }
}
