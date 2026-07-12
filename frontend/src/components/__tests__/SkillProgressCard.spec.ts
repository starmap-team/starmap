import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SkillProgressCard from '../SkillProgressCard.vue'

describe('SkillProgressCard', () => {
  const baseSkill = {
    skill: 'Python',
    status: 'not_started' as const,
    progress_pct: 0,
    estimated_hours: 40,
    prerequisites: [],
    current_level: 0,
    target_level: 3,
  }

  it('renders skill name', () => {
    const wrapper = mount(SkillProgressCard, {
      props: { skill: baseSkill },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    expect(wrapper.text()).toContain('Python')
  })

  it('maps status to correct label', () => {
    const cases = [
      { status: 'not_started', label: '未开始' },
      { status: 'in_progress', label: '学习中' },
      { status: 'mastered', label: '已掌握' },
    ] as const

    for (const { status, label } of cases) {
      const wrapper = mount(SkillProgressCard, {
        props: { skill: { ...baseSkill, status } },
        global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
      })
      expect(wrapper.text()).toContain(label)
    }
  })

  it('computes progressColor based on progress_pct', () => {
    // >= 80 → success, >= 40 → warning, else → primary
    const wrapper80 = mount(SkillProgressCard, {
      props: { skill: { ...baseSkill, progress_pct: 80 } },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    const vm80 = wrapper80.vm as any
    expect(vm80.progressColor).toContain('success')

    const wrapper50 = mount(SkillProgressCard, {
      props: { skill: { ...baseSkill, progress_pct: 50 } },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    const vm50 = wrapper50.vm as any
    expect(vm50.progressColor).toContain('warning')

    const wrapper10 = mount(SkillProgressCard, {
      props: { skill: { ...baseSkill, progress_pct: 10 } },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    const vm10 = wrapper10.vm as any
    expect(vm10.progressColor).toContain('primary')
  })

  it('computes levelDots correctly', () => {
    const wrapper = mount(SkillProgressCard, {
      props: { skill: { ...baseSkill, current_level: 2, target_level: 4 } },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    const vm = wrapper.vm as any
    const dots = vm.levelDots
    expect(dots).toHaveLength(5)
    expect(dots[0].active).toBe(true)   // i=1 <= 2
    expect(dots[1].active).toBe(true)   // i=2 <= 2
    expect(dots[2].active).toBe(false)  // i=3 > 2
    expect(dots[0].target).toBe(true)   // i=1 <= 4
    expect(dots[4].target).toBe(false)  // i=5 > 4
  })

  it('emits update-status event', async () => {
    const wrapper = mount(SkillProgressCard, {
      props: { skill: { ...baseSkill, status: 'in_progress' } },
      global: { stubs: { ElCard: { template: '<div><slot/></div>' }, ElTag: { template: '<span><slot/></span>' } } },
    })
    const vm = wrapper.vm as any
    vm.handleStatusChange('mastered')
    expect(wrapper.emitted('update-status')).toBeTruthy()
    expect(wrapper.emitted('update-status')![0]).toEqual(['Python', 'mastered'])
  })
})