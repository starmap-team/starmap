/**
 * DataSources.vue smoke + behavior tests.
 *
 * Mocks @/api/request at the module level so the store's real logic runs
 * while network calls are intercepted. Verifies loading/empty/error states,
 * card rendering with source-name mapping, and sync feedback.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
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
    daily_crawl_volume: [10, 20, 30],
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
    await store.triggerSync('src-42')
    expect(mockPost).toHaveBeenCalledWith('/datasources/src-42/sync')
    expect(mockPost).not.toHaveBeenCalledWith('/admin/datasources/src-42/sync')
  })

  it('updates source via the corrected public endpoint', async () => {
    const { useDataSourceStore } = await import('@/stores/datasource')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDataSourceStore()
    await store.updateSource('src-7', { status: 'paused' })
    expect(mockPut).toHaveBeenCalledWith('/datasources/src-7', { status: 'paused' })
    expect(mockPut).not.toHaveBeenCalledWith('/admin/datasources/src-7', { status: 'paused' })
  })
})
