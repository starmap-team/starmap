/**
 * StarMap Graph Color System — unified palette for 2D + 3D rendering.
 *
 * All graph color constants and helpers live here as pure exports.
 * Store-dependent colors (KA_COLOR_MAP) are built by the caller.
 */

// ── Domain palette (fallback for KnowledgeArea nodes) ──
export const DOMAIN_COLORS = [
  '#6366f1', // indigo
  '#8b5cf6', // violet
  '#a855f7', // purple
  '#ec4899', // pink
  '#f43f5e', // rose
  '#0ea5e9', // sky
  '#06b6d4', // cyan
  '#14b8a6', // teal
  '#22c55e', // green
  '#84cc16', // lime
  '#eab308', // yellow
  '#f97316', // orange
  '#ef4444', // red
  '#64748b', // slate
] as const

/** Alias — fallback palette used when a domain's backend color is unset. */
export const KA_FALLBACK_COLORS = DOMAIN_COLORS

// ── Edge type colors ──
export const EDGE_TYPE_COLORS: Record<string, string> = {
  REQUIRES:      '#22d3ee',   // cyan-400
  EVOLVES_TO:    '#f472b6',   // pink-400
  PREREQUISITE:  '#a78bfa',   // violet-400
  CONTAINS:      '#38bdf8',   // sky-400
  BELONGS_TO:    '#34d399',   // emerald-400
  DEFAULT:       '#64748b',   // slate-500
}

// ── Node type base colors ──
export const NODE_TYPE_COLORS: Record<string, string> = {
  KnowledgeArea: '#8b5cf6',  // violet
  Position:      '#3b82f6',  // blue
  Skill:         '#10b981',  // emerald
  Tool:          '#f59e0b',  // amber
  Certificate:   '#06b6d4',  // cyan
  LearningResource: '#ec4899', // pink
  Industry:      '#64748b',  // slate
}

// ── Node type Chinese labels ──
export const TYPE_LABELS: Record<string, string> = {
  KnowledgeArea: '领域',
  Position: '岗位',
  Skill: '技能',
  Tool: '工具',
  Certificate: '证书',
  LearningResource: '学习资源',
  Industry: '行业',
}

// ── Combined type→{label, color} map (for tooltips, badges, legends) ──
export const TYPE_INFO: Record<string, { label: string; color: string }> = {
  KnowledgeArea:   { label: TYPE_LABELS.KnowledgeArea,   color: NODE_TYPE_COLORS.KnowledgeArea },
  Position:        { label: TYPE_LABELS.Position,        color: NODE_TYPE_COLORS.Position },
  Skill:           { label: TYPE_LABELS.Skill,           color: NODE_TYPE_COLORS.Skill },
  Tool:            { label: TYPE_LABELS.Tool,            color: NODE_TYPE_COLORS.Tool },
  Certificate:     { label: TYPE_LABELS.Certificate,     color: NODE_TYPE_COLORS.Certificate },
  LearningResource:{ label: TYPE_LABELS.LearningResource,color: NODE_TYPE_COLORS.LearningResource },
  Industry:        { label: TYPE_LABELS.Industry,        color: NODE_TYPE_COLORS.Industry },
}

/**
 * Returns the base color for a non-KA node type.
 * KA coloring is precomputed by the caller (Home.vue builds KA_COLOR_MAP from store).
 * The _categoryOrId parameter is retained for backward compatibility (Phase 5 removes callers).
 */
export function nodeColor(type: string, _categoryOrId?: string): string {
  return NODE_TYPE_COLORS[type] ?? '#64748b'
}

/**
 * Returns color for an edge based on its relationship type.
 */
export function edgeColor(type: string): string {
  return EDGE_TYPE_COLORS[type] ?? EDGE_TYPE_COLORS.DEFAULT
}

/**
 * Returns a brighter/glow version of a base color for 3D glow effects.
 * Boosts brightness by ~30% and returns as CSS color string.
 */
export function glowColor(baseColor: string): string {
  // Parse hex color
  const hex = baseColor.replace('#', '')
  const r = parseInt(hex.substring(0, 2), 16)
  const g = parseInt(hex.substring(2, 4), 16)
  const b = parseInt(hex.substring(4, 6), 16)

  // Boost brightness (mix toward white by 35%)
  const boost = 0.35
  const nr = Math.min(255, Math.round(r + (255 - r) * boost))
  const ng = Math.min(255, Math.round(g + (255 - g) * boost))
  const nb = Math.min(255, Math.round(b + (255 - b) * boost))

  return `rgb(${nr}, ${ng}, ${nb})`
}

/**
 * Returns an RGBA string with specified alpha for semi-transparent rendering.
 */
export function withAlpha(color: string, alpha: number): string {
  const hex = color.replace('#', '')
  const r = parseInt(hex.substring(0, 2), 16)
  const g = parseInt(hex.substring(2, 4), 16)
  const b = parseInt(hex.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Dark theme palette constants for the 3D scene.
 */
export const SCENE_PALETTE = {
  background:    '#0a0e1a',   // deep space navy
  ambientLight:  '#1e293b',   // subtle ambient
  gridColor:     '#1e293b',   // faint grid lines
  textColor:     '#e2e8f0',   // light text for labels
  mutedText:     '#94a3b8',   // muted text
  highlightRing: '#22d3ee',   // cyan highlight ring
  selectionGlow: '#f59e0b',   // amber selection glow
} as const

/**
 * Returns a THREE.js-compatible hex integer from a CSS hex color string.
 */
export function toThreeHex(cssHex: string): number {
  return parseInt(cssHex.replace('#', ''), 16)
}
