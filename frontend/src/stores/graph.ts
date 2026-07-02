import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'

/**
 * 全景图谱 store — 三层视图架构
 * 第 1 层: domain  — 只显示 KnowledgeArea "岛屿"
 * 第 2 层: position — 点击 KA 展开其下的 Position
 * 第 3 层: detail   — 点击 Position 展开其 Skill
 */

// ── 节点类型 ──
export type NodeLabel = 'Position' | 'Skill' | 'Tool' | 'KnowledgeArea' | 'Certificate' | 'LearningResource' | 'Industry'

// ── 视图层级 ──
export type ViewLayer = 'domain' | 'position' | 'detail'

// ── 概览视图模式 ──
export type OverviewMode = 'domain' | 'tech_stack' | 'level'

export interface GraphNode {
  id: string
  labels: NodeLabel[]
  properties: {
    name: string
    category?: string
    proficiency?: string
    source_count?: number
    trend?: 'rising' | 'stable' | 'declining'
    knowledge_points?: string[]
    level?: string
    weight?: number
    position_count?: number
    skill_count?: number
    color?: string
  }
}

export interface GraphEdge {
  source_id: string
  target_id: string
  type: string
  properties: {
    weight: number
    required?: boolean
  }
}

// ── 领域概览数据（来自 /graph/overview） ──
export interface DomainOverviewItem {
  id: string
  name: string
  position_count: number
  skill_count: number
  color: string
}

export interface DomainConnection {
  source_id: string
  target_id: string
  type: string
  properties: { weight: number }
}

