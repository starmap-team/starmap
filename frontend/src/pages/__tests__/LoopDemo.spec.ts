/**
 * LoopDemo.vue smoke + behavior tests.
 * Mocks @/api/request so the loop store's real logic runs without backend calls.
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
  useRoute: () => ({ params: {}, query: {}, path: '/loop', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import LoopDemo from '../LoopDemo.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(LoopDemo, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-card': true,
        'el-button': true,
        'el-input': true,
        'el-textarea': true,
        MainLayout: { template: '<div><slot /></div>' },
        LoopTimeline: true,
        LoopStepInput: true,
        LoopStepSkills: true,
        LoopStepGraph: true,
        LoopStepMatch: true,
        LoopStepLearning: true,
        LoopRunLog: true,
      },
    },
  })
}

describe('LoopDemo.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // default: history empty, run returns success
    mockGet.mockResolvedValue({ items: [] })
    mockPost.mockResolvedValue({
      run_id: 'r-1',
      status: 'completed',
      steps: [
        { step: 1, name: 'jd_input', status: 'success', duration_seconds: 0.05 },
        { step: 2, name: 'skill_extract', status: 'success', duration_seconds: 1.2 },
        { step: 3, name: 'graph_sync', status: 'success', duration_seconds: 0.8 },
        { step: 4, name: 'match_diagnose', status: 'success', duration_seconds: 0.3 },
        { step: 5, name: 'learning_path', status: 'success', duration_seconds: 0.1 },
      ],
    })
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('triggers runLoop via the correct /loop/run endpoint', async () => {
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD 测试内容', 'Data Engineer')

    expect(mockPost).toHaveBeenCalledWith(
      '/loop/run',
      expect.objectContaining({ jd_text: 'JD 测试内容', target_position: 'Data Engineer' }),
      expect.any(Object),
    )
    expect(mockPost).not.toHaveBeenCalledWith(
      '/admin/loop/run',
      expect.any(Object),
      expect.any(Object),
    )
  })

  it('maps step duration_seconds → duration_ms in store state', async () => {
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD 内容', 'Engineer')

    // step 2 had duration_seconds: 1.2 → should become 1200 ms
    expect(store.currentRun?.steps[1].duration_ms).toBe(1200)
  })

  it('propagates backend detail on HTTP error', async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: 'JD 内容过短 (最少 50 字符)' } },
    })
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('短', 'Engineer')

    // fix: loop.ts error handler extracts response.data.detail (not axios default)
    expect(store.error).toBe('JD 内容过短 (最少 50 字符)')
  })

  it('falls back to axios message when no backend detail', async () => {
    mockPost.mockRejectedValueOnce(new Error('Network Error'))
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD 内容', 'Engineer')

    expect(store.error).toBe('Network Error')
  })

  it('loads history on mount via /loop/history', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/loop/history', expect.any(Object))
  })
})