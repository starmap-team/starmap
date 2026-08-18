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
  position_name: string
  match_score: number
  matched_skills: string[]
  gap_skills: string[]
 // fix: 可选 error 字段，后端批量匹配对单条失败会带上此字段
  error?: string
}

interface BatchMatchRaw {
  position_name: string
 // 后端 BatchMatchResponse 单条结构：{ position_name, result: {...}, error?: string }
  result?: {
    match_score?: number
    matched_skills?: string[]
    gap_skills?: string[]
  }
  error?: string
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
 // P2 fix (functional-review 2026-08-13): 移除恒 undefined 的 market_demand ——
 // 后端 RecommendationItem 无此字段，前端 v-if="rec.market_demand" 永不渲染
 // （"需求 X%"标签形同虚设）。保留类型字段以便后端未来补充。
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

  async function fetchRecommendations(planId?: string, position?: string) {
    recLoading.value = true
    recError.value = null
    try {
 // P1 fix (functional-review 2026-08-13): 此前不带 plan_id/position 调用 →
 // 后端 get_recommendations 恒走 general trending 分支，页面文案宣称的
 // "基于差距分析生成个性化推荐"永不生效。传 plan_id 后走后端基于差距的
 // 个性化分支（LearningProgress 缺口排序）。
 // Backend returns RecommendationsResponse: { items: [...], total_items: number }
      const data = asRecord(await request.get('/learning/recommendations', {
        params: {
          ...(planId ? { plan_id: planId } : {}),
          ...(position ? { position } : {}),
        },
      }))
      const items = asArray(data.items)
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
 // fix: skills 必须是 PersonSkillInput 对象数组，与后端 BatchMatchItem.skills 对齐
      const payload = items.map(it => ({
        skills: it.skills.map(name => ({ name, proficiency: '熟悉' })),
        position: it.position,
        position_name: it.position,
      }))
      const data = asRecord(await request.post('/match/batch', { items: payload }))
 // fix: 后端返回 { results: [{ position_name, result: {...}, error? }] }，扁平化映射
      const rawItems = asArray(data.results ?? data.items)
      batchResults.value = (rawItems as unknown as BatchMatchRaw[]).map((r) => ({
        position_name: r.position_name,
        match_score: r.result?.match_score ?? 0,
        matched_skills: r.result?.matched_skills ?? [],
        gap_skills: r.result?.gap_skills ?? [],
        error: r.error,
      })) as BatchMatchItem[]
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
