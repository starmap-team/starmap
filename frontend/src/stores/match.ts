import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 匹配诊断结果 store
 * 对应契约：POST /match/position → MatchResult
 * enrich 字段用于前端展示，联调时需从 contract 字段拆解
 */

// ── 契约 SkillNode（简化为匹配请求用）──
export interface PersonSkill {
  skill_id: string
  name: string
  category: 'hard_skill' | 'soft_skill' | 'tool' | 'certificate'
  proficiency: '了解' | '熟悉' | '精通'
  confidence?: number
}

// ── enrich: 前端展示用差距详情 ──
export interface SkillGap {
  skill: string
  importance: 'required' | 'bonus'
  gap_level: '完全缺失' | '部分掌握' | '已掌握'
  learning_path: string[]
}

// ── 契约 MatchResult + enrich ──
export interface MatchResult {
  // 契约字段
  match_score: number
  matched_skills: string[]
  gap_skills: string[]
  recommendations: string[]
  // enrich: 前端展示额外字段（mock 返回，联调时从 ↑ 拆解）
  target_position?: string
  missing_required?: string[]
  missing_bonus?: string[]
  skill_gap_detail?: SkillGap[]
  overall_assessment?: string
  estimated_learning_time?: string
}

export const useMatchStore = defineStore('match', () => {
  const result = ref<MatchResult | null>(null)
  const loading = ref(false)

  async function runMatch(targetPosition: string, skillNames: string[]) {
    loading.value = true
    try {
      // 将 string[] 转为契约 SkillNode[] 格式
      const person_skills: PersonSkill[] = skillNames.map((name, _i) => ({
        skill_id: `skill_${name}`,
        name,
        category: 'hard_skill' as const,
        proficiency: '熟悉' as const,
      }))

      const resp = await fetch('/api/v1/match/position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_skills, target_position: targetPosition }),
      })
      const data = await resp.json()
      result.value = data as MatchResult
    } finally {
      loading.value = false
    }
  }

  return { result, loading, runMatch }
})
