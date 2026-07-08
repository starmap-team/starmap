/**
 * LearningCenter tab state + filtered skill list — extracted from LearningCenter.vue
 * (Phase 7 D round 10). Pure: takes a currentPlan computed, returns activeTab ref
 * and filteredSkills computed.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { SkillProgress } from '@/stores/learning'

export type LearningTab = 'all' | 'in_progress' | 'not_started'

export interface LearningFiltersApi {
  activeTab: Ref<LearningTab>
  filteredSkills: ComputedRef<SkillProgress[]>
}

export function useLearningFilters(
  currentPlan: ComputedRef<{ skills: SkillProgress[] } | null>,
): LearningFiltersApi {
  const activeTab: Ref<LearningTab> = ref<LearningTab>('all')

  const filteredSkills: ComputedRef<SkillProgress[]> = computed(() => {
    const plan = currentPlan.value
    if (!plan) return []
    if (activeTab.value === 'all') return plan.skills
    return plan.skills.filter(s => s.status === activeTab.value)
  })

  return { activeTab, filteredSkills }
}
