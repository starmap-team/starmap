/**
 * Learning analytics store tests — covers competitiveness + career path + industry trends
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLearningAnalyticsStore } from '../learningAnalytics'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useLearningAnalyticsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useLearningAnalyticsStore()
    expect(store.competitiveness).toEqual([])
    expect(store.competitivenessLoading).toBe(false)
    expect(store.careerPath).toEqual([])
    expect(store.careerPathLoading).toBe(false)
    expect(store.industryTrends).toEqual([])
    expect(store.industryTrendsLoading).toBe(false)
    expect(store.analyticsError).toBeNull()
  })

  // ── 2. fetchCompetitiveness action ──

  it('should fetch competitiveness data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      // fix: 后端返回 bottleneck_skills 列表（扁平字段），非 items
      bottleneck_skills: [
        { skill: 'Python', market_demand: 90, your_level: 3, avg_level: 4 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningAnalyticsStore()
    const result = await store.fetchCompetitiveness('Backend Developer')

    expect(result).toHaveLength(1)
    expect(store.competitiveness).toHaveLength(1)
    expect(store.competitivenessLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/match/competitiveness/Backend%20Developer')
  })

  // ── 3. fetchCareerPath action ──

  it('should fetch career path data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      path: [
        { position: 'Senior Dev', skills_required: ['Python'], estimated_time: '2 years', probability: 0.7 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningAnalyticsStore()
    const result = await store.fetchCareerPath('Backend Developer')

    expect(result).toHaveLength(1)
    expect(store.careerPath).toHaveLength(1)
    expect(store.careerPathLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/career-path/Backend%20Developer')
  })

  // ── 4. fetchIndustryTrends action ──

  it('should fetch industry trends data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      items: [
        { skill: 'Rust', current_demand: 80, trend: 'rising', growth_rate: 0.3, avg_salary: 150000 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningAnalyticsStore()
    const result = await store.fetchIndustryTrends()

    expect(result).toHaveLength(1)
    expect(store.industryTrends).toHaveLength(1)
    expect(store.industryTrendsLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/industry-report')
  })
})
