/**
 * Learning plan store tests — covers plan CRUD + progress + restore + error handling + loading
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLearningPlanStore } from '../learningPlan'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    addParsedSkill: vi.fn(),
  })),
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

describe('useLearningPlanStore', () => {
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
    const store = useLearningPlanStore()
    expect(store.currentPlan).toBeNull()
    expect(store.plans).toEqual([])
    expect(store.planLoading).toBe(false)
    expect(store.planError).toBeNull()
  })

  // ── 2. createPlan action ──

  it('should create a plan and update state', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningPlanStore()
    const matchResult = { position_name: 'Backend Developer', match_score: 0.7, skill_gap_detail: [] }
    const plan = await store.createPlan(matchResult)

    expect(plan).toBeTruthy()
    expect(plan.plan_id).toBe('plan-123')
    expect(plan.position).toBe('Backend Developer')
    expect(store.currentPlan).toBeTruthy()
    expect(store.currentPlan!.plan_id).toBe('plan-123')
    expect(store.plans).toHaveLength(1)
    expect(store.planLoading).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalled()
  })

  // ── 3. fetchPlan action ──

  it('should fetch a plan and set currentPlan', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningPlanStore()
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
	    // Backend returns list[PlanResponse] — a plain JSON array
	    vi.mocked(request.get).mockResolvedValueOnce([mockPlanResponse])

	    const store = useLearningPlanStore()
	    const plans = await store.fetchPlans()

	    expect(plans).toHaveLength(1)
	    expect(store.plans).toHaveLength(1)
	    expect(store.plans[0].plan_id).toBe('plan-123')
	    // Should set currentPlan to first plan when none is set
	    expect(store.currentPlan).toBeTruthy()
	    expect(store.currentPlan!.plan_id).toBe('plan-123')
	  })

  // ── 5. updateProgress action ──

  it('should update progress and re-fetch plan for authoritative overall_pct', async () => {
	    const request = (await import('@/api/request')).default
	    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
	    vi.mocked(request.put).mockResolvedValueOnce({})
	    // updateProgress re-fetches the plan to get authoritative overall_pct
	    const updatedResponse = {
	      ...mockPlanResponse,
	      skills: mockPlanResponse.skills.map(s =>
	        s.skill_name === 'Docker' ? { ...s, status: 'mastered', progress_pct: 100 } : s
	      ),
	      overall_pct: 66.7,
	    }
	    vi.mocked(request.get).mockResolvedValueOnce(updatedResponse)

	    const store = useLearningPlanStore()
	    await store.fetchPlan('plan-123')
	    expect(store.currentPlan).toBeTruthy()

	    await store.updateProgress('plan-123', 'Docker', 'mastered')

	    // After re-fetch, skill status comes from backend response
	    const skillItem = store.currentPlan!.skills.find(s => s.skill === 'Docker')
	    expect(skillItem!.status).toBe('mastered')
	    expect(skillItem!.progress_pct).toBe(100)
	    expect(request.put).toHaveBeenCalledWith('/learning/plan/plan-123/progress', {
	      skill_name: 'Docker',
	      status: 'mastered',
	    })
	    // Re-fetch was called to get authoritative data
	    expect(request.get).toHaveBeenCalledWith('/learning/plan/plan-123')
	  })

	  it('should re-fetch plan when status changes to in_progress', async () => {
	    const request = (await import('@/api/request')).default
	    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
	    vi.mocked(request.put).mockResolvedValueOnce({})
	    // updateProgress re-fetches the plan
	    const updatedResponse = {
	      ...mockPlanResponse,
	      skills: mockPlanResponse.skills.map(s =>
	        s.skill_name === 'K8s' ? { ...s, status: 'in_progress', progress_pct: 10 } : s
	      ),
	    }
	    vi.mocked(request.get).mockResolvedValueOnce(updatedResponse)

	    const store = useLearningPlanStore()
	    await store.fetchPlan('plan-123')

	    await store.updateProgress('plan-123', 'K8s', 'in_progress')

	    const skillItem = store.currentPlan!.skills.find(s => s.skill === 'K8s')
	    expect(skillItem!.status).toBe('in_progress')
	    expect(skillItem!.progress_pct).toBe(10)
	  })

  // ── 6. addSkillToPlan action ──

  it('should add a skill to the current plan', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)
    vi.mocked(request.post).mockResolvedValueOnce({})
    // fetchPlan is called again after addSkillToPlan
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningPlanStore()
    await store.fetchPlan('plan-123')

    await store.addSkillToPlan('Rust', 'Backend Developer')

    expect(request.post).toHaveBeenCalledWith('/learning/plan/plan-123/skills', {
      skill_name: 'Rust',
      importance: 'bonus',
      estimated_hours: 20,
    })
  })

  it('should throw when no current plan exists on addSkillToPlan', async () => {
    const store = useLearningPlanStore()
    await expect(store.addSkillToPlan('Rust', 'Backend Developer')).rejects.toThrow('请先创建学习计划')
  })

  // ── 7. restorePlanFromLocalStorage ──

  it('should restore plan from localStorage when valid plan_id exists', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(localStorage.getItem).mockReturnValueOnce('plan-123')
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningPlanStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeTruthy()
    expect(plan!.plan_id).toBe('plan-123')
    expect(store.currentPlan).toBeTruthy()
  })

  it('should return null when no stored plan_id exists', async () => {
    const store = useLearningPlanStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeNull()
  })

  it('should clear stored plan_id when fetch fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(localStorage.getItem).mockReturnValueOnce('plan-invalid')
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useLearningPlanStore()
    const plan = await store.restorePlanFromLocalStorage()

    expect(plan).toBeNull()
    expect(store.currentPlan).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalled()
  })

  // ── 8. Error handling ──

  it('should set error state when createPlan fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Server error'))

    const store = useLearningPlanStore()
    await expect(store.createPlan({ position_name: 'Dev' })).rejects.toThrow('Server error')

    expect(store.planError).toContain('创建学习计划失败')
    expect(store.planLoading).toBe(false)
  })

  it('should set error state when fetchPlan fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useLearningPlanStore()
    await expect(store.fetchPlan('invalid')).rejects.toThrow('Not found')

    expect(store.planError).toContain('获取学习计划失败')
    expect(store.planLoading).toBe(false)
  })

  // ── 9. Loading state ──

  it('should toggle loading state during async operations', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.post).mockReturnValueOnce(pendingPromise as any)

    const store = useLearningPlanStore()
    const actionPromise = store.createPlan({ position_name: 'Dev' })

    expect(store.planLoading).toBe(true)

    resolvePromise!({ plan_id: 'p1', position: 'Dev', skills: [] })
    await actionPromise

    expect(store.planLoading).toBe(false)
  })

  // ── 10. Plan mapping ──

  it('should map plan response correctly with phases to path', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(mockPlanResponse)

    const store = useLearningPlanStore()
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

    const store = useLearningPlanStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan!.path).toEqual([])
  })

  it('should handle plan response with zero total_weeks', async () => {
    const request = (await import('@/api/request')).default
    const zeroWeeksResponse = { ...mockPlanResponse, total_weeks: 0 }
    vi.mocked(request.get).mockResolvedValueOnce(zeroWeeksResponse)

    const store = useLearningPlanStore()
    const plan = await store.fetchPlan('plan-123')

    expect(plan!.estimated_completion).toBe('—')
  })
})
