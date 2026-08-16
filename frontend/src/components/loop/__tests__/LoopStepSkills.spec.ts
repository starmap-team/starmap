/**
 * LoopStepSkills.spec — * Verifies D-05 口径拆解行（技能数 + 信任度均值）+ D-06 model_used 透传
 * （云端 vs 本地 fallback 文案差异）+ 空 data 不崩.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import LoopStepSkills from '../LoopStepSkills.vue'

function makeStep(data: Record<string, unknown>, status: 'success' | 'failed' | 'running' = 'success') {
  return { step: 2, name: '技能提取', status, data } as never
}

describe('LoopStepSkills.vue', () => {
  it('renders skill_count and skill_confidence_avg from data (D-05)', () => {
    const wrapper = mount(LoopStepSkills, {
      props: {
        step: makeStep({
          skill_count: 8,
          skill_confidence_avg: 0.86,
          skills: [{ skill: 'Python', is_new: true, confidence: 0.92 }],
        }),
        celebrated: false,
        skills: [{ skill: 'Python', is_new: true, confidence: 0.92 }],
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('技能数: 8')
    expect(html).toContain('信任度均值: 86%')
  })

  it('shows cloud model tag for non-fallback model_used (D-06)', () => {
    const wrapper = mount(LoopStepSkills, {
      props: {
        step: makeStep({
          model_used: 'spark-x',
          skill_count: 5,
          skill_confidence_avg: 0.9,
          skills: [],
        }),
        celebrated: false,
        skills: [],
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('模型: spark-x')
    // cloud model — no local fallback hint
    expect(html).not.toContain('本地，预计较慢')
  })

  it('shows local fallback hint when model_used contains -fallback (D-06)', () => {
    const wrapper = mount(LoopStepSkills, {
      props: {
        step: makeStep({
          model_used: 'qwen-fallback',
          skill_count: 5,
          skill_confidence_avg: 0.9,
          skills: [],
        }),
        celebrated: false,
        skills: [],
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('模型: qwen-fallback')
    expect(html).toContain('本地，预计较慢')
  })

  it('does not crash when data has no model_used (honest empty state)', () => {
    const wrapper = mount(LoopStepSkills, {
      props: {
        step: makeStep({ skills: [] }, 'success'),
        celebrated: false,
        skills: [],
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    // No model tag rendered when model_used absent
    expect(html).not.toContain('模型:')
    // Falls back to 技能数: 0 since no skill_count either
    expect(html).toContain('技能数: 0')
  })
})
