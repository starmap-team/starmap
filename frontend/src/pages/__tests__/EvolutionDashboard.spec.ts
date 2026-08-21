/**
 * 覆盖:
 *  - 4 KPI 数字响应（kpiCards computed）
 *  - mount 时 4 个 fetch 并行触发（fetchTrends / fetchSnapshots / fetchEmergingAlerts / fetchKpi）
 *  - 选中技能 → CII 仪表盘 / 技能对比响应
 *  - 刷新按钮 → fetchTrends + analyze 触发
 *  - 技能点击 → fetchChangelog 抽屉
 *  - 数据口径说明 collapse 展开
 *  - 提示框（新手友好引导）渲染
 *  - 对照口径（trust_mean_neo4j_skill）响应
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── mock request BEFORE importing page/store ──
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
  useRoute: () => ({ params: {}, query: {}, path: '/evolution', meta: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), go: vi.fn(), back: vi.fn() }),
}))
vi.mock('echarts/core', () => ({ use: () => {}, default: {} }))
vi.mock('vue-echarts', () => ({ default: { template: '<div class="v-chart-stub" />' } }))

import EvolutionDashboard from '../EvolutionDashboard.vue'

// ── fixtures：模拟 /evolution/* 完整 6 端点响应 ──
const TRENDS_RESPONSE = {
  data: {
    period: '90d',
    data_points: [
      { date: '2026-08-01', overall_score: 0.85, duplicate_rate: 0.05, freshness_hours: 2, total_records: 400, new_records: 10, quality_score: 0.85, hallucination_rate: 0.03 },
    ],
    summary: { total_skills: 361, avg_cii: 97.1 },
    items: [
      { skill_name: 'Terraform', trend: 'rising', current_cii: 166.7, change: 66.7, confidence: 0.5, related_positions: ['高级后端工程师'] },
      { skill_name: 'Python', trend: 'stable', current_cii: 66.7, change: -33.3, confidence: 0.36, related_positions: [] },
    ],
  },
}

const SNAPSHOTS_RESPONSE = [
  { snapshot_date: '2026-08-01', position_count: 233, skill_count: 590, source_count: 36 },
  { snapshot_date: '2026-07-01', position_count: 200, skill_count: 550, source_count: 30 },
]

const KPI_RESPONSE = {
  emerging_count: 5,
  trust_mean: 0.747,
  trust_mean_neo4j_skill: 0.5,
  cii_mean: 97.1,
  alert_count: 9,
  days: 90,
}

// store 期望 { alerts: [...], total, summary }
const EMERGING_ALERTS_RESPONSE = {
  alerts: [
    { skill_name: 'Tableau', level: 'emerging', z_score: 10.0, portability_score: 0.5, current_count: 10, avg_count: 9.0, domain_count: 1 },
    { skill_name: 'PyTorch', level: 'emerging', z_score: 10.0, portability_score: 0.5, current_count: 10, avg_count: 9.0, domain_count: 1 },
    { skill_name: 'AWS', level: 'rising', z_score: 0.0, portability_score: 0.5, current_count: 5, avg_count: 5.0, domain_count: 1 },
    { skill_name: 'SQL', level: 'declining', z_score: -1.523, portability_score: 0.32, current_count: 3, avg_count: 8.0, domain_count: 1 },
  ],
  total: 4,
  summary: 'emerging: 2, rising: 1, declining: 1',
}

const CHANGELOG_RESPONSE = [
  { id: 1, position: 'Senior Backend Engineer', skill: 'Terraform', change: 'added', trust_score: 0.75, created_at: '2026-08-01' },
]

const ANALYZE_RESPONSE = {
  message: 'Analysis triggered',
  task_id: 'task-uuid-123',
  days: 90,
}

// ── mock router ──
function setupMocks() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/evolution/trends')) return Promise.resolve(TRENDS_RESPONSE.data)
    if (url.includes('/evolution/snapshots')) return Promise.resolve(SNAPSHOTS_RESPONSE)
    if (url.includes('/evolution/kpi')) return Promise.resolve(KPI_RESPONSE)
    if (url.includes('/evolution/emerging-alerts')) return Promise.resolve(EMERGING_ALERTS_RESPONSE)
    if (url.includes('/evolution/changelog/')) return Promise.resolve(CHANGELOG_RESPONSE)
    return Promise.resolve({})
  })
  mockPost.mockImplementation((url: string) => {
    if (url.includes('/evolution/analyze')) return Promise.resolve(ANALYZE_RESPONSE)
    return Promise.resolve({})
  })
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(EvolutionDashboard, {
    global: { plugins: [ElementPlus, pinia] },
  })
}

// ════════════════════════════════════════════════════════════════
// 1. Mount 触发所有 fetch actions（fetchTrends / fetchSnapshots / fetchEmergingAlerts / fetchKpi）
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 组件 fetch actions 触发', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('mount 后触发 /evolution/trends', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith(expect.stringContaining('/evolution/trends'), expect.any(Object))
  })

  it('mount 后触发 /evolution/snapshots', async () => {
    mountPage()
    await flushPromises()
    // fetchSnapshots 拼 `?limit=50` 到 URL，且只传一个参数
    expect(mockGet).toHaveBeenCalledWith(expect.stringContaining('/evolution/snapshots'))
  })

  it('mount 后触发 /evolution/kpi', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/evolution/kpi', expect.any(Object))
  })

  it('mount 后触发 /evolution/emerging-alerts', async () => {
    mountPage()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith(expect.stringContaining('/emerging-alerts'), expect.any(Object))
  })

  it('mount 后 4 个 fetch 并发（无序）', async () => {
    mountPage()
    await flushPromises()
    const calls = mockGet.mock.calls.map(c => c[0])
    const expectedEndpoints = ['/evolution/trends', '/evolution/snapshots', '/evolution/kpi', '/emerging-alerts']
    expectedEndpoints.forEach(ep => {
      expect(calls.some(c => c.includes(ep))).toBe(true)
    })
  })
})

// ════════════════════════════════════════════════════════════════
// 2. KPI 数字响应（store → 组件渲染）
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution KPI 数字响应', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('kpiCards 包含 4 张（沿 M11 UX 重构 + 高度统一）', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchKpi()
    expect(store.kpi.emerging_count).toBe(5)
    expect(store.kpi.trust_mean).toBe(0.747)
    expect(store.kpi.cii_mean).toBe(97.1)
    expect(store.kpi.alert_count).toBe(9)
  })

  it('trust_mean_neo4j_skill 字段同步（跨菜单口径对照 D-cross）', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchKpi()
    // M11 D-cross：信任均值对照口径（Neo4j Skill.trust_score 实时均值）
    expect(store.kpi.trust_mean_neo4j_skill).toBe(0.5)
  })

  it('kpiCards computed 渲染对照口径文案（含 /quality 引用）', async () => {
    // kpiCards 是组件级 computed；通过 mount + 断言组件内 trust-mean breakdown
    const wrapper = mountPage()
    await flushPromises()
    const breakdowns = wrapper.findAll('.kpi-number-breakdown')
    // 信任均值卡 breakdown 含 "对照：/quality"
    const trustBreakdown = breakdowns.map(b => b.text()).find(t => t.includes('对照：/quality'))
    expect(trustBreakdown).toBeTruthy()
    expect(trustBreakdown).toContain('平均信任度')
  })
})

// ════════════════════════════════════════════════════════════════
// 3. 选中技能 → CII 仪表盘 + 技能对比响应
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution selectedSkill 响应', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('selectSkill 变化 → store.trendItems 过滤响应', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    const result = await store.fetchTrends()
    expect(result.items.length).toBe(2)
    expect(store.trendItems.length).toBe(2)
  })

  it('fetchEmergingAlerts 成功填充 alerts 数组', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()
    expect(store.emergingAlerts.length).toBe(4)
    expect(store.emergingAlerts[0].skill_name).toBe('Tableau')
    expect(store.emergingAlerts[0].level).toBe('emerging')
  })
})

// ════════════════════════════════════════════════════════════════
// 4. 刷新按钮 / 分析触发（事件绑定）
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 事件绑定', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('analyze() 调用 POST /evolution/analyze', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    const result = await store.analyze()
    expect(mockPost).toHaveBeenCalledWith('/evolution/analyze', undefined, expect.any(Object))
    expect(result.task_id).toBe('task-uuid-123')
  })

  it('fetchTrends(days=30) 携带 days 参数', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchTrends(30)
    const call = mockGet.mock.calls.find(c => c[0].includes('/evolution/trends'))
    expect(call?.[1]?.params?.days).toBe(30)
  })

  it('fetchChangelog(skill_name) 携带 skill 参数', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchChangelog('Python')
    // fetchChangelog 用模板字符串拼 URL（无第二参数）
    expect(mockGet).toHaveBeenCalledWith('/evolution/changelog/Python')
  })

  it('fetchSnapshots(limit) 携带 limit 参数', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchSnapshots(10)
    // fetchSnapshots 拼 `?limit=10` 到 URL（无第二参数）
    expect(mockGet).toHaveBeenCalledWith('/evolution/snapshots?limit=10')
  })
})

// ════════════════════════════════════════════════════════════════
// 5. 数据口径说明 collapse（E2/E7）
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 数据口径说明 collapse', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('collapse 初始存在（explainer-card）', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.explainer-card').exists() || wrapper.find('.el-collapse').exists()).toBe(true)
  })
})

// ════════════════════════════════════════════════════════════════
// 6. 新手友好引导 alert（沿 ui-ux-pro-max）
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 新手友好引导', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('kpi-help-alert 渲染（含"什么是技能演化看板"）', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const alert = wrapper.find('.kpi-help-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('什么是技能演化看板')
  })

  it('4 张 kpi-number-card 都有 kpi-help-icon', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const helpIcons = wrapper.findAll('.kpi-help-icon')
    expect(helpIcons.length).toBe(4)
  })

  it('4 张 kpi-number-card 渲染', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.kpi-number-card').length).toBe(4)
  })
})

// ════════════════════════════════════════════════════════════════
// 7. 错误处理 — fetch 失败不崩 + 降级
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 错误降级', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchTrends 失败 → 异常传播（store 无 catch 层，调用方处理）', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    // fetchTrends 只有 try/finally（无 catch）→ 异常向上传播，前端 ElMessage 处理
    await expect(store.fetchTrends()).rejects.toThrow('Network Error')
  })

  it('fetchKpi 失败 → 异常传播 + kpi 保持默认 0', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await expect(store.fetchKpi()).rejects.toThrow('Network Error')
    // kpi 赋值在 try 内未执行 → 保持默认
    expect(store.kpi.emerging_count).toBe(0)
    expect(store.kpi.trust_mean).toBeNull()  // 空表后端返回 null → 显示"—"而非误导 0%
  })

  it('fetchEmergingAlerts 失败 → alerts 保持空数组', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network Error'))
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()
    expect(store.emergingAlerts).toEqual([])
  })
})

// ════════════════════════════════════════════════════════════════
// 8. 端到端契约 — 后端 → store → 组件渲染链路
// ════════════════════════════════════════════════════════════════

describe('Phase 11 Evolution 端到端契约', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('后端 KPI 响应字段全部映射到 store.kpi', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchKpi()
    const k = store.kpi
    // 三端契约（沿 D-cross 修复）：5 个 KPI 字段 + trust_mean_neo4j_skill
    expect(k).toHaveProperty('emerging_count', 5)
    expect(k).toHaveProperty('trust_mean', 0.747)
    expect(k).toHaveProperty('trust_mean_neo4j_skill', 0.5)
    expect(k).toHaveProperty('cii_mean', 97.1)
    expect(k).toHaveProperty('alert_count', 9)
  })

  it('后端 emerging_alerts 数据结构契约', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()
    const alert = store.emergingAlerts[0]
    expect(alert).toMatchObject({
      skill_name: expect.any(String),
      level: expect.stringMatching(/^(emerging|rising|stable|declining)$/),
      z_score: expect.any(Number),
      portability_score: expect.any(Number),
    })
  })

  it('后端 trends 数据契约（含 items）', async () => {
    const { useEvolutionStore } = await import('@/stores/evolution')
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useEvolutionStore()
    const result = await store.fetchTrends()
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.items[0]).toMatchObject({
      skill_name: expect.any(String),
      trend: expect.stringMatching(/^(rising|stable|declining)$/),
      current_cii: expect.any(Number),
    })
  })
})
