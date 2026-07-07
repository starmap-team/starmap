import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useGraphStore, type GraphNode, type ViewLayer, type OverviewMode } from '@/stores/graph'
import { cv, tooltipStyle } from '@/utils/chartTheme'
}

export interface BreadcrumbItem {
  label: string
  layer: ViewLayer
  action?: () => void
}

export interface EvolutionEdgeArg {
  source: string | { id: string }
  target: string | { id: string }
  type?: string
  properties?: any
}

export interface RadarChartOption {
  tooltip: unknown
  radar: unknown
  series: unknown[]
}

export interface UseHomeInteractions {
  // refs
  graph2DRef: Ref<any>
  graph3DRef: Ref<any>
  evolutionDrawerVisible: Ref<boolean>
  selectedEvolutionEdge: Ref<any>
  // constants
  evolutionTrendLabel: Record<string, string>
  evolutionTrendType: Record<string, string>
  // computed
  breadcrumb: ComputedRef<BreadcrumbItem[]>
  positionRadarOption: ComputedRef<RadarChartOption | null>
  // handlers
  onOverviewModeChange: (mode: string) => void
  onCameraPreset: (preset: 'overview' | 'domain' | 'position') => void
  onResetCamera: () => void
  onToggleAutoRotate: (autoRotate3DRef: Ref<boolean>) => void
  onNodeDblClick: (nodeId: string) => void
  resetHighlight: () => void
  toggleEvolution: (
    showEvolutionRef: Ref<boolean>,
    selectedNodeRef: Ref<any>,
  ) => Promise<void>
  closeDetail: (clearSelection: () => void) => void
  handleNodeClick: (
    nodeId: string,
    selectedNodeRef: Ref<any>,
  ) => Promise<void>
  onCanvasClick: (clearSelection: () => void) => void
  handleSearchSelect: (
    id: string,
    _name: string,
    _type: string,
    selectedNodeRef: Ref<any>,
  ) => void
  openEvolutionDrawer: (edge: EvolutionEdgeArg) => void
  closeEvolutionDrawer: () => void
}

/**
 * Hand-rolled by Ponytail: home page interactions were spread across Home.vue's
 * <script setup>; we keep a single composable that owns all interaction handlers
 * plus the radar chart option computation. Upgrading is straightforward: drop this
 * file's exports into the existing useGraphToolbarState / useEvolutionPanel if/when
 * a per-section composable split becomes worth it.
 */
