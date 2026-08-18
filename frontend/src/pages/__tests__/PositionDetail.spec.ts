/**
 * PositionDetail.vue — 岗位详情页测试 (7 用例)
 *
 * 覆盖: 渲染/loading 骨架屏/技能表格/空技能/未找到友好态/雷达图 props
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
  useRoute: () => ({ params: { name: 'test-position-id' }, query: {}, path: '/position/test-position-id', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import PositionDetail from '../PositionDetail.vue'

function makeDetailResponse(overrides: Record<string, unknown> = {}) {
  return {
    position_id: 'uuid-001',
    name: 'Python 后端开发工程师',
    name_cn: '后端工程师',
    industry: '信息技术',
    description: '负责核心业务系统后端设计与开发',
    skills_required: [
      { skill_id: 's1', name: 'Python', category: 'hard_skill', proficiency: '精通', confidence: 0.95, source_count: 10 },
      { skill_id: 's2', name: 'FastAPI', category: 'tool', proficiency: '熟悉', confidence: 0.85, source_count: 6 },
      { skill_id: 's3', name: 'PostgreSQL', category: 'tool', proficiency: '了解', confidence: 0.7, source_count: 3 },
    ],
    discovered_at: '2026-01-01T00:00:00',
    ...overrides,
  }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(PositionDetail, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        'router-link': true,
        'router-view': true,
        MainLayout: { template: '<div><slot /></div>' },
        // SkillRadar 依赖 echarts，jsdom 无法渲染 canvas → 用 stub 替代
        SkillRadar: {
          name: 'SkillRadar',
          template: '<div class="skill-radar-stub" />',
          props: ['data', 'positionName'],
        },
      },
    },
  })
}

describe('PositionDetail.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue(makeDetailResponse())
  })

  it('renders without crashing', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('shows skeleton loading state before data resolves', async () => {
    mockGet.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountPage()
    // onMounted 设置 loading=true，DOM 更新需要 nextTick
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.el-skeleton').exists()).toBe(true)
  })

  it('renders position name and industry after load', async () => {
    mockGet.mockResolvedValue(makeDetailResponse())
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('后端工程师')
    expect(wrapper.text()).toContain('信息技术')
  })

  it('renders skills table with skill names', async () => {
    mockGet.mockResolvedValue(makeDetailResponse())
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('技能要求 (3)')
    expect(wrapper.text()).toContain('Python')
    expect(wrapper.text()).toContain('FastAPI')
  })

  it('shows friendly hint when skills are empty', async () => {
    mockGet.mockResolvedValue(makeDetailResponse({ skills_required: [] }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('技能要求 (0)')
  })

  it('shows not-found state when API rejects', async () => {
    mockGet.mockRejectedValue(new Error('Not Found'))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('未找到该岗位')
    expect(wrapper.text()).toContain('返回岗位列表')
  })

  it('passes radar data to SkillRadar component', async () => {
    mockGet.mockResolvedValue(makeDetailResponse())
    const wrapper = mountPage()
    await flushPromises()
    const radar = wrapper.findComponent({ name: 'SkillRadar' })
    expect(radar.exists()).toBe(true)
    const props = radar.props()
    expect(props.data).toHaveLength(3)
    expect(props.data[0]).toHaveProperty('skill', 'Python')
    expect(props.positionName).toBe('后端工程师')
  })

  it('shows recent-update badge when discovered_at is recent', async () => {
    const recent = new Date(Date.now() - 3 * 86400000).toISOString()
    mockGet.mockResolvedValue(makeDetailResponse({ discovered_at: recent }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('数据更新于')
  })

  it('shows demo-data badge when discovered_at is null', async () => {
    mockGet.mockResolvedValue(makeDetailResponse({ discovered_at: null }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('演示数据')
  })

  // ── D-05: 雷达图缺数据降级（沿 M5 D-04：无画像岗位不返回 404）──
  it('degrades radar to "暂无技能画像" card when skills are empty', async () => {
    mockGet.mockResolvedValue(makeDetailResponse({ skills_required: [] }))
    const wrapper = mountPage()
    await flushPromises()

    // 雷达图不渲染，改渲染降级卡片 + 引导按钮
    expect(wrapper.findComponent({ name: 'SkillRadar' }).exists()).toBe(false)
    expect(wrapper.find('.no-profile-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无技能画像')
    expect(wrapper.text()).toContain('前往 JD 抽取')
    // 关键：岗位本体仍正常展示，不落入 404 友好态
    expect(wrapper.text()).not.toContain('未找到该岗位')
    expect(wrapper.text()).toContain('后端工程师')
  })

  it('keeps radar and hides degradation card when skills exist', async () => {
    mockGet.mockResolvedValue(makeDetailResponse())
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findComponent({ name: 'SkillRadar' }).exists()).toBe(true)
    expect(wrapper.find('.no-profile-card').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('暂无技能画像')
  })
})
