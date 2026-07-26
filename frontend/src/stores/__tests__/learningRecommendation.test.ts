/**
 * Learning recommendation store tests — covers recommendations + batch match + error handling
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLearningRecommendationStore } from '../learningRecommendation'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useLearningRecommendationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useLearningRecommendationStore()
    expect(store.recommendations).toEqual([])
    expect(store.recLoading).toBe(false)
    expect(store.recError).toBeNull()
    expect(store.batchResults).toEqual([])
    expect(store.batchLoading).toBe(false)
  })

  // ── 2. fetchRecommendations action ──

  it('should fetch recommendations and set state', async () => {
    const request = (await import('@/api/request')).default
    const mockRecs = {
      items: [
        { skill: 'Rust', reason: 'High demand', importance: 'required', estimated_hours: 20 },
        { skill: 'Go', reason: 'Growing ecosystem', importance: 'bonus', estimated_hours: 15 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockRecs)

    const store = useLearningRecommendationStore()
    await store.fetchRecommendations()

    expect(store.recommendations).toHaveLength(2)
    expect(store.recommendations[0].skill).toBe('Rust')
    expect(store.recommendations[0].priority).toBe('high')
    expect(store.recommendations[1].priority).toBe('low')
    expect(request.get).toHaveBeenCalledWith('/learning/recommendations')
  })

  // ── 3. runBatchMatch action ──

  it('should run batch match and set results', async () => {
    const request = (await import('@/api/request')).default
    const mockResults = {
      results: [
        // fix: 后端返回 { position_name, result: {match_score, ...} } 嵌套结构
        {
          position_name: 'Dev',
          result: { match_score: 0.8, matched_skills: ['Python'], gap_skills: ['Docker'] },
        },
      ],
    }
    vi.mocked(request.post).mockResolvedValueOnce(mockResults)

    const store = useLearningRecommendationStore()
    const items = [{ skills: ['Python'], position: 'Dev' }]
    const results = await store.runBatchMatch(items)

    expect(results).toHaveLength(1)
    expect(store.batchResults).toHaveLength(1)
    expect(store.batchLoading).toBe(false)
    // fix: skills 必须是 PersonSkillInput 对象数组（与后端 BatchMatchItem.skills 对齐）
    expect(request.post).toHaveBeenCalledWith('/match/batch', {
      items: [{
        skills: [{ name: 'Python', proficiency: '熟悉' }],
        position: 'Dev',
        position_name: 'Dev',
      }],
    })
  })

  // ── 4. Error handling ──

  it('should set error and clear recommendations when fetchRecommendations fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = useLearningRecommendationStore()
    await store.fetchRecommendations()

    expect(store.recError).toContain('获取推荐失败')
    expect(store.recommendations).toEqual([])
    expect(store.recLoading).toBe(false)
  })
})
