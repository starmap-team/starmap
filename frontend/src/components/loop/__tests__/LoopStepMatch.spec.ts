/**
 * LoopStepMatch.spec — Phase 07-02 T9
 * Verifies D-05 M5 分数拆解行（required_avg / bonus_avg / 权重 / inflated）.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import LoopStepMatch from '../LoopStepMatch.vue'

function makeStep(data: Record<string, unknown>, status: 'success' | 'failed' | 'running' = 'success') {
  return { step: 4, name: '匹配诊断', status, data } as never
}

describe('LoopStepMatch.vue', () => {
  it('renders score_breakdown row with required_avg / bonus_avg / weights (D-05)', () => {
    const wrapper = mount(LoopStepMatch, {
      props: {
        step: makeStep({
          match_score: 0.72,
          score_breakdown: {
            required_avg: 0.8,
            bonus_avg: 0.5,
            weight_required: 0.7,
            weight_bonus: 0.3,
            inflated: false,
          },
        }),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('必备均值 80%')
    expect(html).toContain('加分均值 50%')
    expect(html).toContain('必备权重 70%')
    expect(html).toContain('加分权重 30%')
    // inflated=false → no CII warning tag
    expect(html).not.toContain('CII 通胀修正')
  })

  it('shows CII warning when inflated=true (M5 D-01)', () => {
    const wrapper = mount(LoopStepMatch, {
      props: {
        step: makeStep({
          match_score: 0.6,
          score_breakdown: {
            required_avg: 0.65,
            bonus_avg: 0.4,
            weight_required: 0.7,
            weight_bonus: 0.3,
            inflated: true,
          },
        }),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('CII 通胀修正已触发')
  })

  it('does not render breakdown row when data lacks score_breakdown', () => {
    const wrapper = mount(LoopStepMatch, {
      props: {
        step: makeStep({ match_score: 0.5 }),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    // No breakdown row when score_breakdown absent
    expect(html).not.toContain('必备均值')
    expect(html).not.toContain('加分均值')
  })
})
