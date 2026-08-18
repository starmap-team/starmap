/**
 * useGraphHighlight — Node highlight/clearHighlight logic
 *
 * Highlights a target node + its 1-hop neighbors while fading the rest.
 * Extracted from Graph2D.vue to be testable and reusable.
 */
import type { Graph } from '@/types/g6'
import { cv } from '@/utils/chartTheme'

export interface HighlightOptions {
  fadeOpacity?: number
  relatedOpacity?: number
  centerLineWidth?: number
  relatedLineWidth?: number
}

export function useGraphHighlight(graphRef: { value: Graph | null }, visibleNodes: () => Array<{ id: string }>, visibleEdges: () => Array<{ source_id: string; target_id: string }>) {
  function highlightNode(nodeId: string, opts: HighlightOptions = {}): void {
    const graph = graphRef.value
    if (!graph) return
    const {
      fadeOpacity = 0.12,
      relatedOpacity = 0.85,
      centerLineWidth = 4,
      relatedLineWidth = 2,
    } = opts

 // 1-hop neighbor lookup
    const relatedIds = new Set<string>([nodeId])
    for (const e of visibleEdges()) {
      if (e.source_id === nodeId) relatedIds.add(e.target_id)
      else if (e.target_id === nodeId) relatedIds.add(e.source_id)
    }

 // Batch style update in a single G6 call (faster than per-node)
    const updateNodes = visibleNodes().map((n) => {
      const isCenter = n.id === nodeId
      const isRelated = relatedIds.has(n.id)
      return {
        id: n.id,
        style: {
          fillOpacity: isCenter ? 1 : isRelated ? relatedOpacity : fadeOpacity,
          lineWidth: isCenter ? centerLineWidth : isRelated ? relatedLineWidth : 0.5,
          shadowColor: isCenter ? cv('--primary') : 'transparent',
          shadowBlur: isCenter ? 24 : 0,
          cursor: 'pointer' as const,
        },
      }
    })
    graph.updateNodeData(updateNodes)
    graph.draw()
  }

  function clearHighlight(): void {
 // Caller should re-render the current layer to restore default styles
 // (component-level concern; this composable just signals intent)
  }

  return { highlightNode, clearHighlight }
}
