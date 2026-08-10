/**
 * MatchTrustGuide.spec.ts — D-01/D-02 分数拆解 + 信任度降级文案测试。
 */
import { describe, it, expect } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import MatchTrustGuide from '../MatchTrustGuide.vue'

function mount(overrides: Record<string, unknown> = {}) {
  return shallowMount(MatchTrustGuide, {
    props: {
      matchScore: 0.74,
      trustScore: 0.8,
      ...overrides,
    },
  })
}

describe('MatchTrustGuide.vue', () => {
  it('D-01: 渲染分数拆解（必备均值×权重 + 加分均值×权重 + 公式）', () => {
    const wrapper = mount({
      scoreBreakdown: { required_avg: 0.82, bonus_avg: 0.55, weight_required: 0.7, weight_bonus: 0.3, inflated: false },
    })
    const text = wrapper.text()
    expect(text).toContain('分数构成')
    expect(text).toContain('必备技能均值')
    expect(text).toContain('82%')
    expect(text).toContain('55%')
    expect(text).toContain('× 0.7')
    expect(text).toContain('× 0.3')
    expect(text).toContain('匹配度 = 必备均值 × 0.7 + 加分均值 × 0.3')
  })

  it('D-01: inflated=true 时显示通胀修正提示', () => {
    const wrapper = mount({
      scoreBreakdown: { required_avg: 0.7, bonus_avg: 0.5, weight_required: 0.7, weight_bonus: 0.3, inflated: true },
    })
    expect(wrapper.text()).toContain('岗位要求存在通胀迹象，边缘必备项已按加分项处理')
  })

  it('D-01: 无 score_breakdown 时不渲染拆解区', () => {
    const wrapper = mount({ scoreBreakdown: null })
    expect(wrapper.text()).not.toContain('分数构成')
  })

  it('D-02: trustScore=null 时显示降级文案而非裸「—」', () => {
    const wrapper = mount({ trustScore: null })
    expect(wrapper.text()).toContain('信任度暂不可用（图谱服务未响应）')
  })

  it('D-02: trustScore 有值时显示百分比且无降级文案', () => {
    const wrapper = mount({ trustScore: 0.8 })
    const text = wrapper.text()
    expect(text).toContain('80%')
    expect(text).not.toContain('信任度暂不可用')
  })
})
