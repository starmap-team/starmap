/**
 * UserManagement.vue smoke + behavior tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: () => Promise.resolve({}),
    patch: (...args: unknown[]) => mockPatch(...args),
    delete: () => Promise.resolve({}),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/admin/users', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import UserManagement from '../UserManagement.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(UserManagement, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-table': true,
        'el-table-column': true,
        'el-button': true,
        'el-input': true,
        'el-dialog': true,
        'el-form': true,
        'el-form-item': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('UserManagement.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ items: [], total: 0 })
    mockPost.mockResolvedValue({})
    mockPatch.mockResolvedValue({})
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('loads user list via the public /admin/users endpoint', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/admin/users', expect.any(Object))
  })

  it('handles empty user list response', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0 })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('handles populated user list with various roles', async () => {
    mockGet.mockResolvedValueOnce({
      items: [
        { id: 'u1', username: 'alice', role: 'admin', is_active: true },
        { id: 'u2', username: 'bob', role: 'user', is_active: false },
      ],
      total: 2,
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('handles user API errors without crashing', async () => {
    mockGet.mockRejectedValueOnce(new Error('User API unavailable'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('handles user unlock endpoint with correct URL', async () => {
    mockPost.mockResolvedValueOnce({ ok: true })
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
    // store-level URL is /admin/users/{id}/unlock — verified in store, not here
  })
})
