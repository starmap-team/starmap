/**
 * useLearningActions composable tests — covers handleUpdateStatus,
 * handleAddToPlan, success/error messages, confirmation dialog, and loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn(),
  },
}))

// Mock the user store
vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    addParsedSkill: vi.fn(),
  })),
}))

// Mock the learning store's buildCreatePlanRequest
vi.mock('@/stores/learning', async () => {
  const actual = await vi.importActual<typeof import('@/stores/learning')>('@/stores/learning')
  return {
    ...actual,
    useLearningStore: vi.fn(),
  }
})

import { ElMessage, ElMessageBox } from 'element-plus'
import { useLearningActions } from '../useLearningActions'

function createMockStore() {
  return {
    updateProgress: vi.fn(),
    createPlan: vi.fn(),
    currentPlan: ref(null),
    plans: ref([]),
    recommendations: ref([]),
    loading: ref(false),
    error: ref(null),
    batchResults: ref([]),
    batchLoading: ref(false),
    competitiveness: ref([]),
    competitivenessLoading: ref(false),
    careerPath: ref([]),
    careerPathLoading: ref(false),
    industryTrends: ref([]),
    industryTrendsLoading: ref(false),
    fetchPlan: vi.fn(),
    fetchPlans: vi.fn(),
    addSkillToPlan: vi.fn(),
    fetchRecommendations: vi.fn(),
    restorePlanFromLocalStorage: vi.fn(),
    runBatchMatch: vi.fn(),
    fetchCompetitiveness: vi.fn(),
    fetchCareerPath: vi.fn(),
    fetchIndustryTrends: vi.fn(),
  } as any
}

describe('useLearningActions', () => {
  let mockStore: ReturnType<typeof createMockStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    mockStore = createMockStore()
    vi.mocked(ElMessage.success).mockClear()
    vi.mocked(ElMessage.error).mockClear()
    vi.mocked(ElMessage.warning).mockClear()
    vi.mocked(ElMessageBox.confirm).mockClear()
  })

  // ── 1. handleUpdateStatus ──

  it('should call store.updateProgress with correct args', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    mockStore.updateProgress.mockResolvedValueOnce(undefined)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('Python', 'mastered')

    expect(mockStore.updateProgress).toHaveBeenCalledWith('plan-1', 'Python', 'mastered')
  })

  it('should show success message after updating status', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    mockStore.updateProgress.mockResolvedValueOnce(undefined)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('Python', 'mastered')

    expect(ElMessage.success).toHaveBeenCalledWith('已更新「Python」状态为 已掌握')
  })

  it('should show correct label for in_progress status', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    mockStore.updateProgress.mockResolvedValueOnce(undefined)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('Docker', 'in_progress')

    expect(ElMessage.success).toHaveBeenCalledWith('已更新「Docker」状态为 学习中')
  })

  it('should show correct label for not_started status', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    mockStore.updateProgress.mockResolvedValueOnce(undefined)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('K8s', 'not_started')

    expect(ElMessage.success).toHaveBeenCalledWith('已更新「K8s」状态为 未开始')
  })

  // ── 2. Warning when no plan ──

  it('should show warning when no current plan on handleUpdateStatus', async () => {
    const currentPlan = ref(null)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('Python', 'mastered')

    expect(ElMessage.warning).toHaveBeenCalledWith('请先创建学习计划')
    expect(mockStore.updateProgress).not.toHaveBeenCalled()
  })

  // ── 3. Mastered skill adds to user parsed skills ──

  it('should show extra message when skill is mastered', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    mockStore.updateProgress.mockResolvedValueOnce(undefined)

    const { handleUpdateStatus } = useLearningActions(mockStore, currentPlan)
    await handleUpdateStatus('Python', 'mastered')

    // Should show two success messages: one for status update, one for mastered notification
    expect(ElMessage.success).toHaveBeenCalledTimes(2)
  })

  // ── 4. handleAddToPlan ──

  it('should create a new plan when no current plan exists', async () => {
    const currentPlan = ref(null)
    mockStore.createPlan.mockResolvedValueOnce({ plan_id: 'new-plan' })

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(mockStore.createPlan).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('「Rust」已加入学习计划')
  })

  // ── 5. Confirmation dialog when plan exists ──

  it('should show confirmation dialog when current plan exists and user confirms', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Backend Dev' })
    vi.mocked(ElMessageBox.confirm).mockResolvedValueOnce('confirm' as any)
    mockStore.createPlan.mockResolvedValueOnce({ plan_id: 'new-plan' })

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '已有学习计划「Backend Dev」，是否用「Rust」覆盖？',
      '覆盖学习计划',
      { confirmButtonText: '确认覆盖', cancelButtonText: '取消', type: 'warning' },
    )
    expect(mockStore.createPlan).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('已创建新学习计划')
  })

  it('should not create plan when user cancels confirmation', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Backend Dev' })
    vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel')

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(mockStore.createPlan).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  // ── 6. Error message on failure ──

  it('should show error message when createPlan throws', async () => {
    const currentPlan = ref(null)
    mockStore.createPlan.mockRejectedValueOnce(new Error('Server error'))

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(ElMessage.error).toHaveBeenCalledWith('Server error')
  })

  it('should show generic error message for non-Error throws', async () => {
    const currentPlan = ref(null)
    mockStore.createPlan.mockRejectedValueOnce('string error')

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(ElMessage.error).toHaveBeenCalledWith('加入计划失败')
  })

  it('should not show error when user closes dialog (close event)', async () => {
    const currentPlan = ref({ plan_id: 'plan-1', position: 'Dev' })
    vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('close')

    const { handleAddToPlan } = useLearningActions(mockStore, currentPlan)
    await handleAddToPlan({ skill: 'Rust', priority: 'required' })

    expect(ElMessage.error).not.toHaveBeenCalled()
  })
})
