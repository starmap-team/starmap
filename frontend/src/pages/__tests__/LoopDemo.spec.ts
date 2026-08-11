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

  // ---- Phase 07-02 T10: 错误透传 + 重新开始新 run_id + 状态映射 ----

  it('preserves backend detail on 422 validation error (D-04 错误透传)', async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: 'JD 文本过短 (最少 50 字符)' } },
    })
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('短', 'Engineer')

    expect(store.error).toBe('JD 文本过短 (最少 50 字符)')
  })

  it('restarting run produces a new run_id (D-04 整轮重跑)', async () => {
    mockPost.mockResolvedValue({
      run_id: 'r-1',
      status: 'completed',
      steps: [{ step: 1, status: 'success', duration_seconds: 0.1 }],
    })
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD 内容', 'Engineer')
    const firstRunId = store.currentRun?.run_id

    // small delay so Date.now() ticks
    await new Promise(r => setTimeout(r, 5))
    mockPost.mockResolvedValue({
      run_id: 'r-2',
      status: 'completed',
      steps: [{ step: 1, status: 'success', duration_seconds: 0.1 }],
    })
    await store.runLoop('JD 内容', 'Engineer')
    const secondRunId = store.currentRun?.run_id

    expect(firstRunId).toBeTruthy()
    expect(secondRunId).toBeTruthy()
    expect(firstRunId).not.toBe(secondRunId)
  })

  it('maps backend step statuses to frontend (success / degraded / failed)', async () => {
    mockPost.mockResolvedValue({
      run_id: 'r-3',
      status: 'completed',
      steps: [
        { step: 1, name: 'jd_input', status: 'success', duration_seconds: 0.05 },
        { step: 2, name: 'skill_extract', status: 'success', duration_seconds: 1.2 },
        { step: 3, name: 'graph_sync', status: 'failed', duration_seconds: 0.3, error: 'neo4j down' },
        { step: 4, name: 'match_diagnose', status: 'success', duration_seconds: 0.3 },
        { step: 5, name: 'learning_path', status: 'success', duration_seconds: 0.1 },
      ],
    })
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD', 'Engineer')

    // step 3 should be failed; others success
    const step3 = store.currentRun?.steps[2]
    expect(step3?.status).toBe('failed')
    expect(step3?.error).toBe('neo4j down')
    const step1 = store.currentRun?.steps[0]
    expect(step1?.status).toBe('success')
  })

  it('falls back to axios message when backend has no detail (500/no-response)', async () => {
    mockPost.mockRejectedValueOnce(new Error('Network Error'))
    const { useLoopStore } = await import('@/stores/loop')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useLoopStore()

    await store.runLoop('JD 内容', 'Engineer')

    expect(store.error).toBe('Network Error')
    // currentRun.status should be marked partial (degraded) since run was interrupted
    expect(store.currentRun?.status).toBe('partial')
  })
})