import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useResponseValidation } from '@/validation'
// PLAN-014: 契约 schema（后端 Pydantic 导出，脚本生成；供 DEV 响应校验）
import graphSchema from '@contracts/schemas/graph.schema.json'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

/**
 * 全景图谱 store — 三层视图架构
 * 第 1 层: domain — 只显示 KnowledgeArea "岛屿"
 * 第 2 层: position — 点击 KA 展开其下的 Position
 * 第 3 层: detail — 点击 Position 展开其 Skill
 */

// ── 节点类型 ──
export type NodeLabel = 'Position' | 'Skill' | 'Tool' | 'KnowledgeArea' | 'Certificate' | 'LearningResource' | 'Industry' | 'Domain'

// ── 视图层级 ──

/** DRY helper: map raw evolution path API data to internal GraphEdge format */
interface RawEvolutionPath {
  source_position: string
  target_position: string
  similarity?: number
  trend?: 'rising' | 'stable' | 'declining'
  skill_overlap?: string[]
  key_gaps?: string[]
  evidence_count?: number
}

function mapEvolutionPath(p: RawEvolutionPath) {
  return {
    source_id: p.source_position,
    target_id: p.target_position,
    type: 'EVOLVES_TO' as const,
    properties: {
      weight: p.similarity ?? 0.5,
      similarity: p.similarity ?? 0.5,
      trend: (p.trend ?? (p.similarity ?? 0) >= 0.6 ? 'rising' : (p.similarity ?? 0) >= 0.3 ? 'stable' : 'declining') as 'rising' | 'stable' | 'declining',
      skill_overlap: p.skill_overlap ?? [],
      key_gaps: p.key_gaps ?? [],
      evidence_count: p.evidence_count ?? 0,
    },
  }
}
export type ViewLayer = 'domain' | 'position' | 'detail'

// ── 概览视图模式 ──
export type OverviewMode = 'domain' | 'tech_stack' | 'level' | 'heat'

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
 // PLAN-014: DEV 响应结构校验（失败仅 warn，不阻断业务）
  const { validateResponse } = useResponseValidation()

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
 // PLAN-006④: 后端响应时间戳（Unix 秒），前端用来显示"截至 X"诚实时效
  const overviewGeneratedAt = ref<number>(0)

 // ── 概览视图模式 ──
  const overviewMode = ref<OverviewMode>('domain')

 // ── 演化关系边 ──
  const evolutionEdges = ref<GraphEdge[]>([])

 // ── 演化图层状态（ 聚焦当前岗位） ──
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
 // + R4：剔除任一端点不在当前 domains.id 集合的悬空连接，
 // 避免空组（如 lv-junior）残留的 incident 边传入 3d-force-graph 触发 "node not found"。
      const validIds = new Set(domains.value.map(d => d.id))
      return domainConnections.value
        .filter(c => validIds.has(c.source_id) && validIds.has(c.target_id))
        .map(c => ({
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
      const data = validateResponse(
        await request.get(`/graph/overview?group_by=${mode}`) as {
          domains?: DomainOverviewItem[]
          connections?: DomainConnection[]
          independent_positions?: number
          independent_skills?: number
          independent_edges?: number
          generated_at?: number
        },
        graphSchema, '/graph/overview', 'DomainOverviewResponse',
      )
      domains.value = data.domains ?? []
      domainConnections.value = data.connections ?? []
 // 独立节点计数（去重，与 Neo4j 实际节点数一致）
      independentPositions.value = data.independent_positions ?? 0
      independentSkills.value = data.independent_skills ?? 0
      independentEdges.value = data.independent_edges ?? 0
      overviewGeneratedAt.value = data.generated_at ?? 0
      overviewMode.value = mode
 // 切换视图模式 = 重新从顶层导航，必须重置层级状态
 // 否则 expandedKAId/expandedPositionId 指向旧数据，导致图谱混乱
      currentLayer.value = 'domain'
      expandedKAId.value = null
      expandedKAName.value = ''
      expandedPositionId.value = null
      positionsByKA.value = new Map()
 // ponytail: 演化聚焦状态不随模式切换重置会指向旧岗位（演化开关开着时残留）
      focusedPositionId.value = null
      focusedPositionName.value = ''
      evolutionPaths.value = []
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch overview:', e)
      ElMessage.error('加载图谱数据失败，请检查后端服务')
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
      const data = await request.get(`/graph/ka/${kaId}/positions`) as {
        positions?: GraphNode[]
        position_skill_edges?: GraphEdge[]
        skills?: GraphNode[]
      }
      const positions: GraphNode[] = data.positions ?? []
      const psEdges: GraphEdge[] = data.position_skill_edges ?? []
      const skillsData: GraphNode[] = data.skills ?? []
 // 缓存 — fix: 整体替换 Map 以触发 Vue 响应式
      positionsByKA.value = new Map(positionsByKA.value).set(kaId, positions)
 // 合并到全局节点池（O(1) 查重）
      const existingNodeIds = new Set(allNodes.value.map(n => n.id))
      for (const p of positions) {
        if (!existingNodeIds.has(p.id)) {
          existingNodeIds.add(p.id)
          allNodes.value.push(p)
        }
      }
      for (const s of skillsData) {
        if (!existingNodeIds.has(s.id)) {
          existingNodeIds.add(s.id)
          allNodes.value.push(s)
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
      const data = await request.get<RawEvolutionPath[]>('/evolution/paths/all')
      const paths = Array.isArray(data) ? data : []
      evolutionEdges.value = paths.map(mapEvolutionPath)
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Graph] Failed to fetch evolution edges:', e)
      evolutionEdges.value = []
    }
  }

 /**
 *: 获取聚焦岗位的演化路径（仅当前岗位的上下游）。
 * Returns a promise so callers can await before reading evolutionPaths.
 */
  async function fetchEvolutionPathsForPosition(positionName: string) {
    if (!positionName) {
      evolutionPaths.value = []
      return
    }
    evolutionPathsLoading.value = true
    try {
      const data = await request.get<RawEvolutionPath[]>(`/evolution/paths/${encodeURIComponent(positionName)}`)
      const paths = Array.isArray(data) ? data : []
      evolutionPaths.value = paths.map(mapEvolutionPath)
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
 // 清空缓存，防止残留旧 overviewMode 下的分组数据导致回退混乱
    positionsByKA.value = new Map()
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
 // 防御：若 Position 不在当前 KA 下，自动修正 KA 上下文
    if (expandedKAId.value) {
      const positions = positionsByKA.value.get(expandedKAId.value) ?? []
      if (!positions.some(p => p.id === positionId)) {
 // 遍历缓存找到该 Position 所属的 KA
        for (const [kaId, posList] of positionsByKA.value) {
          if (posList.some(p => p.id === positionId)) {
            const kaDomain = domains.value.find(d => d.id === kaId)
            expandedKAId.value = kaId
            expandedKAName.value = kaDomain?.name ?? ''
            break
          }
        }
      }
    }
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
    overviewGeneratedAt,
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
 // 演化图层聚焦（）
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

