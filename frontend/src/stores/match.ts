import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface PersonSkill {
  skill_id: string
  name: string
  category: 'hard_skill' | 'soft_skill' | 'tool' | 'certificate'
  proficiency: string
  confidence?: number
}

export interface SkillGap {
  skill: string
  importance: 'required' | 'bonus'
  gap_level: string
  learning_path: string[]
}

export interface MatchResult {
  match_score: number
  matched_skills: string[]
  gap_skills: string[]
  recommendations: string[]
  target_position?: string
  missing_required?: string[]
  missing_bonus?: string[]
  skill_gap_detail?: SkillGap[]
  overall_assessment?: string
  estimated_learning_time?: string
}

export interface PositionSkills {
  position_name: string
  required_skills: { name: string; proficiency: string; importance: string }[]
  bonus_skills: { name: string; proficiency: string }[]
}

export const useMatchStore = defineStore('match', () => {
  const result = ref<MatchResult | null>(null)
  const loading = ref(false)

  async function runMatch(targetPosition: string, skillNames: string[]) {
    loading.value = true
    try {
      const person_skills: PersonSkill[] = skillNames.map((name) => ({
        skill_id: `skill_${name}`,
        name,
        category: 'hard_skill' as const,
        proficiency: '熟悉',
      }))
      const data = await request.post('/match/position', {
        person_skills,
        target_position: targetPosition,
      })
      result.value = data as unknown as MatchResult
    } finally {
      loading.value = false
    }
  }

  async function fetchPositionSkills(positionId: string): Promise<PositionSkills | null> {
    try {
      const data = await request.get(`/graph/position/${positionId}/skills`)
      return (data as any).skills ?? (data as unknown as PositionSkills)
    } catch {
      return null
    }
  }

  return { result, loading, runMatch, fetchPositionSkills }
})