export const useGraphStore = defineStore('graph', () => {
  // ── 原始数据 ──
  const allNodes = ref<GraphNode[]>([])
  const allEdges = ref<GraphEdge[]>([])
  const loading = ref(false)

  // ── 三层导航状态 ──
  const currentLayer = ref<ViewLayer>('domain')
  const expandedKAId = ref<string | null>(null)
  const expandedKAName = ref<string>( '')
  const expandedPositionId = ref<string | null>(null)

  // ── 领域概览数据 ──
  const domains = ref<DomainOverviewItem[]>([])
  const domainConnections = ref<DomainConnection[]>([])

  // ── 概览视图模式 ──
  const overviewMode = ref<OverviewMode>('domain')

  // ── 演化关系边 ──
  const evolutionEdges = ref<GraphEdge[]>([])

  // ── KA 下的 Position 缓存 ──
  const positionsByKA = ref<Map<string, GraphNode[]>>(new Map())

  // ── 节点/边索引（O(1) 查找） ──
  const nodeMap = computed(() => {
    const map = new Map<string, GraphNode>()
    for (const n of allNodes.value) map.set(n.id, n)
    return map
  })

  // ── 当前可见节点 & 边（根据层级） ──
  const visibleNodes = computed(() => {
    if (currentLayer.value === 'domain') {
      return domains.value.map(d => ({
        id: d.id,
        labels: ['KnowledgeArea' as NodeLabel],
        properties: { name: d.name, position_count: d.position_count, skill_count: d.skill_count, color: d.color },
      }))
    }
    if (currentLayer.value === 'position' && expandedKAId.value) {
      const positions = positionsByKA.value.get(expandedKAId.value) ?? []
      // KA 节点 + 下属 Position
      const kaNode: GraphNode = {
        id: expandedKAId.value,
        labels: ['KnowledgeArea' as NodeLabel],
        properties: { name: expandedKAName.value, color: domains.value.find(d => d.id === expandedKAId.value)?.color },
      }
      return [kaNode, ...positions]
    }
    if (currentLayer.value === 'detail' && expandedPositionId.value) {
      const posNode = nodeMap.value.get(expandedPositionId.value)
      if (!posNode) return []
      // 找到该 Position 所属的 KA
      const kaNode = expandedKAId.value
        ? [{
            id: expandedKAId.value,
            labels: ['KnowledgeArea' as NodeLabel],
            properties: { name: expandedKAName.value, color: domains.value.find(d => d.id === expandedKAId.value)?.color },
          }]
        : []
      // 找到该 Position 的 Skill
      const skillIds = new Set<string>()
      const skills: GraphNode[] = []
      for (const e of allEdges.value) {
        if (e.source_id === expandedPositionId.value && e.type === 'REQUIRES') {
          const skill = nodeMap.value.get(e.target_id)
          if (skill) { skillIds.add(e.target_id); skills.push(skill) }
        }
      }
      return [...kaNode, posNode, ...skills]
    }
    return []
  })

  const visibleEdges = computed(() => {
    if (currentLayer.value === 'domain') {
      return domainConnections.value.map(c => ({
        source_id: c.source_id,
        target_id: c.target_id,
        type: c.type,
        properties: c.properties,
      }))
    }
    if (currentLayer.value === 'position' && expandedKAId.value) {
      // 显示 KA → Position 关联边（虚拟边，通过 BELONGS_TO 推导）
      const positions = positionsByKA.value.get(expandedKAId.value) ?? []
      return positions.map(p => ({
        source_id: expandedKAId.value!,
        target_id: p.id,
        type: 'CONTAINS',
        properties: { weight: 1 },
      }))
    }
    if (currentLayer.value === 'detail' && expandedPositionId.value) {
      // 显示 Position → Skill 的 REQUIRES 边
      return allEdges.value.filter(e =>
        e.source_id === expandedPositionId.value && e.type === 'REQUIRES',
      )
    }
    return []
  })

  // ── API 调用 ──

  /** 第 1 层：获取领域概览 */
  async function fetchOverview(mode: OverviewMode = 'domain') {
    overviewMode.value = mode
    loading.value = true
    try {
      const data = await request.get(`/graph/overview?group_by=${mode}`) as any
      domains.value = data.domains ?? []
      domainConnections.value = data.connections ?? []
    } catch (e) {
      console.error('[Graph] Failed to fetch overview:', e)
      domains.value = []
      domainConnections.value = []
    } finally {
      loading.value = false
    }
  }

  /** 第 2 层：获取 KA 下的 Position */
  async function fetchKAPositions(kaId: string) {
    loading.value = true
    try {
      const edgeKeys = new Set(allEdges.value.map(x => `${x.source_id}-${x.target_id}-${x.type}`))
      const data = await request.get(`/graph/ka/${kaId}/positions`) as any
      const positions: GraphNode[] = data.positions ?? []
      const psEdges: GraphEdge[] = data.position_skill_edges ?? []
      // 缓存
      positionsByKA.value.set(kaId, positions)
      // 合并到全局节点池（O(1) 查重）
      const existingNodeIds = new Set(allNodes.value.map(n => n.id))
      for (const p of positions) {
        if (!existingNodeIds.has(p.id)) {
          existingNodeIds.add(p.id)
          allNodes.value.push(p)
        }
      }
      for (const e of psEdges) {
        const key = `${e.source_id}-${e.target_id}-${e.type}`
        if (!edgeKeys.has(key)) {
          edgeKeys.add(key)
          allEdges.value.push(e)
        }
      }
      return positions
    } catch (e) {
      console.error('[Graph] Failed to fetch KA positions:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  /** 加载演化关系边 */
  async function fetchEvolutionEdges() {
    try {
      const data = await request.get('/evolution/paths/all') as any
      evolutionEdges.value = Array.isArray(data) ? data.map((p: any) => ({ source_id: p.source_position, target_id: p.target_position, type: 'EVOLVES_TO', properties: { weight: p.similarity ?? 0.5 } })) : []
    } catch (e) {
      console.error('[Graph] Failed to fetch evolution edges:', e)
      evolutionEdges.value = []
    }
  }

  // ── 导航 ──

  function goToDomainLayer() {
    currentLayer.value = 'domain'
    expandedKAId.value = null
    expandedKAName.value = ''
    expandedPositionId.value = null
  }

  async function goToPositionLayer(kaId: string, kaName: string) {
    expandedKAId.value = kaId
    expandedKAName.value = kaName
    expandedPositionId.value = null
    currentLayer.value = 'position'
    // 如果缓存中没有，先加载
    if (!positionsByKA.value.has(kaId)) {
      await fetchKAPositions(kaId)
    }
  }

  function goToDetailLayer(positionId: string) {
    expandedPositionId.value = positionId
    currentLayer.value = 'detail'
  }

  return {
    // 数据
    allNodes,
    allEdges,
    domains,
    domainConnections,
    positionsByKA,
    nodeMap,
    // 层级状态
    currentLayer,
    expandedKAId,
    expandedKAName,
    expandedPositionId,
    // 计算
    visibleNodes,
    visibleEdges,
    // 加载
    loading,
    // API
    fetchOverview,
    fetchKAPositions,
    // 概览视图模式
    overviewMode,
    // 演化
    evolutionEdges,
    fetchEvolutionEdges,
    // 导航
    goToDomainLayer,
    goToPositionLayer,
    goToDetailLayer,
  }
})


