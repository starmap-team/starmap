/**
 * useDetailLayer — Renders the detail (Position + its Skills) layer for Graph2D.
 *
 * Extracted from Graph2D.vue to decouple the detail rendering logic
 * from the component lifecycle.
 */
import type { Graph, NodeData, EdgeData } from '@/types/g6'
import { useGraphStore } from '@/stores/graph'
import { NODE_TYPE_COLORS } from '@/utils/graphColors'
import { cv } from '@/utils/chartTheme'

export interface DetailLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  maxNodesLimit: () => number
  proficiencyFilter: () => string[]
}

/**
 * Render the detail layer: position center + skills with radial layout, proficiency filtering.
 */
export function renderDetailLayer(deps: DetailLayerDeps): void {
  const graphInstance = deps.graph()
  if (!graphInstance) return

  const graphStore = useGraphStore()
  const posId = graphStore.expandedPositionId
  if (!posId) return

  const graphNodes: NodeData[] = []
  const graphEdges: EdgeData[] = []
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (deps.kaColorMap().get(kaId) ?? cv('--chart-3')) : cv('--chart-3')

  // Build KA background node
  if (kaId) {
    graphNodes.push({
      id: kaId,
      style: {
        size: 36,
        fill: kaColor,
        fillOpacity: 0.35,
        stroke: kaColor,
        lineWidth: 1,
        labelText: graphStore.expandedKAName,
        labelFill: cv('--muted-foreground'),
        labelFontSize: 10,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 4,
      },
    })
  }

  // Build center position node
  const posNode = graphStore.nodeMap.get(posId)
  graphNodes.push({
    id: posId,
    style: {
      size: 50,
      fill: NODE_TYPE_COLORS.Position,
      fillOpacity: 0.9,
      stroke: cv('--primary-hover'),
      lineWidth: 3,
      labelText: posNode?.properties.name ?? '岗位',
      labelFill: cv('--primary-foreground'),
      labelFontSize: 13,
      labelFontWeight: 'bold' as const,
      labelPlacement: 'center' as const,
      shadowColor: 'rgba(59,130,246,0.3)',
      shadowBlur: 12,
    },
  })

  // Get position edges and apply proficiency filter
  const allPosEdges = graphStore.visibleEdges.filter(e => e.source_id === posId)
  const hasActiveFilter = deps.proficiencyFilter().length < 3
  const filteredEdges = hasActiveFilter
    ? allPosEdges.filter(e => {
        const skillNode = graphStore.nodeMap.get(e.target_id)
        if (!skillNode) return false
        const level = (e.properties as Record<string, unknown>)?.level
        const prof = skillNode.properties.proficiency || (typeof level === 'string' ? level : '') || ''
        return prof ? deps.proficiencyFilter().includes(prof) : true
      })
    : allPosEdges

  // Apply maxNodesLimit and sort by weight
  const maxSkillNodes = Math.max(deps.maxNodesLimit() - 3, 5)
  const sortedEdges = [...filteredEdges].sort((a, b) => (b.properties?.weight ?? 0.5) - (a.properties?.weight ?? 0.5))
  const posEdges = sortedEdges.slice(0, maxSkillNodes)
  const maxWeight = Math.max(...posEdges.map(e => e.properties?.weight ?? 0.5), 0.1)

  // Build skill nodes and REQUIRES edges
  for (const e of posEdges) {
    const skillNode = graphStore.nodeMap.get(e.target_id)
    if (!skillNode) continue
    const weight = e.properties?.weight ?? 0.5
    const isRequired = weight >= 0.6
    const size = 14 + (weight / maxWeight) * 14
    const skillColor = isRequired ? NODE_TYPE_COLORS.Skill : NODE_TYPE_COLORS.Tool

    graphNodes.push({
      id: e.target_id,
      style: {
        size,
        fill: skillColor,
        fillOpacity: 0.8,
        stroke: isRequired ? cv('--success') : cv('--warning'),
        lineWidth: 1,
        labelText: skillNode.properties.name,
        labelFill: cv('--foreground'),
        labelFontSize: 10,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 4,
      },
    })

    graphEdges.push({
      id: `${posId}-${e.target_id}-REQUIRES`,
      source: posId,
      target: e.target_id,
      style: {
        stroke: skillColor,
        lineWidth: isRequired ? 2 : 1.5,
        opacity: 0.6,
        lineDash: isRequired ? [] : [5, 3],
        endArrow: !isRequired,
      },
    })
  }

  // Inject data, set radial layout, render
  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })
  graphInstance.setLayout({ type: 'radial', unitRadius: 140, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: false })
  graphInstance.render()
  setTimeout(() => graphInstance?.fitView(), 300)
}
