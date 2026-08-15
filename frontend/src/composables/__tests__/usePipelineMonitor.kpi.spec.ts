/**
 * usePipelineMonitor KPI 三段口径测试（Phase 23 Task 9, IC-07 防跨页漂移）。
 *
 * 断言: PipelineMonitor 的三段 KPI（今日采集量 / 今日新增 / 历史累计 / 成功率）
 * 必须从同一 `pipeline.pipelineStatus` 派生，且与后端 status_aggregator 的聚合
 * 值一致（docs/ingestion-kpi-calibers.md 声明的唯一事实源）。禁止前端本地重新聚合。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createApp, reactive } from 'vue'

import type { PipelineStatus } from '@/stores/pipelineRun'

// ── Store mock 状态（reactive：测试中改 store 状态可驱动 computed 重算） ──
const runStoreMock = reactive({
  pipelineStatus: null as PipelineStatus | null,
  dataSources: [] as Array<Record<string, unknown>>,
  loading: false,
  stages: [] as Array<Record<string, unknown>>,
  dataQuality: null,
  runs: [] as Array<Record<string, unknown>>,
  liveActivity: {},
  fetchStatus: vi.fn(),
  fetchStages: vi.fn(),
  fetchDataQuality: vi.fn(),
  fetchDataSources: vi.fn(),
  fetchRuns: vi.fn(),
  handlePipelineEvent: vi.fn(),
  handleQualityAlert: vi.fn(),
  handleMilestone: vi.fn(),
  handleExtractionComplete: vi.fn(),
  resetLiveActivity: vi.fn(),
})

const configStoreMock = reactive({
  schedules: [],
  config: {},
  configLoading: false,
  fetchSchedules: vi.fn(),
  fetchConfig: vi.fn(),
  updateConfig: vi.fn(),
})

const userStoreMock = reactive({ isAdmin: false })

const reviewStoreMock = reactive({
  fetchStats: vi.fn().mockResolvedValue({
    position: 10, skill: 5, position_approved: 2, skill_approved: 1,
  }),
})

vi.mock('@/stores/pipelineRun', () => ({
  usePipelineRunStore: () => runStoreMock,
}))

vi.mock('@/stores/pipelineConfig', () => ({
  usePipelineConfigStore: () => configStoreMock,
  ALL_STAGE_NAMES: [],
}))

vi.mock('@/stores/user', () => ({ useUserStore: () => userStoreMock }))
vi.mock('@/stores/review', () => ({ useReviewStore: () => reviewStoreMock }))

// ── 副作用模块替换：SSE / Element / 主题 / 请求 ──
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/chartTheme', () => ({
  chartColors: () => ({
    primary: '#4f46e5', success: '#16a34a', warning: '#d97706', danger: '#dc2626',
    info: '#2563eb', muted: '#78716c', border: '#e7e5e4', foreground: '#1c1917',
    card: '#ffffff', chart: [],
  }),
}))
vi.mock('@/composables/useSSE', () => ({
  useSSE: () => ({ connected: { value: false }, mode: { value: 'disconnected' }, disconnect: vi.fn() }),
}))
vi.mock('@/config/apiBase', () => ({
  API_BASE: '/api/v1',
  apiUrl: (p: string) => `/api/v1${p}`,
}))
vi.mock('@/api/request', () => ({ setBackgroundPollMode: vi.fn() }))

import { usePipelineMonitor } from '../usePipelineMonitor'

function withSetup<T>(composable: () => T): { result: T; unmount: () => void } {
  let result: T
  const app = createApp({
    setup() {
      result = composable()
      return () => null
    },
  })
  const el = document.createElement('div')
  app.mount(el)
  const unmount = () => app.unmount()
  return { result: result!, unmount }
}

/** status_aggregator.compute_status_aggregates 输出同形 fixture（唯一事实源）。 */
function makeFixture(overrides: Partial<PipelineStatus> = {}): PipelineStatus {
  return {
    is_running: false,
    current_run: null,
    last_run: null,
    recent_failed_run: null,
    run_counts: { completed: 3, failed: 0, running: 0 },
    active_data_sources: 5,
    today_crawl_volume: 1200,
    today_crawl_new: 42,
    total_jd_raw: 10000,
    success_rate: 0.8571,
    avg_quality_score: 0.9,
    ...overrides,
  }
}

