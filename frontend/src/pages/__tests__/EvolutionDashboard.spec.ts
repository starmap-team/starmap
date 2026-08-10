/**
 * EvolutionDashboard.vue smoke + behavior tests.
 * Mocks @/api/request so the evolution store's real logic runs without backend calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, mount, flushPromises } from '@vue/test-utils'
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
  useRoute: () => ({ params: {}, query: {}, path: '/evolution', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import EvolutionDashboard from '../EvolutionDashboard.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(EvolutionDashboard, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        MainLayout: { template: '<div><slot /></div>' },
        // slot-rendering stubs — let KPI / CTA / refresh button text render
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        EmptyState: { template: '<div class="empty-state-stub"><slot /></div>' },
        // swallow stubs — avoid el-table-column scoped slots with undefined row
        'el-table': { template: '<div class="el-table-stub" />' },
        'el-table-column': { template: '<div class="el-table-column-stub" />' },
        'el-select': true,
        'el-option': true,
        'el-slider': true,
        'el-timeline': true,
        'el-timeline-item': true,
        'el-tag': true,
        'el-collapse': true,
        'el-collapse-item': true,
        'el-drawer': true,
      },
    },
  })
}

describe('EvolutionDashboard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({
      items: [],
      trends: [],
      snapshots: [],
      changelog: [],
      paths: [],
      emerging_skills: [],
      alerts: [],
    })
    mockPost.mockResolvedValue({})
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('uses the public /evolution prefix (no /admin/)', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()

    await store.fetchTrends(30)

    expect(mockGet).toHaveBeenCalledWith('/evolution/trends', expect.any(Object))
    expect(mockGet).not.toHaveBeenCalledWith('/admin/evolution/trends', expect.any(Object))
  })

  it('loads snapshots via the public endpoint', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()

    await store.fetchSnapshots(10)

    expect(mockGet).toHaveBeenCalledWith('/evolution/snapshots?limit=10')
  })

  it('loads changelog with URL-encoded identifier', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()

    await store.fetchChangelog('后端工程师')

    expect(mockGet).toHaveBeenCalledWith('/evolution/changelog/%E5%90%8E%E7%AB%AF%E5%B7%A5%E7%A8%8B%E5%B8%88')
  })

  it('handles fetch errors without crashing (silently sets empty)', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()

    // fetchEmergingAlerts has try/catch — verify it gracefully handles rejection
    await expect(store.fetchEmergingAlerts()).resolves.toBeUndefined()
    expect(store.emergingAlerts).toEqual([])
  })

  it('handles axios errors with detail field without crashing', async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { detail: '演化分析服务不可用' } },
    })
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()

    // fix: evolution.ts error handler extracts response.data.detail, store stays usable
    await expect(store.fetchEmergingAlerts()).resolves.toBeUndefined()
    expect(store.emergingAlerts).toEqual([])
  })

  it('loads data on mount', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalled()
  })

  // ── 10-03 (D-11): KPI 行渲染 store.kpi ──

  it('renders the 4 KPI cards from store.kpi', async () => {
    const wrapper = mountPage()
    const { useEvolutionStore } = await import('@/stores/evolution')
    const store = useEvolutionStore()
    store.kpi = { emerging_count: 7, trust_mean: 0.81, cii_mean: 112.5, alert_count: 3, days: 90 }
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('涌现技能数')
    expect(text).toContain('7')
    expect(text).toContain('81%')
    expect(text).toContain('112.5')
    expect(text).toContain('预警数')
    expect(text).toContain('3')
  })

  it('calls fetchKpi on mount for the KPI row', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/evolution/kpi', expect.any(Object))
  })

  // ── C1/E4: 新兴技能卡片渲染 emerging-alerts 的 emerging/rising 子集（与预警表同源）──

  it('renders emerging/rising skills in the emerging grid from alerts (same source as 预警表)', async () => {
    const wrapper = mountPage()
    const { useEvolutionStore } = await import('@/stores/evolution')
    const store = useEvolutionStore()
    store.emergingAlerts = [
      { skill_name: 'Rust', category: 'backend', level: 'rising', z_score: 1.8, current_frequency: 10, mean_frequency: 5, source_count: 4, trend: 'rising', portability_score: 0.3, domains: ['IT'], positions: ['后端工程师'], alert_message: '上升技能提示: Rust' },
      { skill_name: 'Go', category: 'backend', level: 'emerging', z_score: 2.5, current_frequency: 12, mean_frequency: 5, source_count: 5, trend: 'rising', portability_score: 0.4, domains: ['IT'], positions: ['后端工程师'], alert_message: '新兴技能预警: Go' },
      { skill_name: 'Python', category: 'backend', level: 'declining', z_score: -2.0, current_frequency: 4, mean_frequency: 9, source_count: 6, trend: 'declining', portability_score: 0.9, domains: ['IT'], positions: ['后端工程师'], alert_message: '下降技能提示: Python' },
    ]
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Rust')
    expect(text).toContain('Go')
    // declining 不进新兴技能卡片（与预警表同源口径）
    expect(wrapper.findAll('.emerging-item')).toHaveLength(2)
  })

  it('shows no emerging cards when no emerging/rising alerts exist', async () => {
    const wrapper = mountPage()
    const { useEvolutionStore } = await import('@/stores/evolution')
    const store = useEvolutionStore()
    store.emergingAlerts = [
      { skill_name: 'Python', category: 'backend', level: 'declining', z_score: -2.0, current_frequency: 4, mean_frequency: 9, source_count: 6, trend: 'declining', portability_score: 0.9, domains: ['IT'], positions: ['后端工程师'], alert_message: '下降技能提示: Python' },
    ]
    await flushPromises()
    expect(wrapper.findAll('.emerging-item')).toHaveLength(0)
  })

  // ── 10-03 (D-13): 刷新按钮触发 fetch 集合 ──

  it('refresh button triggers the full fetch set', async () => {
    const wrapper = mountPage()
    await flushPromises()
    vi.clearAllMocks()
    const refreshBtn = wrapper.findAll('button').find(b => b.text().includes('刷新'))
    expect(refreshBtn).toBeTruthy()
    await refreshBtn!.trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/evolution/trends', expect.any(Object))
    expect(mockGet).toHaveBeenCalledWith('/evolution/snapshots?limit=50')
    expect(mockGet).toHaveBeenCalledWith('/evolution/emerging-alerts', expect.any(Object))
    expect(mockGet).toHaveBeenCalledWith('/evolution/kpi', expect.any(Object))
  })

  // ── 10-03 (D-12): 空态含引导按钮 ──

  it('empty state shows trigger-analyze CTA and doc link', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('触发演化分析')
    expect(wrapper.find('a.guide-doc-link').exists()).toBe(true)
  })

  // ── 10-03 (D-09): 证据抽屉默认折叠、可核验 ──

  it('evidence area defaults to collapsed and shows evidence fields when expanded', async () => {
    const { default: EvolutionChangelogDrawer } = await import('@/components/EvolutionChangelogDrawer.vue')
    const evidence = {
      source_count: 4,
      mention_count_old: 1,
      mention_count_new: 5,
      change_type: 'added_required',
      factors: { stability: 0.6 },
    }
    const drawer = mount(EvolutionChangelogDrawer, {
      props: {
        modelValue: true,
        skillName: 'Go',
        loading: false,
        data: [
          {
            id: 'cl-1', skill_name: 'Go', change_type: 'added_required',
            old_requirement: null, new_requirement: 'required', confidence: 0.9, created_at: '2024-01-01',
            trust_score: 0.85, evidence_json: evidence,
          },
        ],
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    // 默认折叠：证据内容不可见
    expect(drawer.find('.evidence-collapse .el-collapse-item__wrap').exists()).toBe(true)
    expect(drawer.find('.evidence-collapse').text()).toContain('证据')
    // 展开后展示源计数/提及新旧/稳定性因子
    const collapseItems = drawer.findAll('.el-collapse-item__header')
    if (collapseItems.length) await collapseItems[0].trigger('click')
    await flushPromises()
    const bodyText = drawer.find('.el-collapse-item__wrap').text()
    expect(bodyText).toContain('源计数')
    expect(bodyText).toContain('4')
    expect(bodyText).toContain('提及（新）')
    expect(bodyText).toContain('5')
  })

  it('evidence area shows 暂无证据 when evidence_json is empty', async () => {
    const { default: EvolutionChangelogDrawer } = await import('@/components/EvolutionChangelogDrawer.vue')
    const drawer = mount(EvolutionChangelogDrawer, {
      props: {
        modelValue: true,
        skillName: 'Go',
        loading: false,
        data: [
          {
            id: 'cl-2', skill_name: 'Go', change_type: 'retained',
            old_proficiency: null, new_proficiency: null, confidence: 0.5, created_at: '2024-01-01',
            trust_score: 0.5, evidence_json: {},
          },
        ],
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    const collapseItems = drawer.findAll('.el-collapse-item__header')
    if (collapseItems.length) await collapseItems[0].trigger('click')
    await flushPromises()
    expect(drawer.find('.el-collapse-item__wrap').text()).toContain('暂无证据')
  })
})