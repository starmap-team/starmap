/**
 * Evolution formatters and label maps — extracted from EvolutionDashboard.vue (Phase 7 D round 8).
 * Pure helpers, no Vue or store deps.
 */

/** Format CII change percentage: last point vs 100 baseline, 1 decimal. */
export function formatChange(points: number[] | undefined): string {
  if (!points?.length) return '-'
  const last = points[points.length - 1] ?? 0
  const delta = last - 100
  const sign = delta >= 0 ? '+' : ''
  return sign + delta.toFixed(1) + '%'
}

export const TREND_LABEL: Record<string, string> = {
  rising: '↑ 上升',
  stable: '→ 平稳',
  declining: '↓ 下降',
}

export const TREND_TAG_TYPE: Record<string, string> = {
  rising: 'success',
  stable: 'info',
  declining: 'danger',
}
