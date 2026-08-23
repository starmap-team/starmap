/**
 * MatchDiagnosis.vue behavior tests.
 * Mocks @/api/request so the real match/resume/user stores run without backend calls.
 * G1 gap closure (05-03): 向导流程 / 雷达映射 / 诊断结果渲染 / 空结果守卫 / 批量模式.
 */
/* eslint-disable vue/one-component-per-file -- test-local interaction stubs */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { nextTick, defineComponent } from 'vue'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing page/stores ──
const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: () => Promise.resolve({}),
    delete: () => Promise.resolve({}),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/match', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/useAuthBootstrap', () => ({
  ensureBootstrapped: vi.fn().mockResolvedValue(true),
}))

import MatchDiagnosis from '../MatchDiagnosis.vue'
import { useResumeStore } from '@/stores/resume'
import { useUserStore } from '@/stores/user'
import { useMatchStore } from '@/stores/match'
import { PROFICIENCY_MAP } from '@/constants/labels'

// ── explicit interaction stubs (findComponent matches by definition) ──
const MatchFlowStub = defineComponent({
  name: 'MatchFlow',
  emits: ['navigate'],
  template: '<div class="stub-match-flow" />',
})
const PositionSearchStub = defineComponent({
  name: 'PositionSearch',
  emits: ['select'],
  template: '<div class="stub-position-search" />',
})
const SkillRadarStub = defineComponent({
  name: 'SkillRadar',
  props: { data: { type: Array, default: () => [] }, positionName: { type: String, default: '' } },
  template: '<div class="stub-skill-radar" />',
})
const MatchTrustGuideStub = defineComponent({
  name: 'MatchTrustGuide',
  props: {
    matchScore: { type: [Number, String], default: null },
    trustScore: { type: [Number, String], default: null },
    scoreBreakdown: { type: Object, default: null },
    note: { type: String, default: null },
  },
  template: '<div class="stub-match-trust-guide" />',
})
const ElTabsStub = defineComponent({
  name: 'ElTabs',
  emits: ['update:modelValue'],
  template: '<div class="stub-el-tabs"><slot /></div>',
})

const SAMPLE_POSITION_SKILLS = {
  position: { name: 'Python 工程师' },
  skills: [
    { name: 'Python', importance: 'required', proficiency: '精通' },
    { name: 'SQL', importance: 'required', proficiency: '熟悉' },
    { name: 'Docker', importance: 'bonus', proficiency: '熟悉' },
  ],
}

const SAMPLE_RESULT = {
  match_id: 'm-1',
  match_score: 0.82,
  matched_skills: ['Python', 'SQL'],
  gap_skills: ['Kubernetes'],
  recommendations: ['学习 Kubernetes'],
  target_position: 'Python 工程师',
  overall_assessment: '匹配度良好',
  estimated_learning_time: '4 周',
  cii: 0.7,
  trust_score: 0.6,
  note: '匹配结果仅供参考',
  score_breakdown: { required_avg: 0.8, bonus_avg: 0.87, weight_required: 0.7, weight_bonus: 0.3, inflated: false },
}

const EMPTY_RESULT = {
  match_id: 'm-2',
  match_score: 0,
  matched_skills: [],
  gap_skills: [],
  recommendations: [],
  target_position: 'Python 工程师',
  overall_assessment: '',
  cii: null,
  trust_score: null,
  note: null,
  score_breakdown: null,
}

type PageWrapper = VueWrapper<InstanceType<typeof MatchDiagnosis>>

function mountPage(): PageWrapper {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(MatchDiagnosis, {
    global: {
      plugins: [ElementPlus, pinia],
      stubs: {
        MainLayout: { template: '<div><slot /></div>' },
        'router-link': true,
        'router-view': true,
        'v-chart': true,
        MatchFlow: MatchFlowStub,
        PositionSearch: PositionSearchStub,
        SkillRadar: SkillRadarStub,
        MatchTrustGuide: MatchTrustGuideStub,
        ElTabs: ElTabsStub,
        // slot-rendering stubs so step content stays reachable
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-tab-pane': { template: '<div class="el-tab-pane-stub"><slot /></div>' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-input': true,
      },
    },
  })
}

/** Drive the wizard via the page's own MatchFlow navigate event. */
async function navigate(wrapper: PageWrapper, step: number) {
  wrapper.findComponent(MatchFlowStub).vm.$emit('navigate', step)
  await nextTick()
}

/** Select a target position via the PositionSearch select event. */
async function selectPosition(wrapper: PageWrapper, name = 'Python 工程师') {
  wrapper.findComponent(PositionSearchStub).vm.$emit('select', { position_id: 'p1', name })
  await flushPromises()
}

/** Click the 开始诊断 button inside .step-actions. */
async function clickStartDiagnosis(wrapper: PageWrapper) {
  await wrapper.find('.step-actions .el-button-stub').trigger('click')
  await flushPromises()
}

