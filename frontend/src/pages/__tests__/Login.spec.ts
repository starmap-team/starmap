/**
 * Login.vue smoke test + 未认证时登录页不触发图谱请求/错误 toast 的回归防护
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/login', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))

// 未登录时不调用 fetchOverview(避免 401 噪音) — 回归防护:
// 若移除 userStore.isLoggedIn 守卫, 此测试会失败
const fetchOverviewMock = vi.fn()
vi.mock('@/stores/graph', () => ({
  useGraphStore: () => ({
    fetchOverview: fetchOverviewMock,
    visibleNodes: [], // useGraph3DData 依赖, 测试环境置空
    visibleEdges: [],
  }),
}))

import Login from '../Login.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(Login, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-form': true,
        'el-form-item': true,
        'el-input': true,
        'el-button': true,
        Graph3D: true,
      },
    },
  })
}

describe('Login.vue', () => {
  beforeEach(() => {
    fetchOverviewMock.mockReset()
    localStorage.clear()
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('未登录时不调用 fetchOverview(避免登录页 401 噪音 toast)', async () => {
    mountPage()
    await flushPromises()
    expect(fetchOverviewMock).not.toHaveBeenCalled()
  })
})
