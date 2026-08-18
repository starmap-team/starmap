import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import { useResponseValidation } from '@/validation/useResponseValidation'
// PLAN-014 批次5: match 契约接入 (10 模型在 schemas/match.py 已就位)
// relative path 解析从 src/stores/ 到 repo root/starmap-contracts/schemas/ 需 ../../../
import matchSchema from '@contracts/schemas/match.schema.json'

const { validateResponse: validateMatch } = useResponseValidation()

export interface PersonSkill {
  skill_id?: string
  name: string
  category?: 'hard_skill' | 'soft_skill' | 'tool' | 'certificate'
  proficiency: string
  confidence?: number
  source_count?: number
}

export type Importance = 'required' | 'bonus'

export type GapLevel = '完全缺失' | '部分掌握' | '已掌握'

export interface SkillGap {
  skill: string
  importance: Importance
  gap_level: GapLevel
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
  cii?: number | null
 //（ 强制规范）：后端 MatchResponse.note 同步，前端运行时校验依赖
  note?: string | null
 // D6: 后端匹配结果含 trust_score（matched_skills 的 Neo4j Skill.trust_score 最小值）
  trust_score?: number | null
 //: 分数拆解（required_avg/bonus_avg/权重/inflated）— 后端 MatchScoreBreakdown
  score_breakdown?: {
    required_avg?: number
    bonus_avg?: number
    weight_required?: number
    weight_bonus?: number
    inflated?: boolean
  } | null
}

export interface PositionSkills {
  position_name: string
  required_skills: { name: string; proficiency: string; importance: Importance }[]
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
        proficiency: skillProficiencies?.[name] ?? '熟悉',
      }))
      const raw = await request.post<MatchResult>('/match/position', {
        person_skills,
        target_position: targetPosition,
      })
 // PLAN-014 批次5: 契约运行时校验 (MatchResponse 入口) — DEV 仅 warn, 不阻断
      const matchResult = validateMatch(raw, matchSchema, '/match/position', 'MatchResponse')
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
      const matchResult = await request.get<MatchResult>(`/match/result/${matchId}`)
      history.value.set(matchId, matchResult)
      return matchResult
    } catch {
      return null
    }
  }

  async function fetchPositionSkills(positionId: string): Promise<PositionSkills | null> {
    try {
      const data = await request.get(`/graph/position/${positionId}/skills`) as PositionSkillDetailResponse
 // Backend returns PositionSkillDetailResponse {position, skills, edges}
      if (data.skills && Array.isArray(data.skills)) {
        const positionName = data.position?.name ?? positionId
        const required = data.skills.filter((s: SkillNodeRaw) => s.importance === 'required')
        const bonus = data.skills.filter((s: SkillNodeRaw) => s.importance === 'bonus')
        return {
          position_name: positionName,
          required_skills: required.map((s: SkillNodeRaw) => ({ name: s.name, proficiency: s.proficiency, importance: s.importance })),
          bonus_skills: bonus.map((s: SkillNodeRaw) => ({ name: s.name, proficiency: s.proficiency })),
        }
      }
      return null
    } catch {
      return null
    }
  }

  interface SkillNodeRaw {
    skill_id: string
    name: string
    category: string
    proficiency: string
    confidence: number
    source_count: number
    trend: string
    importance: Importance
  }

  interface MatchHistoryItem {
    match_id: string
    target_position: string
    match_score: number
    matched_skills: string[]
    created_at?: string
  }

  interface PositionSkillDetailResponse {
    position: { position_id: string; name: string; industry: string; description: string; skills_required: unknown[] } | null
    skills: SkillNodeRaw[]
    edges: { source_id: string; target_id: string; type: string; properties: Record<string, unknown> }[]
  }

  interface MatchHistoryResponse {
    items: MatchHistoryItem[]
  }

  const historyList = ref<MatchHistoryItem[]>([])

  async function fetchHistory() {
    try {
      const data = await request.get('/match/history', { params: { limit: 10 } }) as MatchHistoryResponse
      historyList.value = data.items ?? []
    } catch {
      historyList.value = []
    }
  }

  function clearResult() {
    result.value = null
  }

  return { result, loading, history, historyList, runMatch, fetchMatchResult, fetchPositionSkills, fetchHistory, clearResult }
})