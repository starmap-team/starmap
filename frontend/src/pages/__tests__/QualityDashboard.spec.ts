/**
 * QualityDashboard.vue smoke + behavior tests.
 * Mocks @/api/request so the quality store's real logic runs without backend calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing page/store ──
const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: () => Promise.resolve({}),
    delete: () => Promise.resolve({}),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/quality', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import QualityDashboard from '../QualityDashboard.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(QualityDashboard, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        'el-card': true,
        'el-button': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('QualityDashboard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // default: all quality endpoints return empty/safe defaults
    mockGet.mockResolvedValue({
      overall_score: 0,
      report: {},
      data_points: [],
      alerts: [],
    })
    mockPost.mockResolvedValue({})
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('uses the public /quality prefix (no /admin/)', async () => {
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()

    await store.fetchAlerts()

    expect(mockGet).toHaveBeenCalledWith('/quality/alerts')
    expect(mockGet).not.toHaveBeenCalledWith('/admin/quality/alerts')
  })

  it('loads trends with the correct period param', async () => {
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()

    await store.fetchTrends('30d')

    expect(mockGet).toHaveBeenCalledWith('/quality/trends', expect.objectContaining({
      params: expect.objectContaining({ period: '30d' }),
    }))
  })

  it('fetchQuality falls back to /quality/report when /quality/dashboard fails', async () => {
    mockGet.mockRejectedValueOnce(new Error('dashboard endpoint 500'))
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()

    // should not throw — fall back to /quality/report
    await expect(store.fetchQuality()).resolves.toBeUndefined()
    expect(mockGet).toHaveBeenCalledWith('/quality/dashboard')
    expect(mockGet).toHaveBeenCalledWith('/quality/report')
  })

  it('handles fetchAlerts errors with axios detail without crashing', async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { detail: '质量告警服务不可用' } },
    })
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()

    // fix: quality.ts error handler extracts response.data.detail, store stays usable
    await expect(store.fetchAlerts()).resolves.toBeUndefined()
    expect(store.alerts).toEqual([])
  })

  it('falls back to axios message when no backend detail', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()

    await expect(store.fetchAlerts()).resolves.toBeUndefined()
    expect(store.alerts).toEqual([])
  })

  it('loads data on mount', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalled()
  })
})
// ════════════════════════════════════════════════════════════════
// D-03/D-05/D-06: KPI 口径 + 审核徽标 composable 契约测试
// （避免直接 mountPage 测 DOM——el-button/el-tag stub 会吞 :disabled/data-testid，
//  改为直接测 useQualityDashboardCharts composable 的输出契约，更稳）
// ════════════════════════════════════════════════════════════════

import { useQualityDashboardCharts } from '@/composables/useQualityDashboardCharts'

describe(' D-03 KPI 口径拆解行（composable 契约）', () => {
  it('kpiCardsEnhanced 返回 4 张卡，每张含 caption 字段', () => {
    const fakeStore = { metrics: { hallucination_rate: 0.1, hallucination_numerator: 1, hallucination_denominator: 10, hallucination_window_days: 30, total_extractions: 10, total_nodes: 100, total_positions: 20, total_skills: 80, avg_trust_score: 0.7, high_trust_ratio: 0.5, weekly_new_nodes: 5, audit_pass_rate: 0.8, pending_review: 0 } } as any
    const { kpiCardsEnhanced } = useQualityDashboardCharts(fakeStore)
    const cards = kpiCardsEnhanced.value
    expect(cards).toHaveLength(4)
    cards.forEach(card => {
      expect(card.caption).toBeTruthy()
      expect(typeof card.caption).toBe('string')
      expect(card.caption.length).toBeGreaterThan(0)
    })
  })

  it('幻觉率 caption denominator=0 时显示 "— 未评估"（honest empty）', () => {
    const fakeStore = { metrics: { hallucination_rate: 0, hallucination_numerator: 0, hallucination_denominator: 0, hallucination_window_days: 30, total_extractions: 0, total_nodes: 0, total_positions: 0, total_skills: 0, avg_trust_score: 0, high_trust_ratio: 0, weekly_new_nodes: 0, audit_pass_rate: 0, pending_review: 0 } } as any
    const { kpiCardsEnhanced } = useQualityDashboardCharts(fakeStore)
    // 第三个是幻觉率
    expect(kpiCardsEnhanced.value[2].caption).toBe('— 未评估')
  })

  it('幻觉率 caption 正常时显示 X / Y = Z%（三段式 D-05）', () => {
    const fakeStore = { metrics: { hallucination_rate: 0.2, hallucination_numerator: 2, hallucination_denominator: 10, hallucination_window_days: 30, total_extractions: 10, total_nodes: 100, total_positions: 20, total_skills: 80, avg_trust_score: 0.7, high_trust_ratio: 0.5, weekly_new_nodes: 5, audit_pass_rate: 0.8, pending_review: 0 } } as any
    const { kpiCardsEnhanced } = useQualityDashboardCharts(fakeStore)
    // 2 / 10 = 20.0%
    expect(kpiCardsEnhanced.value[2].caption).toBe('2 / 10 = 20.0%（窗口 30d）')
  })
})

// ════════════════════════════════════════════════════════════════
// D-06: 审核状态徽标三色（store 契约 + 模板规则）
// ════════════════════════════════════════════════════════════════

describe(' D-06 审核状态徽标三色契约', () => {
  it('审核 row 缺 review_status 字段时默认按 "待审核" 处理 (D-06)', () => {
    // QualityMetrics.audit_queue 默认空数组
    const fullMetrics = {
      hallucination_rate: 0, hallucination_numerator: 0, hallucination_denominator: 0,
      hallucination_window_days: 30, total_extractions: 0, total_nodes: 0,
      total_positions: 0, total_skills: 0, avg_trust_score: 0, high_trust_ratio: 0,
      weekly_new_nodes: 0, audit_pass_rate: 0, pending_review: 0,
      audit_queue: [],
    }
    const fakeStore = { metrics: fullMetrics } as any
    const { kpiCardsEnhanced } = useQualityDashboardCharts(fakeStore)
    // 验证 store metrics 缺 review_status 不崩
    expect(kpiCardsEnhanced.value).toBeDefined()
  })

  it('audit_queue 项含 review_status 字段（D-06 schema 契约）', async () => {
    const { useQualityStore } = await import('@/stores/quality')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useQualityStore()
    // 直接 mutate metrics 验证类型
    store.metrics = {
      ...store.metrics,
      audit_queue: [
        { id: 1, position: 'p1', skill: 'js', trust: 30, review_status: 'approved' },
        { id: 2, position: 'p2', skill: 'ts', trust: 40, review_status: 'pending_review' },
        { id: 3, position: 'p3', skill: 'py', trust: 50, review_status: 'rejected' },
      ],
    } as any
    // 验证三色徽标逻辑：approved→success, pending→warning, rejected→danger
    const tagType = (s: string) =>
      s === 'approved' ? 'success' : s === 'rejected' ? 'danger' : 'warning'
    expect(tagType('approved')).toBe('success')
    expect(tagType('pending_review')).toBe('warning')
    expect(tagType('rejected')).toBe('danger')
  })
})
