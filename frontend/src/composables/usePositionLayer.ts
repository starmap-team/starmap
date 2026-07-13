/**
 * usePositionLayer — Renders the position (KA + its positions) layer for Graph2D.
 *
 * Extracted from Graph2D.vue to decouple the position rendering logic
 * from the component lifecycle.
 */
import type { Graph, NodeData, EdgeData } from '@/types/g6'
import { useGraphStore } from '@/stores/graph'
import { NODE_TYPE_COLORS } from '@/utils/graphColors'
import { cv } from '@/utils/chartTheme'

export interface PositionLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  showEvolution: () => boolean
  maxNodesLimit: () => number
}

/**
 * Render the position layer: KA center + positions with radial layout, evolution edges.
 */
export function renderPositionLayer(deps: PositionLayerDeps): void {
  const graphInstance = deps.graph()
  if (!graphInstance) return

  const graphStore = useGraphStore()
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (deps.kaColorMap().get(kaId) ?? cv('--chart-3')) : cv('--chart-3')
  const positions = graphStore.positionsByKA.get(kaId ?? '') ?? []

  // Calculate max skill count for position size normalization
  const maxSkillCount = Math.max(...positions.map(p => {
    let count = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') count++ }
    return count
  }), 1)

  const graphNodes: NodeData[] = []
  const graphEdges: EdgeData[] = []

  // Build center KA node
  if (kaId) {
    graphNodes.push({
      id: kaId,
      style: {
        size: 60,
        fill: kaColor,
        fillOpacity: 0.7,
        stroke: kaColor,
        lineWidth: 3,
        labelText: graphStore.expandedKAName,
        labelFill: cv('--primary-foreground'),
        labelFontSize: 13,
        labelFontWeight: 'bold' as const,
        labelPlacement: 'center' as const,
        shadowColor: kaColor,
        shadowBlur: 24,
        shadowOffsetY: 3,
      },
    })
  }

  // Apply maxNodesLimit and sort positions by skill count
  const maxPositionNodes = Math.max(deps.maxNodesLimit() - 1, 5)
  const sortedPositions = [...positions].sort((a, b) => {
    let aCount = 0, bCount = 0
    for (const e of graphStore.allEdges) {
      if (e.source_id === a.id && e.type === 'REQUIRES') aCount++
      if (e.source_id === b.id && e.type === 'REQUIRES') bCount++
    }
    return bCount - aCount
  })
  const limitedPositions = sortedPositions.slice(0, maxPositionNodes)

  // Build position nodes
  const posColor = NODE_TYPE_COLORS.Position
  for (const p of limitedPositions) {
    let skillCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') skillCount++ }
    const size = 28 + (skillCount / maxSkillCount) * 16

    graphNodes.push({
      id: p.id,
      style: {
        size,
        fill: posColor,
        fillOpacity: 0.85,
        stroke: cv('--primary-hover'),
        lineWidth: 1.5,
        labelText: p.properties.name,
        labelFill: cv('--foreground'),
        labelFontSize: 11,
        labelFontWeight: 'normal' as const,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 6,
      },
    })

    // Build KA-to-position CONTAINS edges
    if (kaId) {
      graphEdges.push({
        id: `${kaId}-${p.id}-CONTAINS`,
        source: kaId,
        target: p.id,
        style: {
          stroke: kaColor,
          lineWidth: 1,
          opacity: 0.2,
          lineDash: [6, 4],
          endArrow: false,
        },
      })
    }
  }

  // Render evolution edges when enabled
  if (deps.showEvolution()) {
    const trendColors: Record<string, string> = {
      rising: cv('--success'),
      stable: cv('--muted-foreground'),
      declining: cv('--destructive'),
    }
    for (const ev of graphStore.evolutionEdges) {
      const src = limitedPositions.find(p => p.id === ev.source_id || p.properties.name === ev.source_id)
      const tgt = limitedPositions.find(p => p.id === ev.target_id || p.properties.name === ev.target_id)
      if (src && tgt) {
        const trend = ev.properties.trend ?? 'stable'
        const color = trendColors[trend] ?? cv('--muted-foreground')
        graphEdges.push({
          id: `evo-${src.id}-${tgt.id}`,
          source: src.id,
          target: tgt.id,
          style: {
            stroke: color,
            lineWidth: 2 + (ev.properties.weight ?? 0.5) * 3,
            opacity: 0.85,
            lineDash: [12, 6],
            endArrow: true,
            endArrowSize: 8,
            labelText: `${trend === 'rising' ? '↑' : trend === 'declining' ? '↓' : '→'} ${Math.round((ev.properties.similarity ?? 0) * 100)}%`,
            labelFill: color,
            labelFontSize: 9,
            labelFontWeight: 'bold' as const,
            labelOffsetY: -6,
            labelPlacement: 'center' as const,
          },
        })
      }
    }
  }

  // Inject data, set radial layout, render
  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })
  graphInstance.setLayout({ type: 'radial', unitRadius: 160, preventOverlap: true, nodeSize: 48, focusNode: kaId || undefined, animate: false })
  graphInstance.render()
  setTimeout(() => graphInstance?.fitView(), 300)
}