describe('MatchDiagnosis.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ items: [] }) // /match/history 等默认
    mockPost.mockResolvedValue(SAMPLE_RESULT) // /match/position 默认
  })

  it('renders without crashing', () => {
    const wrapper = mountPage()
    expect(wrapper.exists()).toBe(true)
  })

  it('向导流程：step 0 初始渲染，导航可推进各步骤内容', async () => {
    const wrapper = mountPage()
    // 2026-08-23: onFlowNavigate 守卫要求 step 2 需技能, step 3/4 需匹配结果
    const userStore = useUserStore()
    userStore.parsedSkills = [{ skill: 'Python', category: 'hard_skill', proficiency: '熟悉' }]
    const matchStore = useMatchStore()
    matchStore.result = SAMPLE_RESULT as unknown as typeof matchStore.result
    // step 0: 录入技能
    expect(wrapper.find('.step-content .sc-title').text()).toContain('录入你的技能')
    await navigate(wrapper, 1)
    expect(wrapper.find('.step-content .sc-title').text()).toContain('选择目标岗位')
    await navigate(wrapper, 2)
    expect(wrapper.find('.step-content .sc-title').text()).toContain('技能雷达对比')
    await navigate(wrapper, 3)
    expect(wrapper.findComponent(MatchTrustGuideStub).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'GapAnalysisReport' }).exists()).toBe(true)
    await navigate(wrapper, 4)
    expect(wrapper.findComponent({ name: 'LearningPathPlan' }).exists()).toBe(true)
  })

  it('雷达映射：选择岗位后岗位技能映射为 radarData，且渲染 D-04 口径注记', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/position/')) return Promise.resolve(SAMPLE_POSITION_SKILLS)
      return Promise.resolve({ items: [] })
    })
    const wrapper = mountPage()
    const resumeStore = useResumeStore()
    resumeStore.result = {
      position_name: 'Python 工程师',
      required_skills: [{ skill: 'Python', category: 'hard_skill', proficiency: '熟悉' }],
      preferred_skills: [],
      experience_required: 3,
      education_required: '本科',
      confidence: 0.9,
      hallucination_score: null,
      normalized_skills: [],
    }
    await navigate(wrapper, 1)
    await selectPosition(wrapper)
    // 进入 step 2 雷达对比
    expect(wrapper.find('.step-content .sc-title').text()).toContain('技能雷达对比')
    const radarData = wrapper.findComponent(SkillRadarStub).props('data') as { skill: string; required: number; user: number }[]
    expect(radarData).toEqual([
      { skill: 'Python', required: PROFICIENCY_MAP['精通'], user: PROFICIENCY_MAP['熟悉'] },
      { skill: 'SQL', required: PROFICIENCY_MAP['熟悉'], user: 0 },
    ])
    // D-04 口径注记
    expect(wrapper.find('.radar-note').text()).toContain('模糊匹配')
  })

  it('诊断结果渲染：开始诊断后进入 step 3，score_breakdown/trust/note 透传到 MatchTrustGuide', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/position/')) return Promise.resolve(SAMPLE_POSITION_SKILLS)
      return Promise.resolve({ items: [] })
    })
    mockPost.mockResolvedValue(SAMPLE_RESULT)
    const wrapper = mountPage()
    const userStore = useUserStore()
    userStore.parsedSkills = [{ skill: 'Python', category: 'hard_skill', proficiency: '熟悉' }]
    await navigate(wrapper, 1)
    await selectPosition(wrapper)
    await clickStartDiagnosis(wrapper)
    const guide = wrapper.findComponent(MatchTrustGuideStub)
    expect(guide.props('matchScore')).toBe(0.82)
    expect(guide.props('trustScore')).toBe(0.6)
    expect(guide.props('scoreBreakdown')).toEqual(SAMPLE_RESULT.score_breakdown)
    expect(guide.props('note')).toBe('匹配结果仅供参考')
    expect(wrapper.findComponent({ name: 'GapAnalysisReport' }).exists()).toBe(true)
  })

  it('空结果守卫：请求成功但无差距(岗位无画像)时跳转 step 3 展示空态引导', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/position/')) return Promise.resolve(SAMPLE_POSITION_SKILLS)
      return Promise.resolve({ items: [] })
    })
    mockPost.mockResolvedValue(EMPTY_RESULT)
    const wrapper = mountPage()
    const userStore = useUserStore()
    userStore.parsedSkills = [{ skill: 'Python', category: 'hard_skill', proficiency: '熟悉' }]
    await navigate(wrapper, 1)
    await selectPosition(wrapper)
    await clickStartDiagnosis(wrapper)
    // 2026-08-23 BUG-006 优化: 请求成功(非 null)即使结果为空也跳 step 3,
    // GapAnalysisReport 展示"岗位暂无画像"空态, 而非停在 step 2 造成"空白页"错觉。
    expect(wrapper.findComponent(MatchTrustGuideStub).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'GapAnalysisReport' }).exists()).toBe(true)
  })

  it('批量模式：切换到 batch 时渲染 MatchBatchMode', async () => {
    const wrapper = mountPage()
    expect(wrapper.findComponent({ name: 'MatchBatchMode' }).exists()).toBe(false)
    wrapper.findComponent(ElTabsStub).vm.$emit('update:modelValue', 'batch')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'MatchBatchMode' }).exists()).toBe(true)
  })
})
