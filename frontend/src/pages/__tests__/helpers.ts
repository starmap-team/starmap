/**
 * Page test helpers — unified mount wrapper for smoke tests.
 */
import { mount, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

/** Default stubs for all page smoke tests */
const DEFAULT_STUBS: Record<string, boolean> = {
  'router-link': true,
  'router-view': true,
  // Graph/chart components that need Canvas/WebGL — stub them
  'v-chart': true,
  'graph-2d': true,
  'graph-3d': true,
}

/**
 * Mount a page component with Element Plus, Pinia, and router stubs.
 * Use this for most smoke tests.
 */
export function renderPage(
  component: any,
  options?: {
    shallow?: boolean
    stubs?: Record<string, any>
    props?: Record<string, any>
  },
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const mountFn = options?.shallow ? shallowMount : mount
  const mountOptions = {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: { ...DEFAULT_STUBS, ...options?.stubs },
    },
    props: options?.props,
  }

  return mountFn(component, mountOptions as any)
}

/**
 * Get a fresh Pinia instance (for tests that need to set store state before mount).
 */
export function freshPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}
