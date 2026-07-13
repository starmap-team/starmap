/**
 * useDomainLayer — Renders the domain (KA islands) layer for Graph2D.
 *
 * Extracted from Graph2D.vue to decouple the domain rendering logic
 * from the component lifecycle.
 */
import type { Graph, NodeData } from '@/types/g6'
import { useGraphStore } from '@/stores/graph'
import { KA_FALLBACK_COLORS } from '@/utils/graphColors'
import { cv } from '@/utils/chartTheme'

export interface DomainLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  layoutMode: () => 'force' | 'dagre' | 'radial'
}

/**
 * Render the domain overview layer: KA islands with size/color mapping.
 */
export function renderDomainLayer(deps: DomainLayerDeps): void {
  const graphInstance = deps.graph()
  if (!graphInstance) return

  const graphStore = useGraphStore()

  // Calculate max skill count for size normalization
  const maxSkill = Math.max(...graphStore.domains.map(d => d.skill_count), 1)
  const minSize = 50, maxSize = 100

  // Filter out empty domain nodes (no positions and no skills)
  const visibleFiltered = graphStore.visibleNodes.filter(n => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    return domain && (domain.position_count > 0 || domain.skill_count > 0)
  })

  // Map domain data to G6 node objects
  const graphNodes = visibleFiltered.map((n, i) => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    const skillCount = domain?.skill_count ?? 0
    const posCount = domain?.position_count ?? 0
    const importance = skillCount + posCount * 2
    const size = minSize + (skillCount / maxSkill) * (maxSize - minSize)
    const color = deps.kaColorMap().get(n.id) ?? KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length]
    return {
      id: n.id,
      style: {
        size,
        fill: color,
        fillOpacity: 0.9,
        stroke: color,
        lineWidth: importance > 100 ? 3 : 2,
        labelText: n.properties.name + '\n' + posCount + '岗 ' + skillCount + '技',
        labelFill: cv('--primary-foreground'),
        labelFontSize: importance > 100 ? 15 : 13,
        labelFontWeight: 'bold' as const,
        labelPlacement: 'center' as const,
        shadowColor: 'rgba(0,0,0,0.2)',
        shadowBlur: importance > 100 ? 20 : 12,
        cursor: 'pointer' as const,
      },
    }
  })

  // Map domain edges to G6 edge objects
  const graphEdges = graphStore.visibleEdges.map(e => ({
    id: `${e.source_id}-${e.target_id}-${e.type}`,
    source: e.source_id,
    target: e.target_id,
    style: {
      stroke: cv('--muted-foreground'),
      lineWidth: 1.5,
      opacity: 0.3,
      lineDash: [6, 4],
      endArrow: false,
    },
  }))

  // Inject node and edge data
  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })

  // Set entrance animation state
  const entranceNodes = graphNodes.map((n: NodeData) => ({
    id: n.id,
    style: { fillOpacity: 0, scale: 0.3 },
  }))
  graphInstance.updateNodeData(entranceNodes)

  // Select layout based on overview mode and layout mode
  const isLevel = graphStore.overviewMode === 'level'
  const isTechStack = graphStore.overviewMode === 'tech_stack'
  if (deps.layoutMode() === 'dagre' || isLevel) {
    graphInstance.setLayout({ type: 'dagre', rankdir: 'TB', nodesep: isLevel ? 140 : 80, ranksep: isLevel ? 160 : 100, preventOverlap: true, nodeSize: 80, controlPoints: true })
  } else if (isTechStack) {
    graphInstance.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: false, clustering: true, clusterNodeStrength: 0.5, strength: 0.4, coulombDisScale: 0.005, gravity: 8, maxSpeed: 200, maxIteration: 100 })
  } else {
    graphInstance.setLayout({ type: 'force', preventOverlap: true, nodeSize: 80, nodeSpacing: 60, animate: false, strength: 0.4, coulombDisScale: 0.005, gravity: 10, maxSpeed: 200, maxIteration: 100 })
  }
  graphInstance.render()
}
