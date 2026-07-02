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
  match_id?: string
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
  const history = ref<Map<string, MatchResult>>(new Map())

  async function runMatch(targetPosition: string, skillNames: string[], skillProficiencies?: Record<string, string>) {
    loading.value = true
    try {
      const person_skills: PersonSkill[] = skillNames.map((name) => ({
        skill_id: `skill_${name}`,
        name,
        category: 'hard_skill' as const,
        proficiency: skillProficiencies?.[name] ?? '熟悉',
      }))
      const data = await request.post('/match/position', {
        person_skills,
        target_position: targetPosition,
      })
      const matchResult = data as unknown as MatchResult
      result.value = matchResult
      // 缓存到历史记录
      if (matchResult.match_id) {
        history.value.set(matchResult.match_id, matchResult)
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchMatchResult(matchId: string): Promise<MatchResult | null> {
    // 先查本地缓存
    if (history.value.has(matchId)) {
      return history.value.get(matchId) ?? null
    }
    // 再查后端
    try {
      const data = await request.get(`/match/result/${matchId}`)
      const matchResult = data as unknown as MatchResult
      history.value.set(matchId, matchResult)
      return matchResult
    } catch {
      return null
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

  interface MatchHistoryItem {
    match_id: string
    target_position: string
    match_score: number
    matched_skills: string[]
    created_at?: string
  }

  const historyList = ref<MatchHistoryItem[]>([])

  async function fetchHistory() {
    try {
      const data = await request.get('/match/history', { params: { limit: 10 } }) as any
      historyList.value = data.items ?? []
    } catch {
      historyList.value = []
    }
  }

  return { result, loading, history, historyList, runMatch, fetchMatchResult, fetchPositionSkills, fetchHistory }
})