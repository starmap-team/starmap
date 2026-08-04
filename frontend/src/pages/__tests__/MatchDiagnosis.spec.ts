/**
 * MatchDiagnosis.vue smoke test.
 */
import { describe, it, expect, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/match', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import MatchDiagnosis from '../MatchDiagnosis.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(MatchDiagnosis, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        'el-tabs': true,
        'el-tab-pane': true,
        'el-input': true,
        'el-button': true,
        'el-card': true,
      },
    },
  })
}

describe('MatchDiagnosis.vue', () => {
  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })
})
