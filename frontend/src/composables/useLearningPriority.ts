/**
 * LearningCenter priority label/type mappers — extracted from LearningCenter.vue (Phase 7 D)
 * Pure helpers, no Vue or store deps.
 */

export type PriorityLevel = 'high' | 'medium' | 'low'
export type TagType = 'danger' | 'warning' | 'info'

const PRIORITY_TAG: Record<PriorityLevel, TagType> = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const PRIORITY_LABEL: Record<PriorityLevel, string> = {
  high: '高优先',
  medium: '中优先',
  low: '低优先',
}

export function priorityType(p: string): TagType {
  return PRIORITY_TAG[p as PriorityLevel] ?? 'info'
}

export function priorityLabel(p: string): string {
  return PRIORITY_LABEL[p as PriorityLevel] ?? '低优先'
}
