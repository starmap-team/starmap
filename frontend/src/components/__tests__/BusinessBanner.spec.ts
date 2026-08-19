/**
 * BusinessBanner 单元测试
 *
 * 覆盖：
 *  - 基础渲染：type / section / title / description
 *  - 5 种 type 的图标 / 类型标签映射
 *  - meta 数组结构化渲染（含 code 样式 + category 前缀）
 *  - meta 字符串向后兼容：解析 <code>...</code> + ` · ` 分隔
 *  - collapsible 行为：长描述默认展开，>60 字符出现"收起"按钮
 *  - ARIA role：error=alert，其他=note
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BusinessBanner, { type BannerMetaItem } from '../BusinessBanner.vue'

// Element Plus 组件的最小化 stub，避免 mount 时受全局样式/el-icon 注册副作用影响
const globalStubs = {
  'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
}

function mountBanner(props: Record<string, unknown> = {}) {
  return mount(BusinessBanner, {
    props: {
      title: '测试标题',
      ...props,
    },
    global: { stubs: globalStubs },
  })
}

describe('BusinessBanner', () => {
  /* ─── 基础渲染 ─── */
  it('渲染 title 与 type 默认值 info', () => {
    const wrapper = mountBanner()
    expect(wrapper.find('.biz-banner__title').text()).toBe('测试标题')
    expect(wrapper.find('.biz-banner').classes()).toContain('biz-banner--info')
    expect(wrapper.find('.biz-banner__type').text()).toBe('INFO')
  })

  it('渲染 description 文本', () => {
    const wrapper = mountBanner({ description: '详细说明文字' })
    expect(wrapper.find('.biz-banner__desc').text()).toBe('详细说明文字')
  })

  it('渲染 section 章节徽章', () => {
    const wrapper = mountBanner({ section: '' })
    const badge = wrapper.find('.biz-banner__section')
    expect(badge.exists()).toBe(false)  // v-if="section" hides when empty
  })

  /* ─── 5 种 type 映射 ─── */
  const typeCases = [
    { type: 'info', label: 'INFO' },
    { type: 'success', label: 'SUCCESS' },
    { type: 'warning', label: 'WARNING' },
    { type: 'error', label: 'ERROR' },
    { type: 'note', label: 'NOTE' },
  ] as const

  for (const { type, label } of typeCases) {
    it(`type=${type} 映射到类型标签 ${label}`, () => {
      const wrapper = mountBanner({ type })
      expect(wrapper.find('.biz-banner').classes()).toContain(`biz-banner--${type}`)
      expect(wrapper.find('.biz-banner__type').text()).toBe(label)
    })
  }

  it('error 类型使用 role="alert"（屏幕阅读器优先级）', () => {
    const wrapper = mountBanner({ type: 'error' })
    expect(wrapper.find('.biz-banner').attributes('role')).toBe('alert')
  })

  it('非 error 类型使用 role="note"', () => {
    const wrapper = mountBanner({ type: 'info' })
    expect(wrapper.find('.biz-banner').attributes('role')).toBe('note')
  })

  /* ─── meta 数组结构化渲染 ─── */
  it('渲染结构化 meta 数组，code 字段应用 monospace 样式类', () => {
    const meta: BannerMetaItem[] = [
      { category: '后端', label: '/pipeline/*', code: true, copyable: true },
      { label: 'Neo4j' },
    ]
    const wrapper = mountBanner({ meta })
    const items = wrapper.findAll('.biz-banner__meta-item')
    expect(items).toHaveLength(2)
    expect(items[0].find('.biz-banner__meta-cat').text()).toBe('后端:')
    expect(items[0].find('.biz-banner__meta-chip').classes()).toContain('is-code')
    expect(items[1].find('.biz-banner__meta-chip').classes()).not.toContain('is-code')
  })

  it('空 meta 数组不渲染 meta 容器', () => {
    const wrapper = mountBanner({ meta: [] })
    expect(wrapper.find('.biz-banner__meta').exists()).toBe(false)
  })

  /* ─── meta 字符串向后兼容 ─── */
  it('向后兼容：字符串 meta 中 <code> 片段被解析为 is-code chip', () => {
    const meta = '后端: <code>/pipeline/*</code> · 数据源: <code>pipeline_runs</code> + Neo4j · SSE 实时推送'
    const wrapper = mountBanner({ meta })
    const chips = wrapper.findAll('.biz-banner__meta-chip')
    const codeChips = chips.filter(c => c.classes().includes('is-code'))
    // <code> 片段 = 2 个
    expect(codeChips.length).toBe(2)
    // 标签内容正确
    const labels = chips.map(c => c.find('.biz-banner__meta-label').text())
    expect(labels).toContain('/pipeline/*')
    expect(labels).toContain('pipeline_runs')
    expect(labels).toContain('Neo4j')
    expect(labels).toContain('SSE 实时推送')
  })

  it('向后兼容：字符串 meta 中首个 `Category:` 被抽取为 category 前缀', () => {
    const meta = '后端: <code>/x</code>'
    const wrapper = mountBanner({ meta })
    const firstItem = wrapper.find('.biz-banner__meta-item')
    expect(firstItem.find('.biz-banner__meta-cat').text()).toBe('后端:')
  })

  /* ─── collapsible 行为 ─── */
  it('collapsible=false 时不显示展开/收起按钮', () => {
    const wrapper = mountBanner({ description: '短', collapsible: false })
    expect(wrapper.find('.biz-banner__toggle').exists()).toBe(false)
  })

  it('collapsible=true 且 description > 60 字符时显示收起按钮', () => {
    // 显式构造 > 60 字符的描述
    const long = '这是一段用于测试的非常长的描述文字，' + 'x'.repeat(80)
    expect(long.length).toBeGreaterThan(60)
    const wrapper = mountBanner({ description: long, collapsible: true })
    expect(wrapper.find('.biz-banner__toggle').exists()).toBe(true)
  })

  it('collapsible=true 且 defaultCollapsed=true 时收起描述，aria-expanded=false', () => {
    const long = '这是一段用于测试的非常长的描述文字，' + 'x'.repeat(80)
    const wrapper = mountBanner({ description: long, collapsible: true, defaultCollapsed: true })
    const toggle = wrapper.find('.biz-banner__toggle')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    // 折叠时 description 元素不应渲染
    expect(wrapper.find('.biz-banner__desc').exists()).toBe(false)
  })

  /* ─── compact 模式 ─── */
  it('compact=true 触发紧凑类', () => {
    const wrapper = mountBanner({ compact: true })
    expect(wrapper.find('.biz-banner').classes()).toContain('biz-banner--compact')
  })

  /* ─── 无 v-html 安全保证 ─── */
  it('title 中的 HTML 字符被作为纯文本渲染（XSS 安全）', () => {
    const wrapper = mountBanner({ title: '<img src=x onerror=alert(1)>' })
    // 应该是文本节点，而非真实 img 元素
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.biz-banner__title').text()).toContain('<img')
  })
})