describe('usePipelineMonitor KPI 三段口径（IC-07 防跨页漂移）', () => {
  let unmount: () => void

  beforeEach(() => {
    vi.useFakeTimers()
    runStoreMock.pipelineStatus = null
    runStoreMock.dataSources = []
  })

  afterEach(() => {
    unmount?.()
    vi.useRealTimers()
  })

  it('三段 KPI 从同一 pipelineStatus 派生且与 status_aggregator 聚合值一致', () => {
    runStoreMock.pipelineStatus = makeFixture()
    const { result, unmount: teardown } = withSetup(() => usePipelineMonitor())
    unmount = teardown

    const cards = result.kpiCards.value
    expect(cards).toHaveLength(4)

    // Card 0: 今日采集量 = today_crawl_volume（与聚合器一致，含重复处理量）
    expect(cards[0].label).toBe('今日采集量')
    expect(cards[0].value).toBe((1200).toLocaleString())
    // Card 0 sub: 今日新增 / 历史累计 同源派生（同一 pipelineStatus 对象）
    expect(cards[0].sub).toContain('今日新增 42')
    expect(cards[0].sub).toContain(`历史累计 ${(10000).toLocaleString()} 条`)

    // Card 1: 采集成功率 = success_rate * 100，一位小数（与聚合器 0.8571 一致）
    expect(cards[1].label).toBe('采集成功率')
    expect(cards[1].value).toBe('85.7%')
    expect(cards[1].sub).toContain('近7天成功')
  })

  it('变更同一 pipelineStatus 后全部卡片联动重算（单源派生，无本地二次聚合）', () => {
    runStoreMock.pipelineStatus = makeFixture()
    const { result, unmount: teardown } = withSetup(() => usePipelineMonitor())
    unmount = teardown

    expect(result.kpiCards.value[0].value).toBe((1200).toLocaleString())

    // 同一聚合器输出对象整体更新 → 卡片无需其它来源即可重算
    runStoreMock.pipelineStatus = makeFixture({
      today_crawl_volume: 300,
      today_crawl_new: 7,
      total_jd_raw: 900,
      success_rate: 0.5,
    })
    expect(result.kpiCards.value[0].value).toBe((300).toLocaleString())
    expect(result.kpiCards.value[0].sub).toContain('今日新增 7')
    expect(result.kpiCards.value[0].sub).toContain(`历史累计 ${(900).toLocaleString()} 条`)
    expect(result.kpiCards.value[1].value).toBe('50.0%')
  })

  it('pipelineStatus 缺失时 KPI 诚实降级为 --（不显示伪值）', () => {
    runStoreMock.pipelineStatus = null
    const { result, unmount: teardown } = withSetup(() => usePipelineMonitor())
    unmount = teardown

    const cards = result.kpiCards.value
    expect(cards[0].value).toBe('--')
    expect(cards[1].value).toBe('--')
  })

  it('待审内容 KPI 与其它卡片同源于同一 pipelineStatus（无跨 store 拼凑）', () => {
    runStoreMock.pipelineStatus = makeFixture({ pending_review_positions: 12, pending_review_skills: 8 })
    const { result, unmount: teardown } = withSetup(() => usePipelineMonitor())
    unmount = teardown

    const card = result.kpiCards.value[3]
    expect(card.label).toBe('待审内容')
    expect(card.value).toBe('12 岗位')
    expect(card.sub).toContain('8 技能待审核')
  })
})
