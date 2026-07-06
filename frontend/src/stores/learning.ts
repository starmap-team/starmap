import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

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

export interface Recommendation {
  skill: string
  reason: string
  priority: 'high' | 'medium' | 'low'
  estimated_hours: number
  market_demand?: number
}

export interface BatchMatchItem {
  resume_name: string
  position_name: string
  match_score: number
  matched_skills: string[]
  gap_skills: string[]
}

export interface CompetitivenessData {
  skill: string
  market_demand: number
  your_level: number
  avg_level: number
}

export interface CareerPathStep {
  position: string
  skills_required: string[]
  estimated_time: string
  probability: number
}

export interface IndustryTrendItem {
  skill: string
  current_demand: number
  trend: 'rising' | 'stable' | 'declining'
  growth_rate: number
  avg_salary?: number
}

/** Map backend PlanResponse to frontend LearningPlan */
function mapPlanResponse(data: any): LearningPlan {
  const skills: SkillProgress[] = (data.skills ?? []).map((s: any) => ({
    skill: s.skill_name ?? s.skill ?? '',
    status: s.status ?? 'not_started',
    progress_pct: s.progress_pct ?? 0,
    estimated_hours: s.estimated_hours ?? 0,
    prerequisites: s.prerequisites ?? [],
    current_level: s.importance === 'required' ? 2 : 1,
    target_level: s.importance === 'required' ? 5 : 3,
  }))

  const path: LearningPathItem[] = (data.phases ?? []).flatMap((phase: any) =>
    (phase.skills ?? []).map((skillName: string) => {
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

/** Map backend RecommendationItem to frontend Recommendation */
function mapRecommendation(rec: any): Recommendation {
  return {
    skill: rec.skill,
    reason: rec.reason ?? '',
    priority: rec.importance === 'required' ? 'high' : rec.importance === 'bonus' ? 'low' : 'medium',
    estimated_hours: rec.estimated_hours ?? 0,
    market_demand: undefined,
  }
}

export const useLearningStore = defineStore('learning', () => {
  const plans = ref<LearningPlan[]>([])
  const currentPlan = ref<LearningPlan | null>(null)
  const recommendations = ref<Recommendation[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function createPlan(matchResult: any) {
    loading.value = true
    error.value = null
    try {
      const data = await request.post('/learning/plan', matchResult) as any
      const plan = mapPlanResponse(data)
      currentPlan.value = plan
      plans.value.unshift(plan)
      return plan
    } catch (e: any) {
      error.value = e?.message ?? '创建学习计划失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchPlan(planId: string) {
    loading.value = true
    error.value = null
    try {
      const data = await request.get(`/learning/plan/${planId}`) as any
      const plan = mapPlanResponse(data)
      currentPlan.value = plan
      return plan
    } catch (e: any) {
      error.value = e?.message ?? '获取学习计划失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateProgress(planId: string, skill: string, status: string) {
    loading.value = true
    error.value = null
    try {
      await request.put(`/learning/plan/${planId}/progress`, { skill_name: skill, status })
      // Update local state
      if (currentPlan.value?.plan_id === planId) {
        const skillItem = currentPlan.value.skills.find(s => s.skill === skill)
        if (skillItem) {
          skillItem.status = status as SkillProgress['status']
          if (status === 'mastered') skillItem.progress_pct = 100
          else if (status === 'in_progress' && skillItem.progress_pct === 0) skillItem.progress_pct = 10
        }
        // Recalculate overall progress
        const total = currentPlan.value.skills.length
        const mastered = currentPlan.value.skills.filter(s => s.status === 'mastered').length
        const inProgress = currentPlan.value.skills.filter(s => s.status === 'in_progress').length
        currentPlan.value.overall_progress = total > 0
          ? Math.round(((mastered + inProgress * 0.5) / total) * 100)
          : 0
      }
    } catch (e: any) {
      error.value = e?.message ?? '更新进度失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchRecommendations() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/learning/recommendations') as any
      const items = data.items ?? data.recommendations ?? []
      recommendations.value = items.map(mapRecommendation)
    } catch (e: any) {
      error.value = e?.message ?? '获取推荐失败'
      recommendations.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchPlans() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/learning/plans') as any
      const items: any[] = Array.isArray(data) ? data : (data.items ?? data.plans ?? [])
      plans.value = items.map(mapPlanResponse)
      if (plans.value.length > 0 && !currentPlan.value) {
        currentPlan.value = plans.value[0]
      }
      return plans.value
    } catch (e: any) {
      error.value = e?.message ?? '获取学习计划失败'
      plans.value = []
      currentPlan.value = null
      return []
    } finally {
      loading.value = false
    }
  }

  async function addSkillToPlan(skillId: string, _targetPosition: string) {
    if (!currentPlan.value) {
      throw new Error('请先创建学习计划')
    }
    loading.value = true
    error.value = null
    try {
      // Add skill to existing plan via dedicated endpoint
      await request.post(`/learning/plan/${currentPlan.value.plan_id}/skills`, {
        skill_name: skillId,
        importance: 'bonus',
        estimated_hours: 20,
      })
      // Refresh the plan to get updated data
      await fetchPlan(currentPlan.value.plan_id)
      // Also refresh recommendations
      await fetchRecommendations()
    } catch (e: any) {
      error.value = e?.message ?? '添加技能到计划失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  // ── Batch match ──
  const batchResults = ref<BatchMatchItem[]>([])
  const batchLoading = ref(false)

  async function runBatchMatch(items: { resume_text?: string; skills: string[]; position: string }[]) {
    batchLoading.value = true
    error.value = null
    try {
      // 兼容后端：同时发送 position 和 position_name，避免字段不匹配导致 target_position 恒为空
      const payload = items.map(it => ({ skills: it.skills, position: it.position, position_name: it.position }))
      const data = await request.post('/match/batch', { items: payload }) as any
      batchResults.value = data.results ?? data.items ?? []
      return batchResults.value
    } catch (e: any) {
      error.value = e?.message ?? '批量匹配失败'
      throw e
    } finally {
      batchLoading.value = false
    }
  }

  // ── Competitiveness ──
  const competitiveness = ref<CompetitivenessData[]>([])
  const competitivenessLoading = ref(false)

  async function fetchCompetitiveness(position: string) {
    competitivenessLoading.value = true
    error.value = null
    try {
      const data = await request.get(`/match/competitiveness/${encodeURIComponent(position)}`) as any
      competitiveness.value = data.items ?? data.skills ?? []
      return competitiveness.value
    } catch (e: any) {
      error.value = e?.message ?? '获取竞争力数据失败'
      competitiveness.value = []
    } finally {
      competitivenessLoading.value = false
    }
  }

  // ── Career path ──
  const careerPath = ref<CareerPathStep[]>([])
  const careerPathLoading = ref(false)

  async function fetchCareerPath(position: string) {
    careerPathLoading.value = true
    error.value = null
    try {
      const data = await request.get(`/evolution/career-path/${encodeURIComponent(position)}`) as any
      careerPath.value = data.path ?? data.steps ?? []
      return careerPath.value
    } catch (e: any) {
      error.value = e?.message ?? '获取职业路径失败'
      careerPath.value = []
    } finally {
      careerPathLoading.value = false
    }
  }

  // ── Industry trends ──
  const industryTrends = ref<IndustryTrendItem[]>([])
  const industryTrendsLoading = ref(false)

  async function fetchIndustryTrends() {
    industryTrendsLoading.value = true
    error.value = null
    try {
      const data = await request.get('/evolution/industry-report') as any
      industryTrends.value = data.items ?? data.trends ?? []
      return industryTrends.value
    } catch (e: any) {
      error.value = e?.message ?? '获取行业趋势失败'
      industryTrends.value = []
    } finally {
      industryTrendsLoading.value = false
    }
  }

  return {
    // Learning plan
    plans,
    currentPlan,
    recommendations,
    loading,
    error,
    createPlan,
    fetchPlan,
    fetchPlans,
    addSkillToPlan,
    updateProgress,
    fetchRecommendations,
    // Batch match
    batchResults,
    batchLoading,
    runBatchMatch,
    // Competitiveness
    competitiveness,
    competitivenessLoading,
    fetchCompetitiveness,
    // Career path
    careerPath,
    careerPathLoading,
    fetchCareerPath,
    // Industry trends
    industryTrends,
    industryTrendsLoading,
    fetchIndustryTrends,
  }
})
