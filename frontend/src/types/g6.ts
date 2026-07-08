/**
 * G6 v5 type bridge — re-exports for dynamic-import scenarios
 *
 * G6 is loaded dynamically for code-splitting, so we extract
 * the types we need into a local module to avoid importing
 * the full library at type-check time.
 */
export type {
  Graph,
  NodeData,
  EdgeData,
  GraphData,
  GraphOptions,
  IEvent as G6Event,
  IPointerEvent as G6PointerEvent,
  IElementEvent as G6ElementEvent,
  ElementDatum as G6ElementDatum,
} from '@antv/g6'

/** G6 Graph constructor type (for dynamic import caching) */
export type G6GraphClass = typeof import('@antv/g6').Graph

/** Edge click event payload — business-defined shape */
export interface EvolutionEdgeProperties {
  weight?: number
  similarity?: number
  trend?: 'rising' | 'stable' | 'declining'
  skill_overlap?: string[]
  key_gaps?: string[]
  evidence_count?: number
}

export interface EvolutionEdgeClickPayload {
  source: string
  target: string
  type: string
  properties: EvolutionEdgeProperties
}

/** Tooltip getContent callback parameters */
export interface G6TooltipEvent {
  target?: { id?: string }
}

export interface G6TooltipItem {
  data: Record<string, unknown>
  id?: string
}
