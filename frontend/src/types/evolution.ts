/**
 * Evolution types — shared across dashboard and evolution stores
 */

//: ChangeType enum — matches backend diff_engine.py
export type ChangeType = 'added_required' | 'added_preferred' | 'removed' | 'promoted' | 'demoted' | 'retained'

export interface EmergingSkill {
 // Backend fields (EmergingSkill model in evolution.py)
  skill_name: string
  level: 'emerging' | 'rising' | 'stable' | 'declining'
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
