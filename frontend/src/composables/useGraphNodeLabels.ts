/**
 * Admin.vue graph node label/status maps — extracted from Admin.vue (Phase 7 D)
 * Pure helpers, no Vue or store deps.
 */

const NODE_TYPE_LABELS: Record<string, string> = {
  Skill: '技能',
  Position: '岗位',
  Domain: '领域',
  Tool: '工具',
  Certificate: '证书',
}

const NODE_STATUS_TAG: Record<string, string> = {
  approved: 'success',
  rejected: 'danger',
  pending: 'warning',
}

const NODE_STATUS_LABELS: Record<string, string> = {
  approved: '已通过',
  rejected: '已拒绝',
  pending: '待审核',
}

export function nodeTypeLabel(type: string): string {
  return NODE_TYPE_LABELS[type] ?? type
}

export function nodeStatusType(status: string): string {
  return NODE_STATUS_TAG[status] ?? 'info'
}

export function nodeStatusLabel(status: string): string {
  return NODE_STATUS_LABELS[status] ?? status
}
