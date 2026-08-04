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