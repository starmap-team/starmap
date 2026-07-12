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
export type NodeLabel = 'Position' | 'Skill' | 'Tool' | 'KnowledgeArea' | 'Certificate' | 'LearningResource' | 'Industry' | 'Domain'

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
    trend?: 'rising' | 'stable' | 'declining'
    skill_overlap?: string[]
    key_gaps?: string[]
    similarity?: number
    evidence_count?: number
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

  // ── 独立节点计数（来自后端 /graph/overview 的独立统计，避免重复计数） ──
  const independentPositions = ref<number>(0)
  const independentSkills = ref<number>(0)
  const independentEdges = ref<number>(0)

  // ── 概览视图模式 ──
  const overviewMode = ref<OverviewMode>('domain')

  // ── 演化关系边 ──
  const evolutionEdges = ref<GraphEdge[]>([])

  // ── 演化图层状态（D-02 聚焦当前岗位） ──
  const focusedPositionId = ref<string | null>(null)
  const focusedPositionName = ref<string>('')
  const evolutionPaths = ref<GraphEdge[]>([])
  const evolutionPathsLoading = ref(false)

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
    loading.value = true
    try {
      const data = await request.get(`/graph/overview?group_by=${mode}`) as {
        domains?: DomainOverviewItem[]
        connections?: DomainConnection[]
        independent_positions?: number
        independent_skills?: number
        independent_edges?: number
      }
      domains.value = data.domains ?? []
      domainConnections.value = data.connections ?? []
      // 独立节点计数（去重，与 Neo4j 实际节点数一致）
      independentPositions.value = data.independent_positions ?? 0
      independentSkills.value = data.independent_skills ?? 0
      independentEdges.value = data.independent_edges ?? 0
      // 延迟设置 overviewMode 直到数据就绪，避免 Graph3D watch 被触发两次：
      // 1) overviewMode 变了但 nodes/links 还是旧数据（力配置错配）
      // 2) API 返回后 nodes/links 更新（再次触发）
      // Vue 的批处理会在同一微任务中合并 domains/domainConnections/overviewMode 的更新，
      // 确保 computed 属性只触发一次 watch
      overviewMode.value = mode
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch overview:', e)
      domains.value = []
      domainConnections.value = []
      independentPositions.value = 0
      independentSkills.value = 0
      independentEdges.value = 0
    } finally {
      loading.value = false
    }
  }

  /** 第 2 层：获取 KA 下的 Position */
  async function fetchKAPositions(kaId: string) {
    loading.value = true
    try {
      const edgeKeys = new Set(allEdges.value.map(x => `${x.source_id}-${x.target_id}-${x.type}`))
      const data = await request.get(`/graph/ka/${kaId}/positions`) as { positions?: GraphNode[]; position_skill_edges?: GraphEdge[] }
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
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch KA positions:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  /** 加载演化关系边（含趋势、技能重叠、差距等详情） */
  async function fetchEvolutionEdges() {
    try {
      const data = await request.get('/evolution/paths/all') as unknown as Array<{ source_position: string; target_position: string; similarity?: number; trend?: 'rising' | 'stable' | 'declining'; skill_overlap?: string[]; key_gaps?: string[]; evidence_count?: number }>
      const paths = Array.isArray(data) ? data : []
      evolutionEdges.value = paths.map((p: { source_position: string; target_position: string; similarity?: number; trend?: 'rising' | 'stable' | 'declining'; skill_overlap?: string[]; key_gaps?: string[]; evidence_count?: number }) => ({
        source_id: p.source_position,
        target_id: p.target_position,
        type: 'EVOLVES_TO',
        properties: {
          weight: p.similarity ?? 0.5,
          similarity: p.similarity ?? 0.5,
          trend: (p.trend ?? (p.similarity ?? 0) >= 0.6 ? 'rising' : (p.similarity ?? 0) >= 0.3 ? 'stable' : 'declining') as 'rising' | 'stable' | 'declining',
          skill_overlap: p.skill_overlap ?? [],
          key_gaps: p.key_gaps ?? [],
          evidence_count: p.evidence_count ?? 0,
        },
      }))
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch evolution edges:', e)
      evolutionEdges.value = []
    }
  }

  /**
   * D-02: 获取聚焦岗位的演化路径（仅当前岗位的上下游）。
   * Returns a promise so callers can await before reading evolutionPaths.
   */
  async function fetchEvolutionPathsForPosition(positionName: string) {
    if (!positionName) {
      evolutionPaths.value = []
      return
    }
    evolutionPathsLoading.value = true
    try {
      const data = await request.get(`/evolution/paths/${encodeURIComponent(positionName)}`) as unknown as Array<{ source_position: string; target_position: string; similarity?: number; trend?: 'rising' | 'stable' | 'declining'; skill_overlap?: string[]; key_gaps?: string[]; evidence_count?: number }>
      const paths = Array.isArray(data) ? data : []
      evolutionPaths.value = paths.map((p: { source_position: string; target_position: string; similarity?: number; trend?: 'rising' | 'stable' | 'declining'; skill_overlap?: string[]; key_gaps?: string[]; evidence_count?: number }) => ({
        source_id: p.source_position,
        target_id: p.target_position,
        type: 'EVOLVES_TO',
        properties: {
          weight: p.similarity ?? 0.5,
          similarity: p.similarity ?? 0.5,
          trend: (p.trend ?? (p.similarity ?? 0) >= 0.6 ? 'rising' : (p.similarity ?? 0) >= 0.3 ? 'stable' : 'declining') as 'rising' | 'stable' | 'declining',
          skill_overlap: p.skill_overlap ?? [],
          key_gaps: p.key_gaps ?? [],
          evidence_count: p.evidence_count ?? 0,
        },
      }))
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch evolution paths for position:', e)
      evolutionPaths.value = []
    } finally {
      evolutionPathsLoading.value = false
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
    // 独立节点计数
    independentPositions,
    independentSkills,
    independentEdges,
    // API
    fetchOverview,
    fetchKAPositions,
    // 概览视图模式
    overviewMode,
    // 演化
    evolutionEdges,
    fetchEvolutionEdges,
    // 演化图层聚焦（D-02）
    focusedPositionId,
    focusedPositionName,
    evolutionPaths,
    evolutionPathsLoading,
    fetchEvolutionPathsForPosition,
    // 导航
    goToDomainLayer,
    goToPositionLayer,
    goToDetailLayer,
  }
})


