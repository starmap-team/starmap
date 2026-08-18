/**
 * Unified Graph2D layer renderers — merges 3 single-caller composables:
 * useDomainLayer (100L) + usePositionLayer (157L) + useDetailLayer (137L)
 * All 3 served only by Graph2D.vue.
 */
import type { Graph, NodeData, EdgeData } from '@/types/g6'
import { useGraphStore } from '@/stores/graph'
import { KA_FALLBACK_COLORS, NODE_TYPE_COLORS, displayName } from '@/utils/graphColors'
import { cv } from '@/utils/chartTheme'

// ===== 1. Domain Layer =====

export interface DomainLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  layoutMode: () => 'force' | 'dagre' | 'radial'
  showEvolution?: () => boolean
  animateNodeGrowth?: (nodeIds: string[]) => void
}

export function renderDomainLayer(deps: DomainLayerDeps): void {
  const graphInstance = deps.graph()
  if (!graphInstance) return
  const graphStore = useGraphStore()
  const maxSkill = Math.max(...graphStore.domains.map(d => d.skill_count), 1)
  const minSize = 50, maxSize = 100

  const visibleFiltered = graphStore.visibleNodes.filter(n => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    return domain && (domain.position_count > 0 || domain.skill_count > 0)
  })

  const shouldAnimateGrowth = deps.showEvolution?.() ?? false
  const isAnimating = shouldAnimateGrowth && visibleFiltered.length > 0

  const graphNodes = visibleFiltered.map((n, i) => {
    const domain = graphStore.domains.find(d => d.id === n.id)
    const skillCount = domain?.skill_count ?? 0
    const posCount = domain?.position_count ?? 0
    const importance = skillCount + posCount * 2
    const size = minSize + (skillCount / maxSkill) * (maxSize - minSize)
    const color = deps.kaColorMap().get(n.id) ?? KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length]
 // When animating, start with small scale but keep labels visible
    const nodeScale = isAnimating ? 0.1 : 1
    return { id: n.id, style: { size, fill: color, fillOpacity: 0.9, scale: nodeScale, stroke: color, lineWidth: importance > 100 ? 3 : 2, labelText: n.properties.name + '\n' + posCount + '岗 ' + skillCount + '技', labelFill: cv('--primary-foreground'), labelFontSize: importance > 100 ? 15 : 13, labelFontWeight: 'bold' as const, labelPlacement: 'center' as const, shadowColor: 'rgba(0,0,0,0.2)', shadowBlur: importance > 100 ? 20 : 12, cursor: 'pointer' as const } }
  })

  const graphEdges = graphStore.visibleEdges.map(e => ({ id: `${e.source_id}-${e.target_id}-${e.type}`, source: e.source_id, target: e.target_id, style: { stroke: cv('--muted-foreground'), lineWidth: 1.5, opacity: 0.3, lineDash: [6, 4], endArrow: false } }))

  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })

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
  deps.animateNodeGrowth?.(isAnimating ? visibleFiltered.map(n => n.id) : [])
}

// ===== 2. Position Layer =====

export interface PositionLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  showEvolution: () => boolean
  maxNodesLimit: () => number
  animateNodeGrowth?: (nodeIds: string[]) => void
}

