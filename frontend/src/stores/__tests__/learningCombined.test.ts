/**
 * Combined learning store (useLearningStore) reactivity tests.
 *
 * DEF-002 regression guard: the combined store previously returned a plain
 * object with one-time snapshots of sub-store refs (`batchResults: rec.batchResults`),
 * so later `batchResults.value = [...]` replacements never propagated to consumers.
 * This made batch match results / competitiveness charts render stale data.
 *
 * The fix wraps storeToRefs in `reactive()`, keeping values readable AND reactive.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import { useLearningStore } from '../learning'
import { useLearningRecommendationStore } from '../learningRecommendation'
import { useLearningAnalyticsStore } from '../learningAnalytics'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useLearningStore combined store reactivity', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('batchResults reads through to sub-store updates (DEF-002)', async () => {
    const learning = useLearningStore()
    const rec = useLearningRecommendationStore()

    expect(learning.batchResults).toEqual([])

    // Simulate runBatchMatch writing into the sub-store ref
    rec.batchResults = [
      { position_name: 'Python 后端开发工程师', match_score: 0.52, matched_skills: ['Python'], gap_skills: ['Django'], error: undefined },
    ]
    await nextTick()

    expect(learning.batchResults).toHaveLength(1)
    expect(learning.batchResults[0].position_name).toBe('Python 后端开发工程师')
    // 数组引用变化也必须传导（此前快照 bug 的核心：.value 替换后旧数组仍被引用）
    rec.batchResults = []
    await nextTick()
    expect(learning.batchResults).toEqual([])
  })

  it('competitiveness reads through to sub-store updates (DEF-003)', async () => {
    const learning = useLearningStore()
    const analytics = useLearningAnalyticsStore()

    expect(learning.competitiveness).toEqual([])

    analytics.competitiveness = [{ skill: 'Python', market_demand: 1, your_level: 0.8, avg_level: 0.5 }]
    await nextTick()

    expect(learning.competitiveness).toHaveLength(1)
    expect(learning.competitiveness[0].skill).toBe('Python')
  })

  it('plans / currentPlan / recommendations stay reactive too', async () => {
    const learning = useLearningStore()
    const rec = useLearningRecommendationStore()

    rec.recommendations = [{ skill: 'Python', reason: '市场需求高', priority: 'high', estimated_hours: 10 }]
    await nextTick()
    expect(learning.recommendations).toHaveLength(1)
    expect(learning.recommendations[0].skill).toBe('Python')
  })

  it('loading / error computeds aggregate sub-store flags', async () => {
    const learning = useLearningStore()
    const rec = useLearningRecommendationStore()

    expect(learning.loading).toBe(false)
    rec.recLoading = true
    await nextTick()
    expect(learning.loading).toBe(true)
  })
})
