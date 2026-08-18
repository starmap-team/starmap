// Barrel re-export — backward-compatible combined store
export { useLearningPlanStore } from './learningPlan'
export { useLearningRecommendationStore } from './learningRecommendation'
export { useLearningAnalyticsStore } from './learningAnalytics'

// Re-export types that consumers import from this module
export type { SkillProgress, LearningPathItem, LearningPlan, CreatePlanRequestBody } from './learningPlan'
export { buildCreatePlanRequest } from './learningPlan'
export type { Recommendation, BatchMatchItem } from './learningRecommendation'
export type { CompetitivenessData, CareerPathStep, IndustryTrendItem } from './learningAnalytics'

import { useLearningPlanStore } from './learningPlan'
import { useLearningRecommendationStore } from './learningRecommendation'
import { useLearningAnalyticsStore } from './learningAnalytics'
import { computed, reactive } from 'vue'
import { storeToRefs } from 'pinia'

/**
 * Backward-compatible combined store.
 * Merges the three split stores into a single interface so existing consumers
 * can keep using `useLearningStore` without changes.
 *
 * `loading` and `error` are computed from the sub-stores to preserve the
 * original "any loading / any error" semantics.
 *
 * DEF-002 fix: 此前直接 `batchResults: rec.batchResults` 会把 Pinia ref 解包成
 * 一次性值快照（setup 时取值），后续子 store `.value = [...]` 替换不传导，
 * 导致批量匹配结果/竞争力图表恒显示旧数据。现改用 `storeToRefs` 保留 ref，
 * 并用 `reactive` 包装返回对象（深度解包 ref + 保持响应式），模板
 * `learningStore.batchResults` 读到的仍是数组值，但与子 store 联动更新。
 */
export const useLearningStore = () => {
  const plan = useLearningPlanStore()
  const rec = useLearningRecommendationStore()
  const analytics = useLearningAnalyticsStore()

 // storeToRefs 保留 ref 语义；reactive 深度解包，模板可直接取数组/对象值
  const { batchResults, batchLoading, recommendations, recLoading, recError } = storeToRefs(rec)
  const { competitiveness, competitivenessLoading, careerPath, careerPathLoading, industryTrends, industryTrendsLoading } = storeToRefs(analytics)
  const { plans, currentPlan, planLoading, planError } = storeToRefs(plan)

  const loading = computed(() => planLoading.value || recLoading.value || competitivenessLoading.value || careerPathLoading.value || industryTrendsLoading.value)
  const error = computed(() => planError.value || recError.value || analytics.analyticsError)

  return reactive({
 // Learning plan
    plans,
    currentPlan,
    createPlan: plan.createPlan,
    fetchPlan: plan.fetchPlan,
    fetchPlans: plan.fetchPlans,
    addSkillToPlan: plan.addSkillToPlan,
    updateProgress: plan.updateProgress,
    restorePlanFromLocalStorage: plan.restorePlanFromLocalStorage,
 // Recommendations
    recommendations,
    fetchRecommendations: rec.fetchRecommendations,
 // Batch match
    batchResults,
    batchLoading,
    runBatchMatch: rec.runBatchMatch,
 // Competitiveness
    competitiveness,
    competitivenessLoading,
    fetchCompetitiveness: analytics.fetchCompetitiveness,
 // Career path
    careerPath,
    careerPathLoading,
    fetchCareerPath: analytics.fetchCareerPath,
 // Industry trends
    industryTrends,
    industryTrendsLoading,
    fetchIndustryTrends: analytics.fetchIndustryTrends,
 // Combined loading/error
    loading,
    error,
  })
}
