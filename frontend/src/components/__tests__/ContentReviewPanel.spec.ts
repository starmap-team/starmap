/**
 * ContentReviewPanel 单元测试
 *
 * 覆盖：industry 空值时显示「未分类」warning tag，让审核员能识别需补行业的岗位。
 * 镜像 PositionList.vue:294-303 的「未分类」chip 行为（Per PRD US-001 C4）。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock the review store so we can inject items without backend roundtrip
const mockItems = vi.hoisted(() => ({ value: [] as Array<Record<string, unknown>> }))
const mockStats = vi.hoisted(() => ({ value: {} as Record<string, number> }))

vi.mock('@/stores/review', () => ({
  useReviewStore: () => ({
    items: mockItems.value,
    stats: mockStats.value,
    fetchItems: vi.fn().mockResolvedValue(undefined),
    fetchStats: vi.fn().mockResolvedValue(undefined),
    approve: vi.fn().mockResolvedValue(undefined),
    reject: vi.fn().mockResolvedValue(undefined),
    removeLocal: vi.fn(),
  }),
}))

import ContentReviewPanel from '../ContentReviewPanel.vue'

const globalStubs = {
  'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
  'el-table': {
    template: '<div class="el-table-stub"><slot /></div>',
  },
  'el-table-column': {
    template: '<div class="el-table-col-stub"><slot :row="currentRow" /></div>',
    data() {
      return { currentRow: mockItems.value[0] || {} }
    },
  },
  'el-tag': {
    props: ['type', 'effect', 'size'],
    template:
      '<span class="el-tag-stub" :class="type ? `el-tag--${type}` : `el-tag--info`"><slot /></span>',
  },
  'el-button': { template: '<button class="el-btn-stub"><slot /></button>' },
  'el-input': { template: '<input class="el-input-stub" />' },
  'el-select': { template: '<div class="el-select-stub"><slot /></div>' },
  'el-option': { template: '<div class="el-option-stub"><slot /></div>' },
  'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-pagination': { template: '<div class="el-pagination-stub" />' },
  'el-checkbox': { template: '<input type="checkbox" class="el-cb-stub" />' },
  'el-checkbox-group': { template: '<div class="el-cbg-stub"><slot /></div>' },
  'el-dialog': { template: '<div class="el-dialog-stub"><slot /></div>' },
}

function makeRow(overrides: Record<string, unknown> = {}) {
  return {
    entity_type: 'position',
    entity_id: 'p1',
    name: 'Senior Engineer',
    name_cn: '高级工程师',
    industry: '',
    review_status: 'pending_review',
    created_by: 'system:extract',
    created_at: '2026-08-16T00:00:00Z',
    ...overrides,
  }
}

function mountPanel(rows: Array<Record<string, unknown>>) {
  mockItems.value = rows
  return mount(ContentReviewPanel, {
    global: {
      stubs: globalStubs,
      plugins: [createPinia()],
    },
  })
}

describe('ContentReviewPanel — industry fallback (PRD US-001 C4)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockItems.value = []
    mockStats.value = {}
  })

  it('industry 为空字符串时显示「未分类」warning tag', () => {
    const wrapper = mountPanel([makeRow({ industry: '' })])
    const tag = wrapper.find('.industry-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('未分类')
    expect(tag.classes()).toContain('el-tag--warning')
  })

  it('industry 为 null 时同样显示「未分类」tag', () => {
    const wrapper = mountPanel([makeRow({ industry: null })])
    const tag = wrapper.find('.industry-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('未分类')
  })

  it('industry 有值时显示真实行业名（info 类型），不显示「未分类」', () => {
    const wrapper = mountPanel([makeRow({ industry: '互联网/IT' })])
    const tag = wrapper.find('.industry-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('互联网/IT')
    expect(tag.text()).not.toBe('未分类')
    expect(tag.classes()).toContain('el-tag--info')
  })
})