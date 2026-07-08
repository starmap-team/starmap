/**
 * LearningCenter progress metrics — extracted from LearningCenter.vue (Phase 7 D)
 * Pure computeds over currentPlan, no store mutations.
 */
import { computed, type ComputedRef } from 'vue'
import type { SkillProgress } from '@/stores/learning'

export interface LearningMetrics {
  masteredCount: ComputedRef<number>
  inProgressCount: ComputedRef<number>
  totalHours: ComputedRef<number>
  remainingHours: ComputedRef<number>
}

export function useLearningMetrics(currentPlan: ComputedRef<{ skills: SkillProgress[] } | null>): LearningMetrics {
  const masteredCount: ComputedRef<number> = computed(
    () => currentPlan.value?.skills.filter(s => s.status === 'mastered').length ?? 0,
  )
  const inProgressCount: ComputedRef<number> = computed(
    () => currentPlan.value?.skills.filter(s => s.status === 'in_progress').length ?? 0,
  )
  const totalHours: ComputedRef<number> = computed(
    () => currentPlan.value?.skills.reduce((sum, s) => sum + s.estimated_hours, 0) ?? 0,
  )
  const remainingHours: ComputedRef<number> = computed(() => {
    if (!currentPlan.value) return 0
    return currentPlan.value.skills
      .filter(s => s.status !== 'mastered')
      .reduce((sum, s) => sum + Math.round(s.estimated_hours * (1 - s.progress_pct / 100)), 0)
  })

  return { masteredCount, inProgressCount, totalHours, remainingHours }
}