export function useHomeInteractions(
  getGraphStore: () => ReturnType<typeof useGraphStore>,
): UseHomeInteractions {
  const graphStore = getGraphStore()

  // Template refs
  const graph2DRef = ref<any>(null)
  const graph3DRef = ref<any>(null)

  // Evolution drawer state
  const evolutionDrawerVisible = ref(false)
  const selectedEvolutionEdge = ref<typeof graphStore.evolutionPaths[number] | null>(
    null,
  )

  const evolutionTrendLabel: Record<string, string> = {
    rising: '↑ 上升',
    stable: '→ 平稳',
    declining: '↓ 下降',
  }
  const evolutionTrendType: Record<string, string> = {
    rising: 'success',
    stable: 'info',
    declining: 'danger',
  }

  function openEvolutionDrawer(edge: EvolutionEdgeArg) {
    const sId = typeof edge.source === 'string' ? edge.source : edge.source?.id ?? ''
    const tId = typeof edge.target === 'string' ? edge.target : edge.target?.id ?? ''
    const match = graphStore.evolutionPaths.find(
      e => e.source_id === sId && e.target_id === tId,
    )
    selectedEvolutionEdge.value = match ?? null
    evolutionDrawerVisible.value = true
  }

  function closeEvolutionDrawer() {
    evolutionDrawerVisible.value = false
    selectedEvolutionEdge.value = null
  }

  // Breadcrumb
  const breadcrumb = computed<BreadcrumbItem[]>(() => {
    const items: BreadcrumbItem[] = [
      {
        label: '领域概览',
        layer: 'domain',
        action: () => graphStore.goToDomainLayer(),
      },
    ]
    if (graphStore.expandedKAName) {
      items.push({
        label: graphStore.expandedKAName,
        layer: 'position',
        action: () => {
          graphStore.expandedPositionId = null
          graphStore.currentLayer = 'position'
        },
      })
    }
    if (graphStore.expandedPositionId) {
      const posNode = graphStore.nodeMap.get(graphStore.expandedPositionId)
      items.push({ label: posNode?.properties.name ?? '岗位', layer: 'detail' })
    }
    return items
  })

  // Overview mode / view mode
  function onOverviewModeChange(mode: string) {
    graphStore.fetchOverview(mode as OverviewMode)
  }

  // 3D camera controls
  function onCameraPreset(preset: 'overview' | 'domain' | 'position') {
    graph3DRef.value?.setCameraPreset(preset)
  }
  function onResetCamera() {
    graph3DRef.value?.resetCamera()
  }
  function onToggleAutoRotate(autoRotate3DRef: Ref<boolean>) {
    graph3DRef.value?.toggleAutoRotate()
    autoRotate3DRef.value = !autoRotate3DRef.value
  }

  // Node click / dblclick
  function onNodeDblClick(nodeId: string) {
    const n = graphStore.nodeMap.get(nodeId)
    if (!n) return
    const label = n.labels[0]
    if (label === 'KnowledgeArea') {
      graphStore.goToPositionLayer(n.id, n.properties.name)
    } else if (label === 'Position') {
      graphStore.goToDetailLayer(n.id)
    }
  }

  function resetHighlight() {
    graph2DRef.value?.clearHighlight()
  }

  async function toggleEvolution(
    showEvolutionRef: Ref<boolean>,
    selectedNodeRef: Ref<any>,
  ) {
    showEvolutionRef.value = !showEvolutionRef.value
    if (showEvolutionRef.value) {
      if (graphStore.evolutionEdges.length === 0) {
        await graphStore.fetchEvolutionEdges()
      }
      if (
        selectedNodeRef.value?.labels?.includes('Position') &&
        selectedNodeRef.value.properties.name
      ) {
        graphStore.focusedPositionId = selectedNodeRef.value.id
        graphStore.focusedPositionName = selectedNodeRef.value.properties.name
        await graphStore.fetchEvolutionPathsForPosition(selectedNodeRef.value.properties.name)
      } else if (graphStore.expandedKAId) {
        const positions = graphStore.positionsByKA.get(graphStore.expandedKAId) ?? []
        const firstName = positions[0]?.properties.name
        if (firstName) {
          graphStore.focusedPositionName = firstName
          await graphStore.fetchEvolutionPathsForPosition(firstName)
        }
      }
    } else {
      graphStore.evolutionPaths = []
      graphStore.focusedPositionId = null
      graphStore.focusedPositionName = ''
    }
  }

  function closeDetail(clearSelectionFn: () => void) {
    clearSelectionFn()
    graph2DRef.value?.clearHighlight()
  }

  async function handleNodeClick(
    nodeId: string,
    selectedNodeRef: Ref<any>,
  ) {
    if (graphStore.currentLayer === 'domain') {
      const domain = graphStore.domains.find(d => d.id === nodeId)
      if (domain) {
        selectedNodeRef.value = {
          id: domain.id,
          labels: ['KnowledgeArea'],
          properties: {
            name: domain.name,
            position_count: domain.position_count,
            skill_count: domain.skill_count,
          },
        }
        await graphStore.goToPositionLayer(domain.id, domain.name)
      }
      return
    }
    if (graphStore.currentLayer === 'position') {
      if (nodeId === graphStore.expandedKAId) {
        const domain = graphStore.domains.find(d => d.id === nodeId)
        selectedNodeRef.value = domain
          ? {
              id: domain.id,
              labels: ['KnowledgeArea'],
              properties: {
                name: domain.name,
                position_count: domain.position_count,
                skill_count: domain.skill_count,
              },
            }
          : null
        return
      }
      const node = graphStore.nodeMap.get(nodeId)
      if (node?.labels.includes('Position')) {
        selectedNodeRef.value = node
        graphStore.goToDetailLayer(nodeId)
      }
      return
    }
    const node = graphStore.nodeMap.get(nodeId)
    if (node) selectedNodeRef.value = node
    graph2DRef.value?.highlightNode(nodeId)
  }

  function onCanvasClick(clearSelectionFn: () => void) {
    clearSelectionFn()
    graph2DRef.value?.clearHighlight()
  }

  function findKAForPosition(positionId: string): string | null {
    for (const [kaId, positions] of graphStore.positionsByKA) {
      if (positions.some(p => p.id === positionId)) return kaId
    }
    return null
  }

  function handleSearchSelect(
    id: string,
    _name: string,
    _type: string,
    selectedNodeRef: Ref<any>,
  ) {
    const domain = graphStore.domains.find(d => d.id === id)
    if (domain) {
      graphStore.goToPositionLayer(domain.id, domain.name)
      return
    }
    const node = graphStore.allNodes.find(n => n.id === id)
    if (node?.labels.includes('Position')) {
      const kaId = findKAForPosition(node.id)
      if (kaId) {
        const ka = graphStore.domains.find(d => d.id === kaId)
        graphStore.goToPositionLayer(kaId, ka?.name ?? '').then(() => {
          graphStore.goToDetailLayer(node.id)
          selectedNodeRef.value = node
        })
      }
      return
    }
    if (node?.labels.includes('Skill')) {
      for (const e of graphStore.allEdges) {
        if (e.target_id === id && e.type === 'REQUIRES') {
          const posNode = graphStore.nodeMap.get(e.source_id)
          if (posNode) {
            const kaId = findKAForPosition(posNode.id)
            if (kaId) {
              const ka = graphStore.domains.find(d => d.id === kaId)
              graphStore.goToPositionLayer(kaId, ka?.name ?? '').then(() => {
                graphStore.goToDetailLayer(posNode.id)
                selectedNodeRef.value = node
              })
            }
            return
          }
        }
      }
    }
  }

  // Radar chart option for the selected Position node
  const positionRadarOption = computed<RadarChartOption | null>(() => {
    // selectedNodeRef is read via the closed-over Home.vue binding; we re-derive via
    // graphStore.expandedPositionId since this composable is consumed by Home.vue and
    // it always sets selectedNode before reaching this point.
    const posId = graphStore.expandedPositionId
    if (!posId) return null
    const skills: { name: string; value: number }[] = []
    for (const e of graphStore.allEdges) {
      if (e.source_id === posId && e.type === 'REQUIRES') {
        const skillNode = graphStore.nodeMap.get(e.target_id)
        if (!skillNode) continue
        skills.push({
          name: skillNode.properties.name,
          value: Math.min(e.properties?.weight ?? 0.5, 1),
        })
      }
    }
    if (!skills.length) return null
    const sliced = skills.slice(0, 8)
    return {
      tooltip: { ...(tooltipStyle() as object), trigger: 'item' },
      radar: {
        center: ['50%', '50%'],
        radius: '60%',
        indicator: sliced.map(s => ({ name: s.name, max: 1 })),
        axisName: {
          color: cv('--muted-foreground'),
          fontSize: 10,
          fontFamily:
            "'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Noto Sans SC', sans-serif",
        },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: sliced.map(s => s.value),
              name: '技能权重',
              areaStyle: {
                color: `color-mix(in srgb, ${cv('--primary')} 15%, transparent)`,
              },
              lineStyle: { color: cv('--primary'), width: 2 },
              itemStyle: { color: cv('--primary') },
            },
          ],
        },
      ],
    }
  })

  return {
    graph2DRef,
    graph3DRef,
    evolutionDrawerVisible,
    selectedEvolutionEdge,
    evolutionTrendLabel,
    evolutionTrendType,
    breadcrumb,
    positionRadarOption,
    onOverviewModeChange,
    onCameraPreset,
    onResetCamera,
    onToggleAutoRotate,
    onNodeDblClick,
    resetHighlight,
    toggleEvolution,
    closeDetail,
    handleNodeClick,
    onCanvasClick,
    handleSearchSelect,
    openEvolutionDrawer,
    closeEvolutionDrawer,
  }
}
