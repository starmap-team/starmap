/**
 * Evolution types — shared across dashboard and evolution stores
 */

export interface EmergingSkill {
  // Backend fields (EmergingSkill model in evolution.py)
  skill_name: string
  level: string
  z_score: number
  current_frequency: number
  mean_frequency: number
  source_count: number
  positions: string[]
  // Frontend convenience aliases (mapped in useDashboardCharts)
  name?: string
  frequency?: number
  growth_rate?: number
  relevance?: number
  novelty?: number
  domain?: string
}
