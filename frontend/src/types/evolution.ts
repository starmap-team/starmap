/**
 * Evolution types — shared across dashboard and evolution stores
 */

export interface EmergingSkill {
  name: string
  frequency: number
  growth_rate: number
  relevance: number
  novelty: number
  domain: string
}
