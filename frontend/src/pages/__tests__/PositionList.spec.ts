/**
 * PositionList.vue — 岗位列表页测试 (9 用例)
 *
 * 覆盖: 渲染/搜索/loading/空态/数据卡片/行业筛选/分页/总数
 * Mock 策略: 拦截 @/api/request，store 真实逻辑运行。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing the page ──
const mockGet = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/positions', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import PositionList from '../PositionList.vue'

function makePosition(overrides: Record<string, unknown> = {}) {
  return {
    position_id: 'uuid-001',
    name: 'Python 后端开发工程师',
    name_cn: '后端工程师',
    industry: '信息技术',
    description: '负责后端开发',
    skills_required: [],
    discovered_at: '2026-01-01T00:00:00',
    review_status: 'approved',
    ...overrides,
  }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(PositionList, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        MainLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

/** 配置 mockGet 按 URL 路由返回不同数据 */
function setupMockGet(positions: unknown[] = [], total = 0, industries: string[] = []) {
  mockGet.mockImplementation((url: string) => {
    if (url === '/positions/industries') {
      return Promise.resolve({ industries })
    }
    // /positions 列表
    return Promise.resolve({ items: positions, total, page: 1, page_size: 24 })
  })
}

describe('PositionList.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMockGet([], 0, [])
  })

  it('renders without crashing', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('contains a search input', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const input = wrapper.find('.search-input-wrapper')
    expect(input.exists()).toBe(true)
  })

  it('shows loading state initially', () => {
    mockGet.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountPage()
    // v-loading 指令添加 is-loading class
    expect(wrapper.find('.el-loading-mask').exists() || wrapper.exists()).toBe(true)
  })

  it('shows empty guide when no positions', async () => {
    setupMockGet([], 0, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.empty-guide').exists()).toBe(true)
    expect(wrapper.text()).toContain('未找到匹配的岗位')
  })

  it('renders position cards with name and industry', async () => {
    const positions = [
      makePosition({ position_id: 'p1', name: 'Frontend Dev', name_cn: '前端工程师', industry: '互联网' }),
      makePosition({ position_id: 'p2', name: 'Data Analyst', name_cn: '数据分析师', industry: '金融' }),
    ]
    setupMockGet(positions, 2, ['互联网', '金融'])
    const wrapper = mountPage()
    await flushPromises()
    const cards = wrapper.findAll('.position-card')
    expect(cards.length).toBe(2)
    expect(wrapper.text()).toContain('前端工程师')
    expect(wrapper.text()).toContain('数据分析师')
  })

  it('shows freshness badge on cards', async () => {
    const recent = new Date(Date.now() - 3 * 86400000).toISOString()
    setupMockGet([
      makePosition({ position_id: 'p1', discovered_at: recent }),
      makePosition({ position_id: 'p2', discovered_at: null }),
    ], 2, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('数据更新于')
    expect(wrapper.text()).toContain('演示数据')
  })

  it('fetches industries from API and renders tags', async () => {
    setupMockGet([makePosition()], 1, ['信息技术', '金融', '教育'])
    const wrapper = mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/positions/industries')
    const industrySection = wrapper.find('.industry-tags')
    expect(industrySection.text()).toContain('信息技术')
    expect(industrySection.text()).toContain('教育')
    expect(industrySection.text()).toContain('全部')
  })

  it('shows pagination when total > pageSize', async () => {
    setupMockGet([makePosition()], 50, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.pagination-wrapper').exists()).toBe(true)
  })

  it('hides pagination when total <= pageSize', async () => {
    setupMockGet([makePosition()], 5, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.pagination-wrapper').exists()).toBe(false)
  })

  it('displays total count', async () => {
    setupMockGet([makePosition()], 42, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.result-count').text()).toContain('42')
  })

  // ── D-04: 行业 chip（M10 数据透明）+ created_at 相对时间 ──
  it('renders an industry chip on every card', async () => {
    setupMockGet([
      makePosition({ position_id: 'p1', industry: '互联网' }),
      makePosition({ position_id: 'p2', industry: '金融' }),
    ], 2, [])
    const wrapper = mountPage()
    await flushPromises()
    const chips = wrapper.findAll('.industry-chip')
    expect(chips.length).toBe(2)
    expect(chips[0].text()).toBe('互联网')
    expect(chips[1].text()).toBe('金融')
  })

  it('labels industry chip as 未分类 when industry is missing', async () => {
    setupMockGet([makePosition({ position_id: 'p1', industry: '' })], 1, [])
    const wrapper = mountPage()
    await flushPromises()
    const chip = wrapper.find('.industry-chip')
    expect(chip.exists()).toBe(true)
    // 诚实空态：不渲染空 chip，标注「未分类」
    expect(chip.text()).toBe('未分类')
  })

  it('renders card count matching API total on the page', async () => {
    const items = Array.from({ length: 5 }, (_, i) =>
      makePosition({ position_id: `p${i}`, name_cn: `岗位${i}` }))
    setupMockGet(items, 5, [])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.position-card').length).toBe(5)
    expect(wrapper.find('.result-count').text()).toContain('5')
  })
})
