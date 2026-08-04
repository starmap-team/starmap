/**
 * AuditLog.vue smoke + behavior tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const mockGet = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: () => Promise.resolve({}),
    put: () => Promise.resolve({}),
    patch: () => Promise.resolve({}),
    delete: () => Promise.resolve({}),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/admin/audit', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import AuditLog from '../AuditLog.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(AuditLog, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-table': true,
        'el-table-column': true,
        'el-pagination': true,
        'el-input': true,
        'el-select': true,
        'el-option': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('AuditLog.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ items: [], total: 0 })
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('loads audit events via the public /admin/audit-events endpoint', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/admin/audit-events', expect.any(Object))
  })

  it('handles empty audit events response', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0 })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('handles audit API errors without crashing', async () => {
    mockGet.mockRejectedValueOnce(new Error('Audit API unavailable'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('handles large audit response gracefully', async () => {
    const items = Array.from({ length: 100 }, (_, i) => ({
      id: i,
      event_type: 'login',
      actor: `user${i}`,
      action: 'login',
      timestamp: '2026-07-26T10:00:00',
    }))
    mockGet.mockResolvedValueOnce({ items, total: 100 })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })
})
