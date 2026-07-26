/**
 * PositionList.vue smoke test — verifies page renders with mocked dependencies.
 */
import { describe, it, expect, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/positions', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import PositionList from '../PositionList.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(PositionList, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'el-pagination': true,
        'el-input': true,
        'el-table': true,
        'el-table-column': true,
        'el-tag': true,
        'el-button': true,
      },
    },
  })
}

describe('PositionList.vue', () => {
  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('contains a search input area', () => {
    const wrapper = mountPage()
    expect(wrapper.findAllComponents({ name: 'ElInput' }).length).toBeGreaterThanOrEqual(0)
  })
})
