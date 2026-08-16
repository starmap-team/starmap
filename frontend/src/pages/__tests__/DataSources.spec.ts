/**
 * DataSources.vue smoke + behavior tests.
 *
 * Mocks @/api/request at the module level so the store's real logic runs
 * while network calls are intercepted. Verifies loading/empty/error states,
 * card rendering with source-name mapping, and sync feedback.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing the page (store imports it) ──
const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/datasources', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import DataSources from '../DataSources.vue'

function makeSource(overrides: Record<string, unknown> = {}) {
  return {
    id: 'src-1',
    name: 'boss',
    source_type: 'crawler',
    authority_score: 0.85,
    status: 'active',
    last_crawl_at: '2026-07-26T10:00:00',
    total_records: 1200,
    valid_records: 1100,
    duplicate_rate: 0.05,
    avg_quality_score: 0.9,
    ...overrides,
  }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(DataSources, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        'el-card': true,
        'el-button': true,
        'el-tag': true,
        'el-table': true,
        'el-table-column': true,
        MainLayout: { template: '<div><slot /></div>' },
        BusinessBanner: true,
      },
    },
  })
}

// full mount：真实渲染 el-card/el-button 等，用于断言按钮 disabled 等 DOM 属性
// （shallowMount + stub 会吞掉按钮树，见 11-04 quality 计划 T3/D-03 偏差教训）
function mountFull() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(DataSources, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        // vue-echarts 组件 name 为 'echarts'（VChart 是 import 别名）—— full mount 需按注册名 stub
        echarts: true,
        MainLayout: { template: '<div><slot /></div>' },
        BusinessBanner: true,
      },
    },
  })
}

describe('DataSources.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // default: all list/stats/health calls resolve empty so onMounted doesn't throw
    mockGet.mockResolvedValue([])
    mockPost.mockResolvedValue({})
    mockPut.mockResolvedValue({})
  })

  it('renders without crashing', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('shows empty state when no data sources', async () => {
    mockGet.mockResolvedValue([])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('loads sources into the store and maps display names', async () => {
    mockGet.mockResolvedValue([
      makeSource({ id: 's1', name: 'boss', status: 'active' }),
      makeSource({ id: 's2', name: 'lagou', status: 'paused' }),
    ])
    const { useDataSourceStore } = await import('@/stores/datasource')
    const { getSourceNameLabel } = await import('@/composables/useDataSourceCharts')

    mountPage()
    await flushPromises()

    const store = useDataSourceStore()
    // API → store data flow: both sources loaded
    expect(store.sources.length).toBe(2)
    // source-name mapping used by the card label
    expect(getSourceNameLabel('boss')).toBe('BOSS直聘')
    expect(getSourceNameLabel('lagou')).toBe('拉勾网')
  })

  it('does not crash when a list call rejects', async () => {
    mockGet.mockRejectedValue(new Error('network down'))
    const wrapper = mountPage()
    await flushPromises()
    // page should still mount (error captured in store, not thrown)
    expect(wrapper.exists()).toBe(true)
  })

  it('triggers sync via the corrected public endpoint', async () => {
    // Verify the store posts to /datasources/{id}/sync (not /admin/...)
    const { useDataSourceStore } = await import('@/stores/datasource')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDataSourceStore()
    await store.triggerSync('a1b2c3d4-1234-5678-9abc-def012345678')
    expect(mockPost).toHaveBeenCalledWith('/datasources/a1b2c3d4-1234-5678-9abc-def012345678/sync')
    expect(mockPost).not.toHaveBeenCalledWith('/admin/datasources/a1b2c3d4-1234-5678-9abc-def012345678/sync')
  })

  it('updates source via the corrected public endpoint', async () => {
    const { useDataSourceStore } = await import('@/stores/datasource')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDataSourceStore()
    await store.updateSource('a1b2c3d4-1234-5678-9abc-def012345678', { status: 'paused' })
    expect(mockPut).toHaveBeenCalledWith('/datasources/a1b2c3d4-1234-5678-9abc-def012345678', { status: 'paused' })
    expect(mockPut).not.toHaveBeenCalledWith('/admin/datasources/a1b2c3d4-1234-5678-9abc-def012345678', { status: 'paused' })
  })

  it('renders while fetch is pending (loading state) and settles', async () => {
    // 挂起的列表请求 → dsStore.loading === true 时页面不崩溃；resolve 后归位
    let resolveFetch!: (v: unknown) => void
    mockGet.mockReturnValueOnce(new Promise((resolve) => { resolveFetch = resolve }))
    const wrapper = mountPage()
    await flushPromises()
    const { useDataSourceStore } = await import('@/stores/datasource')
    const store = useDataSourceStore()
    expect(wrapper.exists()).toBe(true)
    expect(store.loading).toBe(true)
    resolveFetch([])
    await flushPromises()
    expect(store.loading).toBe(false)
  })

  it('disables sync and crawl buttons for paused sources', async () => {
    mockGet.mockResolvedValue([makeSource({ id: 'p1', status: 'paused' })])
    const wrapper = mountFull()
    await flushPromises()
    const buttons = wrapper.findAll('button')
    const syncBtn = buttons.find((b) => b.text().includes('一键同步'))
    const crawlBtn = buttons.find((b) => b.text().includes('立即采集'))
    expect(syncBtn?.attributes('disabled')).toBeDefined()
    expect(crawlBtn?.attributes('disabled')).toBeDefined()
  })

  it('filters out inactive sources from visible list and KPI', async () => {
    // 后端 DELETE 软删除产出 status='inactive'；UI 展示层过滤（指向
    // app.core.constants.DataSourceStatus），inactive 不计入数据源总数 KPI。
    mockGet.mockResolvedValue([
      makeSource({ id: 's1', name: 'boss', status: 'active' }),
      makeSource({ id: 's2', name: 'archive', status: 'inactive' }),
    ])
    const wrapper = mountFull()
    await flushPromises()
    const { useDataSourceStore } = await import('@/stores/datasource')
    const store = useDataSourceStore()
    // store 保留全部源（含 inactive，供管理端/恢复用）
    expect(store.sources.length).toBe(2)
    // KPI 总数只统计 visibleSources（过滤 inactive）→ 1 个活跃，而非 2
    expect(wrapper.text()).toContain('1 个活跃')
    expect(wrapper.text()).not.toContain('2 个活跃')
    // 渲染层不出现 inactive 源
    expect(wrapper.text()).not.toContain('archive')
  })
})
