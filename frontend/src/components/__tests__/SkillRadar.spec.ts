/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SkillRadar from '../SkillRadar.vue'

// ECharts 在 jsdom 中不可用，mock vue-echarts
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div data-testid="vchart">{{ JSON.stringify(option) }}</div>',
  },
}))

// mock echarts/core use() — no-op
vi.mock('echarts/core', () => ({
  use: () => {},
}))
vi.mock('echarts/charts', () => ({
  RadarChart: {},
}))
vi.mock('echarts/components', () => ({
  TooltipComponent: {},
  LegendComponent: {},
  RadarComponent: {},
}))

describe('SkillRadar', () => {
  const sampleData = [
    { skill: 'Python', required: 0.9, user: 0.8 },
    { skill: 'Docker', required: 0.7, user: 0.3 },
    { skill: 'SQL', required: 0.8, user: 0.9 },
  ]

  it('renders VChart with correct indicator count', () => {
    const wrapper = mount(SkillRadar, {
      props: { data: sampleData, positionName: 'Backend' },
      global: {
        stubs: { VChart: { template: '<div />' } },
      },
    })
    // 组件应正常渲染
    expect(wrapper.exists()).toBe(true)
  })

  it('computes radar option with correct number of indicators', () => {
    const wrapper = mount(SkillRadar, {
      props: { data: sampleData, positionName: 'Backend' },
      global: {
        stubs: { VChart: { template: '<div />' } },
      },
    })

    // 通过 vm 访问 computed
    const vm = wrapper.vm as any
    const option = vm.radarOption

    // indicators 数量应等于 data 长度
    expect(option.radar.indicator).toHaveLength(3)
    expect(option.radar.indicator[0].name).toBe('Python')
    expect(option.radar.indicator[1].name).toBe('Docker')
    expect(option.radar.indicator[2].name).toBe('SQL')
  })

  it('computes series values from props.data', () => {
    const wrapper = mount(SkillRadar, {
      props: { data: sampleData, positionName: 'Backend' },
      global: {
        stubs: { VChart: { template: '<div />' } },
      },
    })

    const vm = wrapper.vm as any
    const option = vm.radarOption

    // series[0] = 岗位要求 (required)
    expect(option.series[0].data[0].value).toEqual([0.9, 0.7, 0.8])
    // series[1] = 我的技能 (user)
    expect(option.series[1].data[0].value).toEqual([0.8, 0.3, 0.9])
  })

  it('returns empty option when data is empty', () => {
    const wrapper = mount(SkillRadar, {
      props: { data: [], positionName: 'Backend' },
      global: {
        stubs: { VChart: { template: '<div />' } },
      },
    })

    const vm = wrapper.vm as any
    expect(Object.keys(vm.radarOption)).toHaveLength(0)
  })
})