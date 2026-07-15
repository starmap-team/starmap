import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DataSourceCard from '../DataSourceCard.vue'
import type { DataSourceInfo } from '../DataSourceCard.vue'

// Mock ECharts
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div />' },
}))
vi.mock('echarts/core', () => ({ use: () => {} }))
vi.mock('echarts/charts', () => ({ GaugeChart: {} }))
vi.mock('echarts/components', () => ({ TooltipComponent: {} }))

describe('DataSourceCard', () => {
  const baseSource: DataSourceInfo = {
    name: '拉勾网',
    source_type: 'crawler',
    authority_score: 0.85,
    status: 'active',
    last_crawl_at: new Date().toISOString(),
    total_records: 1500,
    valid_records: 1200,
    duplicate_rate: 0.12,
    avg_quality_score: 0.78,
  }

  it('renders source name', () => {
    const wrapper = mount(DataSourceCard, {
      props: { source: baseSource },
      global: {
        stubs: {
          ElCard: { template: '<div><slot/></div>' },
          ElTag: { template: '<span><slot/></span>' },
          VChart: { template: '<div />' },
        },
      },
    })
    expect(wrapper.text()).toContain('拉勾网')
  })

  it('maps status to correct badge', () => {
    const cases = [
      { status: 'active' as const, label: '运行中' },
      { status: 'paused' as const, label: '已暂停' },
      { status: 'error' as const, label: '异常' },
    ]

    for (const { status, label } of cases) {
      const wrapper = mount(DataSourceCard, {
        props: { source: { ...baseSource, status } },
        global: {
          stubs: {
            ElCard: { template: '<div><slot/></div>' },
            ElTag: { template: '<span><slot/></span>' },
            VChart: { template: '<div />' },
          },
        },
      })
      expect(wrapper.text()).toContain(label)
    }
  })

  it('computes sourceTypeLabel correctly', () => {
    const typeMap: Record<string, string> = { crawler: '爬虫', api: 'API', manual: '手动', import: '导入' }

    for (const [type, label] of Object.entries(typeMap)) {
      const wrapper = mount(DataSourceCard, {
        props: { source: { ...baseSource, source_type: type as any } },
        global: {
          stubs: {
            ElCard: { template: '<div><slot/></div>' },
            ElTag: { template: '<span><slot/></span>' },
            VChart: { template: '<div />' },
          },
        },
      })
      expect(wrapper.text()).toContain(label)
    }
  })

  it('formats large record counts', () => {
    const wrapper = mount(DataSourceCard, {
      props: { source: { ...baseSource, total_records: 25000 } },
      global: {
        stubs: {
          ElCard: { template: '<div><slot/></div>' },
          ElTag: { template: '<span><slot/></span>' },
          VChart: { template: '<div />' },
        },
      },
    })
    const vm = wrapper.vm as any
    expect(vm.formattedRecords).toBe('2.5万')
  })

  it('formats thousand-level record counts', () => {
    const wrapper = mount(DataSourceCard, {
      props: { source: { ...baseSource, total_records: 3500 } },
      global: {
        stubs: {
          ElCard: { template: '<div><slot/></div>' },
          ElTag: { template: '<span><slot/></span>' },
          VChart: { template: '<div />' },
        },
      },
    })
    const vm = wrapper.vm as any
    expect(vm.formattedRecords).toBe('3.5k')
  })

  it('computes gauge option with authority score', () => {
    const wrapper = mount(DataSourceCard, {
      props: { source: baseSource },
      global: {
        stubs: {
          ElCard: { template: '<div><slot/></div>' },
          ElTag: { template: '<span><slot/></span>' },
          VChart: { template: '<div />' },
        },
      },
    })
    const vm = wrapper.vm as any
    const option = vm.gaugeOption
    // authority_score 0.85 → 85
    expect(option.series[0].data[0].value).toBe(85)
  })
})