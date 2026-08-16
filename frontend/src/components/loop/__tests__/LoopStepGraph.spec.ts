/**
 * LoopStepGraph.spec — * Verifies D-05 口径拆解行：nodes_written / edges_written (来自 graph_sync 既有契约).
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import LoopStepGraph from '../LoopStepGraph.vue'

function makeStep(data: Record<string, unknown>, status: 'success' | 'failed' | 'running' = 'success') {
  return { step: 3, name: '图谱更新', status, data } as never
}

describe('LoopStepGraph.vue', () => {
  it('renders nodes_written and edges_written from data (D-05)', () => {
    const wrapper = mount(LoopStepGraph, {
      props: {
        step: makeStep({ nodes_written: 12, edges_written: 7, synced: true }),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('新增节点: 12')
    expect(html).toContain('新增关系: 7')
  })

  it('falls back to nodes/edges alias and shows "—" when keys missing', () => {
    const wrapper = mount(LoopStepGraph, {
      props: {
        step: makeStep({ nodes: 4, edges: 0 }),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('新增节点: 4')
    expect(html).toContain('新增关系: 0')
  })

  it('shows "—" placeholders when data has no count fields', () => {
    const wrapper = mount(LoopStepGraph, {
      props: {
        step: makeStep({ synced: false, error: 'neo4j down' }, 'failed'),
        celebrated: false,
      },
      global: { plugins: [ElementPlus] },
    })
    const html = wrapper.html()
    expect(html).toContain('新增节点: —')
    expect(html).toContain('新增关系: —')
  })
})
