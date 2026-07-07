import type { Graph as G6GraphType } from '@antv/g6'

let G6Graph: typeof G6GraphType | null = null

/**
 * Lazy-load @antv/g6 Graph class (shared across CareerPathGraph, LearningPathFlow, LoopDemo).
 * ponytail: single canonical loader, replaces 3 inline copies.
 */
export async function ensureG6Loaded(): Promise<typeof G6GraphType> {
  if (!G6Graph) {
    const g6 = await import('@antv/g6')
    G6Graph = g6.Graph
  }
  return G6Graph
}
