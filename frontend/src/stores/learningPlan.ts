import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

const LOCAL_STORAGE_KEY = 'starmap_learning_plan_id'

function readStoredPlanId(): string | null {
  try {
    return localStorage.getItem(LOCAL_STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStoredPlanId(planId: string | null): void {
  try {
    if (planId) localStorage.setItem(LOCAL_STORAGE_KEY, planId)
    else localStorage.removeItem(LOCAL_STORAGE_KEY)
  } catch {
    // localStorage unavailable — silent
  }
}

export interface SkillProgress {
  skill: string
  status: 'not_started' | 'in_progress' | 'mastered'
  progress_pct: number
  estimated_hours: number
  prerequisites: string[]
  current_level: number
  target_level: number
}

export interface LearningPathItem {
  skill: string
  status: 'not_started' | 'in_progress' | 'mastered'
  prerequisites: string[]
  estimated_hours: number
  progress_pct: number
}

export interface LearningPlan {
  plan_id: string
  position: string
  overall_progress: number
  estimated_completion: string
  skills: SkillProgress[]
  path: LearningPathItem[]
  created_at?: string
  updated_at?: string
}

// ── Backend response shapes (untyped API → narrow at boundary) ──

interface PlanSkillRaw {
  skill_name?: string
  skill?: string
  status?: string
  progress_pct?: number
  estimated_hours?: number
  prerequisites?: string[]
  importance?: string
}

interface PlanPhaseRaw {
  skills?: string[]
}

interface PlanResponseRaw {
  plan_id: string
  position: string
  overall_pct?: number
  total_weeks?: number
  skills?: PlanSkillRaw[]
  phases?: PlanPhaseRaw[]
  stats?: { created_at?: string; updated_at?: string }
}

/** Extract error message from unknown catch value */
function getErrorMsg(e: unknown): string {
  if (e instanceof Error) return e.message
  if (typeof e === 'string') return e
  return '未知错误'
}

/** Map backend PlanResponse to frontend LearningPlan */
function mapPlanResponse(data: PlanResponseRaw): LearningPlan {
  const skills: SkillProgress[] = (data.skills ?? []).map((s) => ({
    skill: s.skill_name ?? s.skill ?? '',
    status: (s.status as SkillProgress['status']) ?? 'not_started',
    progress_pct: s.progress_pct ?? 0,
    estimated_hours: s.estimated_hours ?? 0,
    prerequisites: s.prerequisites ?? [],
    current_level: s.importance === 'required' ? 2 : 1,
    target_level: s.importance === 'required' ? 5 : 3,
  }))

  const path: LearningPathItem[] = (data.phases ?? []).flatMap((phase) =>
    (phase.skills ?? []).map((skillName) => {
      const skillData = skills.find(sk => sk.skill === skillName)
      return {
        skill: skillName,
        status: skillData?.status ?? 'not_started',
        prerequisites: skillData?.prerequisites ?? [],
        estimated_hours: skillData?.estimated_hours ?? 0,
        progress_pct: skillData?.progress_pct ?? 0,
      }
    })
  )

  const stats = data.stats ?? {}
  const totalWeeks = data.total_weeks ?? 0
  const estimatedCompletion = totalWeeks > 0
    ? `${Math.ceil(totalWeeks)} 周`
    : '—'

  return {
    plan_id: data.plan_id,
    position: data.position,
    overall_progress: Math.round((data.overall_pct ?? 0) * 100) / 100,
    estimated_completion: estimatedCompletion,
    skills,
    path,
    created_at: stats.created_at,
    updated_at: stats.updated_at,
  }
}

/** Narrow unknown API response to a typed object */
function asRecord(data: unknown): Record<string, unknown> {
  return (data && typeof data === 'object') ? data as Record<string, unknown> : {}
}

function asArray(data: unknown): unknown[] {
  return Array.isArray(data) ? data : []
}

// ── CreatePlanRequest: 前端→后端请求体类型安全映射 ──

/** 后端 CreatePlanRequest 对应的前端类型 */
export interface CreatePlanRequestBody {
  position: string
  match_score: number
  skills: Array<{
    skill: string
    importance: string
    gap_level: string
    learning_path: string[]
    target_proficiency?: string
  }>
  available_hours_per_week?: number
}

/** 从匹配结果构造 CreatePlanRequest 请求体 (LOOP-03) */
export function buildCreatePlanRequest(matchResult: Record<string, unknown>): CreatePlanRequestBody {
  const position = (matchResult.position_name ?? matchResult.position ?? '') as string
  const matchScore = (matchResult.match_score ?? 0) as number
  const gapDetail = (matchResult.skill_gap_detail ?? []) as Array<Record<string, unknown>>
  const skills = gapDetail.map((gap) => ({
    skill: (gap.skill ?? gap.skill_name ?? '') as string,
    importance: (gap.importance ?? 'required') as string,
    gap_level: (gap.gap_level ?? '完全缺失') as string,
    learning_path: (Array.isArray(gap.learning_path) ? gap.learning_path : []) as string[],
    target_proficiency: (gap.target_proficiency ?? '熟悉') as string,
  }))
  return {
    position: position || '未知岗位',
    match_score: matchScore,
    skills: skills.length > 0 ? skills : [{ skill: '通用技能', importance: 'required', gap_level: '完全缺失', learning_path: [] }],
    available_hours_per_week: 10.0,
  }
}

export const useLearningPlanStore = defineStore('learningPlan', () => {
  const plans = ref<LearningPlan[]>([])
  const currentPlan = ref<LearningPlan | null>(null)
  const planLoading = ref(false)
  const planError = ref<string | null>(null)

  async function createPlan(matchResult: Record<string, unknown>) {
    planLoading.value = true
    planError.value = null
    try {
      const payload = buildCreatePlanRequest(matchResult)
      const data = await request.post('/learning/plan', payload)
      const plan = mapPlanResponse(asRecord(data) as unknown as PlanResponseRaw)
      currentPlan.value = plan
      plans.value.unshift(plan)
      writeStoredPlanId(plan.plan_id)
      return plan
    } catch (e: unknown) {
      planError.value = `创建学习计划失败: ${getErrorMsg(e)}`
      throw e
    } finally {
      planLoading.value = false
    }
  }

  async function fetchPlan(planId: string) {
    planLoading.value = true
    planError.value = null
    try {
      const data = await request.get(`/learning/plan/${planId}`)
      const plan = mapPlanResponse(asRecord(data) as unknown as PlanResponseRaw)
      currentPlan.value = plan
      writeStoredPlanId(plan.plan_id)
      return plan
    } catch (e: unknown) {
      planError.value = `获取学习计划失败: ${getErrorMsg(e)}`
      throw e
    } finally {
      planLoading.value = false
    }
  }

  /** D-06/D-07: restore plan from localStorage on page open.
   * Validates stored plan_id by fetching; clears on 404/invalid.
   */
  async function restorePlanFromLocalStorage(): Promise<LearningPlan | null> {
    const storedId = readStoredPlanId()
    if (!storedId) return null
    try {
      return await fetchPlan(storedId)
    } catch {
      writeStoredPlanId(null)
      currentPlan.value = null
      return null
    }
  }

  async function updateProgress(planId: string, skill: string, status: string) {
    planLoading.value = true
    planError.value = null
    try {
      await request.put(`/learning/plan/${planId}/progress`, { skill_name: skill, status })
      if (currentPlan.value?.plan_id === planId) {
        const skillItem = currentPlan.value.skills.find(s => s.skill === skill)
        if (skillItem) {
          skillItem.status = status as SkillProgress['status']
          if (status === 'mastered') skillItem.progress_pct = 100
          else if (status === 'in_progress' && skillItem.progress_pct === 0) skillItem.progress_pct = 10
        }
        const total = currentPlan.value.skills.length
        const mastered = currentPlan.value.skills.filter(s => s.status === 'mastered').length
        const inProgress = currentPlan.value.skills.filter(s => s.status === 'in_progress').length
        currentPlan.value.overall_progress = total > 0
          ? Math.round(((mastered + inProgress * 0.5) / total) * 100)
          : 0
      }
    } catch (e: unknown) {
      planError.value = `更新进度失败: ${getErrorMsg(e)}`
      throw e
    } finally {
      planLoading.value = false
    }
  }

  async function fetchPlans() {
    planLoading.value = true
    planError.value = null
    try {
      const data = asRecord(await request.get('/learning/plans'))
      const items = asArray(data.items ?? data.plans)
      plans.value = items.map((p) => mapPlanResponse(p as PlanResponseRaw))
      if (plans.value.length > 0 && !currentPlan.value) {
        currentPlan.value = plans.value[0]
      }
      return plans.value
    } catch (e: unknown) {
      planError.value = `获取学习计划失败: ${getErrorMsg(e)}`
      plans.value = []
      currentPlan.value = null
      return []
    } finally {
      planLoading.value = false
    }
  }

  async function addSkillToPlan(skillId: string, _targetPosition: string) {
    if (!currentPlan.value) {
      throw new Error('请先创建学习计划')
    }
    planLoading.value = true
    planError.value = null
    try {
      await request.post(`/learning/plan/${currentPlan.value.plan_id}/skills`, {
        skill_name: skillId,
        importance: 'bonus',
        estimated_hours: 20,
      })
      await fetchPlan(currentPlan.value.plan_id)
    } catch (e: unknown) {
      planError.value = `添加技能到计划失败: ${getErrorMsg(e)}`
      throw e
    } finally {
      planLoading.value = false
    }
  }

  return {
    plans,
    currentPlan,
    planLoading,
    planError,
    createPlan,
    fetchPlan,
    fetchPlans,
    addSkillToPlan,
    updateProgress,
    restorePlanFromLocalStorage,
  }
})
