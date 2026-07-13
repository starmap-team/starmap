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
import { computed } from 'vue'

/**
 * Backward-compatible combined store.
 * Merges the three split stores into a single interface so existing consumers
 * can keep using `useLearningStore()` without changes.
 *
 * `loading` and `error` are computed from the sub-stores to preserve the
 * original "any loading / any error" semantics.
 */
export const useLearningStore = () => {
  const plan = useLearningPlanStore()
  const rec = useLearningRecommendationStore()
  const analytics = useLearningAnalyticsStore()

  const loading = computed(() => plan.planLoading || rec.recLoading || analytics.competitivenessLoading || analytics.careerPathLoading || analytics.industryTrendsLoading)
  const error = computed(() => plan.planError || rec.recError || analytics.analyticsError)

  return {
    // Learning plan
    plans: plan.plans,
    currentPlan: plan.currentPlan,
    createPlan: plan.createPlan,
    fetchPlan: plan.fetchPlan,
    fetchPlans: plan.fetchPlans,
    addSkillToPlan: plan.addSkillToPlan,
    updateProgress: plan.updateProgress,
    restorePlanFromLocalStorage: plan.restorePlanFromLocalStorage,
    // Recommendations
    recommendations: rec.recommendations,
    fetchRecommendations: rec.fetchRecommendations,
    // Batch match
    batchResults: rec.batchResults,
    batchLoading: rec.batchLoading,
    runBatchMatch: rec.runBatchMatch,
    // Competitiveness
    competitiveness: analytics.competitiveness,
    competitivenessLoading: analytics.competitivenessLoading,
    fetchCompetitiveness: analytics.fetchCompetitiveness,
    // Career path
    careerPath: analytics.careerPath,
    careerPathLoading: analytics.careerPathLoading,
    fetchCareerPath: analytics.fetchCareerPath,
    // Industry trends
    industryTrends: analytics.industryTrends,
    industryTrendsLoading: analytics.industryTrendsLoading,
    fetchIndustryTrends: analytics.fetchIndustryTrends,
    // Combined loading/error
    loading,
    error,
  }
}
