/**
 * LearningCenter.vue smoke + behavior tests.
 * Mocks @/api/request so the learning store's real logic runs without backend calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing page/store ──
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
  useRoute: () => ({ params: {}, query: {}, path: '/learning', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import LearningCenter from '../LearningCenter.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(LearningCenter, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-tabs': true,
        'el-tab-pane': true,
        'el-card': true,
        'el-button': true,
        'v-chart': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('LearningCenter.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ plans: [], items: [], recommendations: [] })
    mockPost.mockResolvedValue({ plan_id: 'plan-1' })
    mockPut.mockResolvedValue({})
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('loads plans list via the public /learning/plans endpoint', async () => {
    const { useLearningPlanStore } = await import('@/stores/learningPlan')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningPlanStore()

    await store.fetchPlans()

    expect(mockGet).toHaveBeenCalledWith('/learning/plans')
    expect(mockGet).not.toHaveBeenCalledWith('/admin/learning/plans')
  })

  it('progress update PUTs to the public endpoint', async () => {
    const { useLearningPlanStore } = await import('@/stores/learningPlan')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningPlanStore()

    await store.updateProgress('plan-1', 'Python', 'in_progress')

    expect(mockPut).toHaveBeenCalledWith(
      '/learning/plan/plan-1/progress',
      expect.objectContaining({ skill_name: 'Python', status: 'in_progress' }),
    )
    expect(mockPut).not.toHaveBeenCalledWith(
      '/admin/learning/plan/plan-1/progress',
      expect.any(Object),
    )
  })

  it('propagates backend detail on HTTP error', async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { detail: '学习计划不存在' } },
    })
    const { useLearningPlanStore } = await import('@/stores/learningPlan')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningPlanStore()

    await expect(store.fetchPlan('bad-id')).rejects.toBeDefined()
    expect(store.planError).toContain('学习计划不存在')
  })

  it('falls back to axios message when no backend detail', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useLearningPlanStore } = await import('@/stores/learningPlan')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningPlanStore()

    await expect(store.fetchPlan('any-id')).rejects.toBeDefined()
    expect(store.planError).toContain('Network Error')
  })

  it('loads recommendations via /learning/recommendations', async () => {
    const { useLearningRecommendationStore } = await import('@/stores/learningRecommendation')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningRecommendationStore()

    await store.fetchRecommendations()

    // P1 fix (functional-review 2026-08-13): fetchRecommendations 现带 params 参数
    expect(mockGet).toHaveBeenCalledWith('/learning/recommendations', { params: {} })
  })

  it('passes plan_id to recommendations for personalization', async () => {
    const { useLearningRecommendationStore } = await import('@/stores/learningRecommendation')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLearningRecommendationStore()

    await store.fetchRecommendations('plan-abc', '后端工程师')

    expect(mockGet).toHaveBeenCalledWith('/learning/recommendations', {
      params: { plan_id: 'plan-abc', position: '后端工程师' },
    })
  })
})