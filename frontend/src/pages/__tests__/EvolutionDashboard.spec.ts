/**
 * EvolutionDashboard.vue smoke + behavior tests.
 * Mocks @/api/request so the evolution store's real logic runs without backend calls.
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
        'el-card': true,
        'el-select': true,
        'el-option': true,
        MainLayout: { template: '<div><slot /></div>' },
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
})