import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

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

/** Extract error message from unknown catch value */
function getErrorMsg(e: unknown): string {
  if (e instanceof Error) return e.message
  if (typeof e === 'string') return e
  return '未知错误'
}

/** Narrow unknown API response to a typed object */
function asRecord(data: unknown): Record<string, unknown> {
  return (data && typeof data === 'object') ? data as Record<string, unknown> : {}
}

function asArray(data: unknown): unknown[] {
  return Array.isArray(data) ? data : []
}

export const useLearningAnalyticsStore = defineStore('learningAnalytics', () => {
  const analyticsError = ref<string | null>(null)

  // ── Competitiveness ──
  const competitiveness = ref<CompetitivenessData[]>([])
  const competitivenessLoading = ref(false)

  async function fetchCompetitiveness(position: string) {
    competitivenessLoading.value = true
    analyticsError.value = null
    try {
      const data = asRecord(await request.get(`/match/competitiveness/${encodeURIComponent(position)}`))
      competitiveness.value = (asArray(data.items ?? data.skills)) as CompetitivenessData[]
      return competitiveness.value
    } catch (e: unknown) {
      analyticsError.value = `获取竞争力数据失败: ${getErrorMsg(e)}`
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
    analyticsError.value = null
    try {
      const data = asRecord(await request.get(`/evolution/career-path/${encodeURIComponent(position)}`))
      careerPath.value = (asArray(data.path ?? data.steps)) as CareerPathStep[]
      return careerPath.value
    } catch (e: unknown) {
      analyticsError.value = `获取职业路径失败: ${getErrorMsg(e)}`
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
    analyticsError.value = null
    try {
      const data = asRecord(await request.get('/evolution/industry-report'))
      industryTrends.value = (asArray(data.items ?? data.trends)) as IndustryTrendItem[]
      return industryTrends.value
    } catch (e: unknown) {
      analyticsError.value = `获取行业趋势失败: ${getErrorMsg(e)}`
      industryTrends.value = []
    } finally {
      industryTrendsLoading.value = false
    }
  }

  return {
    analyticsError,
    competitiveness,
    competitivenessLoading,
    fetchCompetitiveness,
    careerPath,
    careerPathLoading,
    fetchCareerPath,
    industryTrends,
    industryTrendsLoading,
    fetchIndustryTrends,
  }
})
