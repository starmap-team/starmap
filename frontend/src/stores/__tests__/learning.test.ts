/**
 * Learning store tests — covers all 11 actions + initial state + error handling + loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLearningStore } from '../learning'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockPlanResponse = {
  plan_id: 'plan-123',
  position: 'Backend Developer',
  overall_pct: 0.45,
  total_weeks: 8,
  skills: [
    { skill_name: 'Python', status: 'mastered', progress_pct: 100, estimated_hours: 10, prerequisites: [], importance: 'required' },
    { skill_name: 'Docker', status: 'in_progress', progress_pct: 50, estimated_hours: 8, prerequisites: [], importance: 'bonus' },
    { skill_name: 'K8s', status: 'not_started', progress_pct: 0, estimated_hours: 15, prerequisites: ['Docker'], importance: 'required' },
  ],
  phases: [{ skills: ['Python', 'Docker'] }, { skills: ['K8s'] }],
  stats: { created_at: '2024-01-01', updated_at: '2024-01-02' },
}

describe('useLearningStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    })
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useLearningStore()
    expect(store.currentPlan).toBeNull()
    expect(store.plans).toEqual([])
    expect(store.recommendations).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.batchResults).toEqual([])
    expect(store.batchLoading).toBe(false)
    expect(store.competitiveness).toEqual([])
    expect(store.competitivenessLoading).toBe(false)
    expect(store.careerPath).toEqual([])
    expect(store.careerPathLoading).toBe(false)
    expect(store.industryTrends).toEqual([])
    expect(store.industryTrendsLoading).toBe(false)
  })

  // ── 2. createPlan action ──

  it('should create a plan and update state', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningStore()
    const matchResult = { position_name: 'Backend Developer', match_score: 0.7, skill_gap_detail: [] }
    const plan = await store.createPlan(matchResult)

    expect(plan).toBeTruthy()
    expect(plan.plan_id).toBe('plan-123')
    expect(plan.position).toBe('Backend Developer')
    expect(store.currentPlan).toBeTruthy()
    expect(store.currentPlan!.plan_id).toBe('plan-123')
    expect(store.plans).toHaveLength(1)
    expect(store.loading).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalled()
  })

  // ── 3. fetchPlan action ──

  it('should fetch a plan and set currentPlan', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan).toBeTruthy()
    expect(plan!.plan_id).toBe('plan-123')
    expect(store.currentPlan).toBeTruthy()
    expect(store.currentPlan!.position).toBe('Backend Developer')
    expect(request.get).toHaveBeenCalledWith('/learning/plan/plan-123')
  })

  // ── 4. fetchPlans action ──

  it('should fetch plans and populate plans list', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ items: [mockPlanResponse] })

    const store = useLearningStore()
    const plans = await store.fetchPlans()

    expect(plans).toHaveLength(1)
    expect(store.plans).toHaveLength(1)
    expect(store.plans[0].plan_id).toBe('plan-123')
    // Should set currentPlan to first plan when none is set
    expect(store.currentPlan).toBeTruthy()
    expect(store.currentPlan!.plan_id).toBe('plan-123')
  })

  // ── 5. updateProgress action ──

  it('should update progress and modify skill status', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
    vi.mocked(request.put).mockResolvedValueOnce({})

    const store = useLearningStore()
    await store.fetchPlan('plan-123')
    expect(store.currentPlan).toBeTruthy()

    await store.updateProgress('plan-123', 'Docker', 'mastered')

    const skillItem = store.currentPlan!.skills.find(s => s.skill === 'Docker')
    expect(skillItem!.status).toBe('mastered')
    expect(skillItem!.progress_pct).toBe(100)
    expect(request.put).toHaveBeenCalledWith('/learning/plan/plan-123/progress', {
      skill_name: 'Docker',
      status: 'mastered',
    })
  })

  it('should set progress_pct to 10 when status changes to in_progress from 0', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
    vi.mocked(request.put).mockResolvedValueOnce({})

    const store = useLearningStore()
    await store.fetchPlan('plan-123')

    await store.updateProgress('plan-123', 'K8s', 'in_progress')

    const skillItem = store.currentPlan!.skills.find(s => s.skill === 'K8s')
    expect(skillItem!.status).toBe('in_progress')
    expect(skillItem!.progress_pct).toBe(10)
  })

  // ── 6. fetchRecommendations action ──

  it('should fetch recommendations and set state', async () => {
    const request = (await import('@/api/request')).default
    const mockRecs = {
      items: [
        { skill: 'Rust', reason: 'High demand', importance: 'required', estimated_hours: 20 },
        { skill: 'Go', reason: 'Growing ecosystem', importance: 'bonus', estimated_hours: 15 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockRecs)

    const store = useLearningStore()
    await store.fetchRecommendations()

    expect(store.recommendations).toHaveLength(2)
    expect(store.recommendations[0].skill).toBe('Rust')
    expect(store.recommendations[0].priority).toBe('high')
    expect(store.recommendations[1].priority).toBe('low')
    expect(request.get).toHaveBeenCalledWith('/learning/recommendations')
  })

  // ── 7. addSkillToPlan action ──

  it('should add a skill to the current plan', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
    vi.mocked(request.post).mockResolvedValueOnce({})
    // fetchPlan is called again after addSkillToPlan
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
    // fetchRecommendations is called after addSkillToPlan
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useLearningStore()
    await store.fetchPlan('plan-123')

    await store.addSkillToPlan('Rust', 'Backend Developer')

    expect(request.post).toHaveBeenCalledWith('/learning/plan/plan-123/skills', {
      skill_name: 'Rust',
      importance: 'bonus',
      estimated_hours: 20,
    })
  })

  it('should throw when no current plan exists on addSkillToPlan', async () => {
    const store = useLearningStore()
    await expect(store.addSkillToPlan('Rust', 'Backend Developer')).rejects.toThrow('请先创建学习计划')
  })

  // ── 8. runBatchMatch action ──

  it('should run batch match and set results', async () => {
    const request = (await import('@/api/request')).default
    const mockResults = {
      results: [
        { resume_name: 'Alice', position_name: 'Dev', match_score: 0.8, matched_skills: ['Python'], gap_skills: ['Docker'] },
      ],
    }
    vi.mocked(request.post).mockResolvedValueOnce(mockResults)

    const store = useLearningStore()
    const items = [{ skills: ['Python'], position: 'Dev' }]
    const results = await store.runBatchMatch(items)

    expect(results).toHaveLength(1)
    expect(store.batchResults).toHaveLength(1)
    expect(store.batchLoading).toBe(false)
    expect(request.post).toHaveBeenCalledWith('/match/batch', {
      items: [{ skills: ['Python'], position: 'Dev', position_name: 'Dev' }],
    })
  })

  // ── 9. fetchCompetitiveness action ──

  it('should fetch competitiveness data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      items: [
        { skill: 'Python', market_demand: 90, your_level: 3, avg_level: 4 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningStore()
    const result = await store.fetchCompetitiveness('Backend Developer')

    expect(result).toHaveLength(1)
    expect(store.competitiveness).toHaveLength(1)
    expect(store.competitivenessLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/match/competitiveness/Backend%20Developer')
  })

  // ── 10. fetchCareerPath action ──

  it('should fetch career path data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      path: [
        { position: 'Senior Dev', skills_required: ['Python'], estimated_time: '2 years', probability: 0.7 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningStore()
    const result = await store.fetchCareerPath('Backend Developer')

    expect(result).toHaveLength(1)
    expect(store.careerPath).toHaveLength(1)
    expect(store.careerPathLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/career-path/Backend%20Developer')
  })

  // ── 11. fetchIndustryTrends action ──

  it('should fetch industry trends data', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      items: [
        { skill: 'Rust', current_demand: 80, trend: 'rising', growth_rate: 0.3, avg_salary: 150000 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = useLearningStore()
    const result = await store.fetchIndustryTrends()

    expect(result).toHaveLength(1)
    expect(store.industryTrends).toHaveLength(1)
    expect(store.industryTrendsLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/industry-report')
  })

  // ── 12. restorePlanFromLocalStorage ──

  it('should restore plan from localStorage when valid plan_id exists', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(localStorage.getItem).mockReturnValueOnce('plan-123')
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeTruthy()
    expect(plan!.plan_id).toBe('plan-123')
    expect(store.currentPlan).toBeTruthy()
  })

  it('should return null when no stored plan_id exists', async () => {
    const store = useLearningStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeNull()
  })

  it('should clear stored plan_id when fetch fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(localStorage.getItem).mockReturnValueOnce('plan-invalid')
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useLearningStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeNull()
    expect(store.currentPlan).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalled()
  })

  // ── 13. Error handling ──

  it('should set error state when createPlan fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Server error'))

    const store = useLearningStore()
    await expect(store.createPlan({ position_name: 'Dev' })).rejects.toThrow('Server error')

    expect(store.error).toContain('创建学习计划失败')
    expect(store.loading).toBe(false)
  })

  it('should set error state when fetchPlan fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useLearningStore()
    await expect(store.fetchPlan('invalid')).rejects.toThrow('Not found')

    expect(store.error).toContain('获取学习计划失败')
    expect(store.loading).toBe(false)
  })

  it('should set error and clear recommendations when fetchRecommendations fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = useLearningStore()
    await store.fetchRecommendations()

    expect(store.error).toContain('获取推荐失败')
    expect(store.recommendations).toEqual([])
    expect(store.loading).toBe(false)
  })

  // ── 14. Loading state ──

  it('should toggle loading state during async operations', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.post).mockReturnValueOnce(pendingPromise as any)

    const store = useLearningStore()
    const actionPromise = store.createPlan({ position_name: 'Dev' })

    expect(store.loading).toBe(true)

    resolvePromise!({ plan_id: 'p1', position: 'Dev', skills: [] })
    await actionPromise

    expect(store.loading).toBe(false)
  })

  // ── Plan mapping ──

  it('should map plan response correctly with phases to path', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan!.skills).toHaveLength(3)
    expect(plan!.path).toHaveLength(3) // 2 from phase 1 + 1 from phase 2
    expect(plan!.overall_progress).toBe(0.45)
    expect(plan!.estimated_completion).toBe('8 周')
  })

  it('should handle plan response without phases', async () => {
    const request = (await import('@/api/request')).default
    const noPhasesResponse = { ...mockPlanResponse, phases: undefined }
    vi.mocked(request.get).mockResolvedValueOnce(noPhasesResponse)

    const store = useLearningStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan!.path).toEqual([])
  })

  it('should handle plan response with zero total_weeks', async () => {
    const request = (await import('@/api/request')).default
    const zeroWeeksResponse = { ...mockPlanResponse, total_weeks: 0 }
    vi.mocked(request.get).mockResolvedValueOnce(zeroWeeksResponse)

    const store = useLearningStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan!.estimated_completion).toBe('—')
  })
})
