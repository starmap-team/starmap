import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DataQualityGauge from '../DataQualityGauge.vue'

// Mock ECharts
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div />' },
}))
vi.mock('echarts/core', () => ({ use: () => {} }))
vi.mock('echarts/charts', () => ({ GaugeChart: {} }))
vi.mock('echarts/components', () => ({ TooltipComponent: {}, GraphicComponent: {} }))

describe('DataQualityGauge', () => {
  it('computes gauge option with correct score value', () => {
    const wrapper = mount(DataQualityGauge, {
      props: { score: 0.85, label: '数据质量', trend: 'up' },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    const vm = wrapper.vm as any
    const option = vm.gaugeOption

    // score 为 0-1 比例，组件内部乘以 100 转为百分值
    expect(option.series[0].data[0].value).toBe(85)
  })

  it('rounds score to integer', () => {
    const wrapper = mount(DataQualityGauge, {
      props: { score: 0.727 },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    const vm = wrapper.vm as any
    // 0.727 * 100 = 72.7，Math.round 后为 73
    expect(vm.gaugeOption.series[0].data[0].value).toBe(73)
  })

  it('uses default label when not provided', () => {
    const wrapper = mount(DataQualityGauge, {
      props: { score: 50 },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    // 默认 label = '数据质量'
    expect(wrapper.props('label')).toBe('数据质量')
  })

  it('uses default trend when not provided', () => {
    const wrapper = mount(DataQualityGauge, {
      props: { score: 50 },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    expect(wrapper.props('trend')).toBe('stable')
  })

  it('gauge has correct axis color zones', () => {
    const wrapper = mount(DataQualityGauge, {
      props: { score: 90 },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    const vm = wrapper.vm as any
    const axisLine = vm.gaugeOption.series[0].axisLine
    // 3 color zones: [0.6, danger], [0.8, warning], [1, success]
    expect(axisLine.lineStyle.color).toHaveLength(3)
    expect(axisLine.lineStyle.color[0][0]).toBe(0.6)
    expect(axisLine.lineStyle.color[1][0]).toBe(0.8)
    expect(axisLine.lineStyle.color[2][0]).toBe(1)
  })
})