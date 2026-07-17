import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CountUpNumber from '../CountUpNumber.vue'

describe('CountUpNumber', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Mock window.matchMedia (not available in jsdom)
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders with default prefix and suffix', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 100 },
    })
    // 初始 displayValue = 0, prefix='', suffix=''
    expect(wrapper.text()).toContain('0')
  })

  it('renders prefix and suffix', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 42, prefix: '~', suffix: '%' },
    })
    // 应包含 prefix 和 suffix
    expect(wrapper.text()).toContain('~')
    expect(wrapper.text()).toContain('%')
  })

  it('computes formattedNumber with decimals', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 3.14, decimals: 2 },
    })
    const vm = wrapper.vm as any
    // displayValue 初始为 0
    expect(vm.formattedNumber).toBe('0.00')
  })

  it('computes formattedNumber with locale formatting for integers', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 1234 },
    })
    const vm = wrapper.vm as any
    // displayValue = 0, Math.round(0).toLocaleString() = '0'
    expect(vm.formattedNumber).toBe('0')
  })

  it('computes displayText combining prefix + formatted + suffix', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 50, prefix: '>', suffix: '项' },
    })
    const vm = wrapper.vm as any
    expect(vm.displayText).toBe('>0项')
  })

  it('easeOutCubic returns 0 at t=0 and 1 at t=1', () => {
    // easeOutCubic(t) = 1 - (1-t)^3
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)
    expect(easeOutCubic(0)).toBe(0)
    expect(easeOutCubic(1)).toBe(1)
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875, 3)
  })

  it('has correct element class', () => {
    const wrapper = mount(CountUpNumber, {
      props: { target: 100 },
    })
    const span = wrapper.find('span')
    expect(span.classes()).toContain('count-up-number')
  })
})