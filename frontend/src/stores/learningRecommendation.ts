import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

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

interface RecommendationRaw {
  skill: string
  reason?: string
  importance?: string
  estimated_hours?: number
}

/** Extract error message from unknown catch value */
function getErrorMsg(e: unknown): string {
  if (e instanceof Error) return e.message
  if (typeof e === 'string') return e
  return '未知错误'
}

/** Map backend RecommendationItem to frontend Recommendation */
function mapRecommendation(rec: RecommendationRaw): Recommendation {
  return {
    skill: rec.skill,
    reason: rec.reason ?? '',
    priority: rec.importance === 'required' ? 'high' : rec.importance === 'bonus' ? 'low' : 'medium',
    estimated_hours: rec.estimated_hours ?? 0,
    market_demand: undefined,
  }
}

/** Narrow unknown API response to a typed object */
function asRecord(data: unknown): Record<string, unknown> {
  return (data && typeof data === 'object') ? data as Record<string, unknown> : {}
}

function asArray(data: unknown): unknown[] {
  return Array.isArray(data) ? data : []
}

export const useLearningRecommendationStore = defineStore('learningRecommendation', () => {
  const recommendations = ref<Recommendation[]>([])
  const recLoading = ref(false)
  const recError = ref<string | null>(null)

  async function fetchRecommendations() {
    recLoading.value = true
    recError.value = null
    try {
      const data = asRecord(await request.get('/learning/recommendations'))
      const items = asArray(data.items ?? data.recommendations)
      recommendations.value = items.map((r) => mapRecommendation(r as RecommendationRaw))
    } catch (e: unknown) {
      recError.value = `获取推荐失败: ${getErrorMsg(e)}`
      recommendations.value = []
    } finally {
      recLoading.value = false
    }
  }

  // ── Batch match ──
  const batchResults = ref<BatchMatchItem[]>([])
  const batchLoading = ref(false)

  async function runBatchMatch(items: { resume_text?: string; skills: string[]; position: string }[]) {
    batchLoading.value = true
    recError.value = null
    try {
      const payload = items.map(it => ({ skills: it.skills, position: it.position, position_name: it.position }))
      const data = asRecord(await request.post('/match/batch', { items: payload }))
      batchResults.value = (asArray(data.results ?? data.items)) as BatchMatchItem[]
      return batchResults.value
    } catch (e: unknown) {
      recError.value = `批量匹配失败: ${getErrorMsg(e)}`
      throw e
    } finally {
      batchLoading.value = false
    }
  }

  return {
    recommendations,
    recLoading,
    recError,
    fetchRecommendations,
    batchResults,
    batchLoading,
    runBatchMatch,
  }
})