export async function renderPositionLayer(deps: PositionLayerDeps): Promise<void> {
  const graphInstance = deps.graph()
  if (!graphInstance) return
  const graphStore = useGraphStore()
  const kaId = graphStore.expandedKAId
  const kaColor = kaId ? (deps.kaColorMap().get(kaId) ?? cv('--chart-3')) : cv('--chart-3')
  const positions = graphStore.positionsByKA.get(kaId ?? '') ?? []

  const maxSkillCount = Math.max(...positions.map(p => {
    let count = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') count++ }
    return count
  }), 1)

  const graphNodes: NodeData[] = []
  const graphEdges: EdgeData[] = []

  if (kaId) {
 // G6 v5 label config: labelText is top-level, but placement/fontSize/fill are nested under `label`
 // eslint-disable-next-line @typescript-eslint/no-explicit-any
    graphNodes.push({ id: kaId, style: { size: 100, fill: kaColor, fillOpacity: 0.95, stroke: kaColor, lineWidth: 4, labelText: graphStore.expandedKAName, label: { placement: 'center', fill: cv('--primary-foreground'), fontSize: 14, fontWeight: 'bold', maxWidth: 90 }, shadowColor: kaColor, shadowBlur: 32 } as any })
  }

  const maxPositionNodes = Math.max(deps.maxNodesLimit() - 1, 5)
  const sortedPositions = [...positions].sort((a, b) => {
    let aCount = 0, bCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === a.id && e.type === 'REQUIRES') aCount++; if (e.source_id === b.id && e.type === 'REQUIRES') bCount++ }
    return bCount - aCount
  })
  const limitedPositions = sortedPositions.slice(0, maxPositionNodes)
  const shouldAnimateGrowth = deps.showEvolution() ?? false
  const isAnimating = shouldAnimateGrowth && limitedPositions.length > 0
  const showLabels = limitedPositions.length <= 12  // Hide labels when crowded; threshold lowered for clarity
  const labelFontSize = limitedPositions.length <= 30 ? 11 : 0  // When crowded, drop fontSize to 0 to avoid hidden-text artifacts

  for (const p of limitedPositions) {
    let skillCount = 0
    for (const e of graphStore.allEdges) { if (e.source_id === p.id && e.type === 'REQUIRES') skillCount++ }
    const size = 28 + (skillCount / maxSkillCount) * 16
    const nodeOpacity = isAnimating ? 0.3 : 0.85
    const nodeScale = isAnimating ? 0.1 : 1
    const displayName_ = displayName(p.properties)
    const truncated = displayName_.length > 8 ? displayName_.slice(0, 7) + '…' : displayName_
 // eslint-disable-next-line @typescript-eslint/no-explicit-any
    graphNodes.push({ id: p.id, style: { size, fill: kaColor, fillOpacity: nodeOpacity, scale: nodeScale, stroke: NODE_TYPE_COLORS.Position, lineWidth: 1.5, labelText: showLabels ? truncated : '', label: { placement: 'bottom', fill: cv('--foreground'), fontSize: labelFontSize, fontWeight: 'normal', offsetY: 6 } } as any })
    if (kaId) graphEdges.push({ id: `${kaId}-${p.id}-CONTAINS`, source: kaId, target: p.id, style: { stroke: kaColor, lineWidth: 1, opacity: 0.2, lineDash: [6, 4], endArrow: false } })
  }

  if (deps.showEvolution()) {
    const trendColors: Record<string, string> = { rising: cv('--success'), stable: cv('--muted-foreground'), declining: cv('--destructive') }
    for (const ev of graphStore.evolutionEdges) {
      const src = limitedPositions.find(p => p.id === ev.source_id || p.properties.name === ev.source_id)
      const tgt = limitedPositions.find(p => p.id === ev.target_id || p.properties.name === ev.target_id)
      if (src && tgt) {
        const trend = ev.properties.trend ?? 'stable'
        const color = trendColors[trend] ?? cv('--muted-foreground')
        graphEdges.push({ id: `evo-${src.id}-${tgt.id}`, source: src.id, target: tgt.id, style: { stroke: color, lineWidth: 2 + (ev.properties.weight ?? 0.5) * 3, opacity: 0.85, lineDash: [12, 6], endArrow: true, endArrowSize: 8, labelText: `${trend === 'rising' ? '↑' : trend === 'declining' ? '↓' : '→'} ${Math.round((ev.properties.similarity ?? 0) * 100)}%`, labelFill: color, labelFontSize: 9, labelFontWeight: 'bold' as const, labelOffsetY: -6, labelPlacement: 'center' as const } })
      }
    }
  }

  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })
  graphInstance.setLayout({ type: 'radial', unitRadius: limitedPositions.length > 30 ? 220 : 160, preventOverlap: true, nodeSize: 32, focusNode: kaId || undefined, animate: false })
  await graphInstance.render()
  deps.animateNodeGrowth?.(isAnimating ? limitedPositions.map(p => p.id) : [])
  setTimeout(() => graphInstance?.fitView(), 300)
}

