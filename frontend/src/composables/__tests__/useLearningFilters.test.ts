/**
 * useLearningFilters composable tests — covers activeTab default,
 * all tab filters, empty skills, and reactive tab changes
 */
import { describe, it, expect } from 'vitest'
import { computed } from 'vue'
import { useLearningFilters } from '../useLearningFilters'
import type { SkillProgress } from '@/stores/learning'

function makeSkill(overrides: Partial<SkillProgress> = {}): SkillProgress {
  return {
    skill: 'Test',
    status: 'not_started',
    progress_pct: 0,
    estimated_hours: 10,
    prerequisites: [],
    current_level: 1,
    target_level: 3,
    ...overrides,
  }
}

describe('useLearningFilters', () => {
  // ── 1. Default tab ──

  it('should default activeTab to "all"', () => {
    const currentPlan = computed(() => ({ skills: [] }))
    const { activeTab } = useLearningFilters(currentPlan)

    expect(activeTab.value).toBe('all')
  })

  // ── 2. Filter by in_progress tab ──

  it('should filter skills to only in_progress when activeTab is "in_progress"', () => {
    const skills = [
      makeSkill({ skill: 'Python', status: 'mastered' }),
      makeSkill({ skill: 'Docker', status: 'in_progress' }),
      makeSkill({ skill: 'K8s', status: 'not_started' }),
    ]
    const currentPlan = computed(() => ({ skills }))
    const { activeTab, filteredSkills } = useLearningFilters(currentPlan)

    activeTab.value = 'in_progress'

    expect(filteredSkills.value).toHaveLength(1)
    expect(filteredSkills.value[0].skill).toBe('Docker')
  })

  // ── 3. All tab ──

  it('should return all skills when activeTab is "all"', () => {
    const skills = [
      makeSkill({ skill: 'Python', status: 'mastered' }),
      makeSkill({ skill: 'Docker', status: 'in_progress' }),
      makeSkill({ skill: 'K8s', status: 'not_started' }),
    ]
    const currentPlan = computed(() => ({ skills }))
    const { filteredSkills } = useLearningFilters(currentPlan)

    expect(filteredSkills.value).toHaveLength(3)
  })

  // ── 4. Mastered tab (not a valid tab per type, but test filtering logic) ──

  it('should return only mastered skills when activeTab is set to "mastered" via type cast', () => {
    const skills = [
      makeSkill({ skill: 'Python', status: 'mastered' }),
      makeSkill({ skill: 'Docker', status: 'in_progress' }),
      makeSkill({ skill: 'K8s', status: 'not_started' }),
    ]
    const currentPlan = computed(() => ({ skills }))
    const { activeTab, filteredSkills } = useLearningFilters(currentPlan)

    // The type only allows 'all' | 'in_progress' | 'not_started',
    // but the filter logic is `s.status === activeTab.value`
    // Setting to 'mastered' would filter by that status
    ;(activeTab as any).value = 'mastered'

    expect(filteredSkills.value).toHaveLength(1)
    expect(filteredSkills.value[0].skill).toBe('Python')
  })

  // ── 5. Not started tab ──

  it('should return only not_started skills when activeTab is "not_started"', () => {
    const skills = [
      makeSkill({ skill: 'Python', status: 'mastered' }),
      makeSkill({ skill: 'Docker', status: 'in_progress' }),
      makeSkill({ skill: 'K8s', status: 'not_started' }),
    ]
    const currentPlan = computed(() => ({ skills }))
    const { activeTab, filteredSkills } = useLearningFilters(currentPlan)

    activeTab.value = 'not_started'

    expect(filteredSkills.value).toHaveLength(1)
    expect(filteredSkills.value[0].skill).toBe('K8s')
  })

  // ── 6. Empty skills list ──

  it('should return empty array when plan has no skills', () => {
    const currentPlan = computed(() => ({ skills: [] }))
    const { filteredSkills } = useLearningFilters(currentPlan)

    expect(filteredSkills.value).toEqual([])
  })

  it('should return empty array when plan is null', () => {
    const currentPlan = computed(() => null)
    const { filteredSkills } = useLearningFilters(currentPlan)

    expect(filteredSkills.value).toEqual([])
  })

  // ── 7. Tab change reactivity ──

  it('should update filteredSkills reactively when activeTab changes', () => {
    const skills = [
      makeSkill({ skill: 'Python', status: 'mastered' }),
      makeSkill({ skill: 'Docker', status: 'in_progress' }),
      makeSkill({ skill: 'K8s', status: 'not_started' }),
    ]
    const currentPlan = computed(() => ({ skills }))
    const { activeTab, filteredSkills } = useLearningFilters(currentPlan)

    // Start with 'all'
    expect(filteredSkills.value).toHaveLength(3)

    // Switch to 'in_progress'
    activeTab.value = 'in_progress'
    expect(filteredSkills.value).toHaveLength(1)
    expect(filteredSkills.value[0].skill).toBe('Docker')

    // Switch to 'not_started'
    activeTab.value = 'not_started'
    expect(filteredSkills.value).toHaveLength(1)
    expect(filteredSkills.value[0].skill).toBe('K8s')

    // Switch back to 'all'
    activeTab.value = 'all'
    expect(filteredSkills.value).toHaveLength(3)
  })
})
