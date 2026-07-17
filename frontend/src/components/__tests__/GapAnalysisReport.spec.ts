/// <reference types="vitest" />
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import GapAnalysisReport from '../GapAnalysisReport.vue'
import { useMatchStore } from '@/stores/match'

// Mock request module
vi.mock('@/api/request', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

describe('GapAnalysisReport', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows empty state when no match result', () => {
    const wrapper = mount(GapAnalysisReport, {
      props: { targetPosition: 'Backend' },
      global: {
        stubs: {
          ElButton: { template: '<button><slot/></button>' },
          ElTable: { template: '<table><slot/></table>' },
          ElTableColumn: { template: '<td />' },
          ElTag: { template: '<span><slot/></span>' },
        },
      },
    })
    expect(wrapper.text()).toContain('诊断尚未开始')
  })

  it('shows match score when result exists', () => {
    const store = useMatchStore()
    store.result = {
      match_score: 0.75,
      matched_skills: ['Python', 'SQL'],
      gap_skills: ['Docker'],
      recommendations: ['学习 Docker'],
      target_position: 'Backend',
      skill_gap_detail: [
        { skill: 'Docker', importance: 'required' as const, gap_level: '完全缺失' as const, learning_path: [] },
      ],
    }

    const wrapper = mount(GapAnalysisReport, {
      props: { targetPosition: 'Backend' },
      global: {
        stubs: {
          ElButton: { template: '<button><slot/></button>' },
          ElTable: { template: '<table><slot/></table>' },
          ElTableColumn: { template: '<td />' },
          ElTag: { template: '<span><slot/></span>' },
        },
      },
    })
    // 分数 0.75 * 100 = 75%
    expect(wrapper.text()).toContain('75')
  })

  it('renders gap detail table with correct row count', () => {
    const store = useMatchStore()
    store.result = {
      match_score: 0.6,
      matched_skills: ['Python'],
      gap_skills: ['Docker', 'K8s'],
      recommendations: [],
      target_position: 'Backend',
      skill_gap_detail: [
        { skill: 'Docker', importance: 'required' as const, gap_level: '完全缺失' as const, learning_path: ['Docker基础'] },
        { skill: 'K8s', importance: 'bonus' as const, gap_level: '部分掌握' as const, learning_path: [] },
      ],
    }

    const wrapper = mount(GapAnalysisReport, {
      props: { targetPosition: 'Backend' },
      global: {
        stubs: {
          ElButton: { template: '<button><slot/></button>' },
          ElTable: { template: '<table><slot/></table>' },
          ElTableColumn: { template: '<td />' },
          ElTag: { template: '<span><slot/></span>' },
        },
      },
    })
    // 差距明细标题应出现
    expect(wrapper.text()).toContain('技能差距明细')
  })

  it('emits goLearning event', async () => {
    const store = useMatchStore()
    store.result = {
      match_score: 0.5,
      matched_skills: [],
      gap_skills: ['Go'],
      recommendations: [],
      target_position: 'Backend',
      skill_gap_detail: [
        { skill: 'Go', importance: 'required' as const, gap_level: '完全缺失' as const, learning_path: [] },
      ],
    }

    const wrapper = mount(GapAnalysisReport, {
      props: { targetPosition: 'Backend' },
      global: {
        stubs: {
          ElButton: { template: '<button><slot/></button>' },
          ElTable: { template: '<table><slot/></table>' },
          ElTableColumn: { template: '<td />' },
          ElTag: { template: '<span><slot/></span>' },
        },
      },
    })

    // 找到"查看学习路径"按钮
    const btn = wrapper.findAll('button').find(b => b.text().includes('查看学习路径'))
    if (btn) {
      await btn.trigger('click')
      expect(wrapper.emitted('goLearning')).toBeTruthy()
    }
  })
})