/**
 * DataDashboard.vue smoke + behavior tests.
 * Mocks @/api/request so the dashboard store's real logic runs without backend calls.
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
  useRoute: () => ({ params: {}, query: {}, path: '/dashboard', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import DataDashboard from '../DataDashboard.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(DataDashboard, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        'el-card': true,
        'el-button': true,
        'el-tag': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('DataDashboard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({
      data: [],
      items: [],
      stages: [],
      total_positions: 0,
      total_skills: 0,
      total_records: 0,
    })
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('calls overview endpoint via the public /dashboard prefix', async () => {
    const { useDashboardStore } = await import('@/stores/dashboard')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()

    await store.fetchOverview()

    expect(mockGet).toHaveBeenCalledWith('/dashboard/overview')
    expect(mockGet).not.toHaveBeenCalledWith('/admin/dashboard/overview')
  })

  it('calls trends endpoint with correct path', async () => {
    const { useDashboardStore } = await import('@/stores/dashboard')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()

    await store.fetchTrends()

    expect(mockGet).toHaveBeenCalledWith('/dashboard/trends')
  })

  it('calls distribution endpoint with correct path', async () => {
    const { useDashboardStore } = await import('@/stores/dashboard')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()

    await store.fetchDistribution()

    expect(mockGet).toHaveBeenCalledWith('/dashboard/distribution')
  })

  it('propagates backend detail on HTTP error in overview', async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { detail: '仪表盘数据不可用' } },
    })
    const { useDashboardStore } = await import('@/stores/dashboard')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()

    await store.fetchOverview()

    // fix: dashboard.ts error handler extracts response.data.detail
    expect(store.error).toBe('仪表盘数据不可用')
  })

  it('falls back to axios message when no backend detail', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useDashboardStore } = await import('@/stores/dashboard')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()

    await store.fetchOverview()

    expect(store.error).toBe('Network Error')
  })

  it('loads data on mount', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalled()
  })
})