// ===== 3. Detail Layer =====

export interface DetailLayerDeps {
  graph: () => Graph | null
  kaColorMap: () => Map<string, string>
  maxNodesLimit: () => number
  proficiencyFilter: () => string[]
  showEvolution?: () => boolean
  animateNodeGrowth?: (nodeIds: string[]) => void
}

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

  const shouldAnimateGrowth = deps.showEvolution?.() ?? false
  const isAnimating = shouldAnimateGrowth && graphStore.visibleNodes.length > 0

  if (kaId) graphNodes.push({ id: kaId, style: { size: 36, fill: kaColor, fillOpacity: 0.35, stroke: kaColor, lineWidth: 1, labelText: graphStore.expandedKAName, labelFill: cv('--muted-foreground'), labelFontSize: 10, labelPlacement: 'bottom' as const, labelOffsetY: 4 } })

  const posNode = graphStore.nodeMap.get(posId)
  const posOpacity = isAnimating ? 0.3 : 0.9
  const posScale = isAnimating ? 0.1 : 1
  graphNodes.push({ id: posId, style: { size: 50, fill: NODE_TYPE_COLORS.Position, fillOpacity: posOpacity, scale: posScale, stroke: cv('--primary-hover'), lineWidth: 3, labelText: posNode ? displayName(posNode.properties) : '岗位', labelFill: cv('--primary-foreground'), labelFontSize: 13, labelFontWeight: 'bold' as const, labelPlacement: 'center' as const, shadowColor: 'rgba(59,130,246,0.3)', shadowBlur: 12 } })

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

  const maxSkillNodes = Math.max(deps.maxNodesLimit() - 3, 5)
  const sortedEdges = [...filteredEdges].sort((a, b) => (b.properties?.weight ?? 0.5) - (a.properties?.weight ?? 0.5))
  const posEdges = sortedEdges.slice(0, maxSkillNodes)
  const maxWeight = Math.max(...posEdges.map(e => e.properties?.weight ?? 0.5), 0.1)

  for (const e of posEdges) {
    const skillNode = graphStore.nodeMap.get(e.target_id)
    if (!skillNode) continue
    const weight = e.properties?.weight ?? 0.5
    const isRequired = weight >= 0.6
    const size = 14 + (weight / maxWeight) * 14
    const skillColor = isRequired ? NODE_TYPE_COLORS.Skill : NODE_TYPE_COLORS.Tool
    const skillOpacity = isAnimating ? 0.3 : 0.8
    const skillScale = isAnimating ? 0.1 : 1
    graphNodes.push({ id: e.target_id, style: { size, fill: skillColor, fillOpacity: skillOpacity, scale: skillScale, stroke: isRequired ? cv('--success') : cv('--warning'), lineWidth: 1, labelText: skillNode.properties.name, labelFill: cv('--foreground'), labelFontSize: 10, labelPlacement: 'bottom' as const, labelOffsetY: 4 } })
    graphEdges.push({ id: `${posId}-${e.target_id}-REQUIRES`, source: posId, target: e.target_id, style: { stroke: skillColor, lineWidth: isRequired ? 2 : 1.5, opacity: 0.6, lineDash: isRequired ? [] : [5, 3], endArrow: !isRequired } })
  }

  graphInstance.setData({ nodes: graphNodes, edges: graphEdges })
  graphInstance.setLayout({ type: 'radial', unitRadius: 140, preventOverlap: true, nodeSize: 32, focusNode: posId, animate: false })
  graphInstance.render()
  deps.animateNodeGrowth?.(isAnimating ? graphNodes.map(n => n.id) : [])
  setTimeout(() => graphInstance?.fitView(), 300)
}
