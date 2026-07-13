/**
 * useEvolutionEdges — Evolution edge composition and color logic for 3D force graph.
 *
 * Extracted from Graph3D.vue to decouple the evolution edge rendering
 * from the component.
 */
import type { LinkObject } from '3d-force-graph'
import type { GraphNode3D } from './useNodeThreeObject'
import { withAlpha } from '@/utils/graphColors'
import { chartColors } from '@/utils/chartTheme'

// ── Types ──
export interface GraphLink3D extends LinkObject<GraphNode3D> {
  type?: string
  properties?: {
    weight?: number
    trend?: 'rising' | 'stable' | 'declining'
    similarity?: number
    skill_overlap?: string[]
    key_gaps?: string[]
    evidence_count?: number
  }
}

const cc = chartColors()

/** Trend → color mapping for evolution edges */
const EVOLUTION_TREND_COLOR: Record<string, string> = {
  rising: cc.success,
  stable: cc.muted,
  declining: cc.danger,
}

/**
 * Compute the color for an evolution edge based on its trend and trust score.
 */
export function evolutionColor(link: GraphLink3D): string {
  const trend = link.properties?.trend ?? 'stable'
  const base = EVOLUTION_TREND_COLOR[trend] ?? EVOLUTION_TREND_COLOR.stable
  // trust_score (0..1) maps to opacity 0.3..1.0
  const trust = link.properties?.similarity ?? link.properties?.weight ?? 0.5
  const alpha = 0.3 + Math.max(0, Math.min(1, trust)) * 0.7
  return withAlpha(base, alpha)
}

/**
 * Compose base links with filtered evolution paths.
 * Only includes evolution edges whose both endpoints are visible in the current node set.
 */
export function composeEvolutionLinks(
  baseLinks: GraphLink3D[],
  evolutionPaths: GraphLink3D[],
  visibleNodes: GraphNode3D[],
  showEvolution: boolean,
): GraphLink3D[] {
  const composed: GraphLink3D[] = [...baseLinks]
  if (!showEvolution || !evolutionPaths?.length) return composed

  const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
  const filtered = evolutionPaths.filter(ev => {
    const srcOk = visibleNodeIds.has(String(ev.source)) || visibleNodeIds.has(typeof ev.source === 'object' ? ev.source.id : '')
    const tgtOk = visibleNodeIds.has(String(ev.target)) || visibleNodeIds.has(typeof ev.target === 'object' ? ev.target.id : '')
    return srcOk && tgtOk
  })
  for (const ev of filtered) {
    composed.push({
      source: ev.source,
      target: ev.target,
      type: 'EVOLVES_TO',
      properties: ev.properties,
    })
  }
  return composed
}
