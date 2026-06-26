import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface PersonSkill {
  skill_id: string
  name: string
  category: 'hard_skill' | 'soft_skill' | 'tool' | 'certificate'
  proficiency: '了解' | '熟悉' | '精通'
  confidence?: number
}

export interface SkillGap {
  skill: string
  importance: 'required' | 'bonus'
  gap_level: '完全缺失' | '部分掌握' | '已掌握'
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

  /** 调用 POST /match/diagnose 执行匹配诊断 */
  async function runMatch(targetPosition: string, skills: (string | Partial<PersonSkill>)[]) {
    loading.value = true
    try {
      const person_skills: PersonSkill[] = skills.map((skill) => {
        const item = typeof skill === 'string' ? { name: skill } : skill
        const name = item.name ?? ''
        return {
          skill_id: item.skill_id ?? `skill_${name}`,
          name,
          category: item.category ?? 'hard_skill',
          proficiency: item.proficiency ?? '熟悉',
          confidence: item.confidence,
        }
      })
      const data = await request.post('/match/position', {
        person_skills,
        target_position: targetPosition,
      })
      result.value = data as unknown as MatchResult
    } finally {
      loading.value = false
    }
  }

  /** 获取岗位要求的技能列表 GET /graph/position/{id}/skills */
  async function fetchPositionSkills(positionId: string): Promise<PositionSkills | null> {
    try {
      const data = await request.get(`/graph/position/${positionId}/skills`) as any
      if (Array.isArray(data?.required_skills)) return data as PositionSkills

      const skills = (data?.skills ?? []).map((skill: any) => ({
        name: skill.name,
        proficiency: skill.proficiency ?? '熟悉',
        importance: skill.importance ?? 'required',
      }))
      return {
        position_name: data?.position?.name ?? positionId,
        required_skills: skills.filter((skill: any) => skill.importance !== 'bonus'),
        bonus_skills: skills.filter((skill: any) => skill.importance === 'bonus'),
      }
    } catch {
      return null
    }
  }

  return { result, loading, runMatch, fetchPositionSkills }
})
