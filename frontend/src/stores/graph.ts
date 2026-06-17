import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 全景图谱 store
 * 对应契约：GET /graph/query → 图谱节点与边
 */

// 节点类型
export type NodeLabel = 'Position' | 'Skill' | 'Tool' | 'KnowledgeArea' | 'Certificate' | 'LearningResource' | 'Industry'

// 视图模式
export type ViewMode = 'tech' | 'level' | 'heat' | 'evolution'

export interface GraphNode {
  id: string
  labels: NodeLabel[]
  properties: {
    name: string
    category?: string
    proficiency?: '了解' | '熟悉' | '精通'
    source_count?: number
    trend?: 'rising' | 'stable' | 'declining'
    knowledge_points?: string[]
  }
}

export interface GraphEdge {
  source_id: string
  target_id: string
  type: string
  properties: {
    weight: number
  }
}

export const useGraphStore = defineStore('graph', () => {
  const nodes = ref<GraphNode[]>([])
  const edges = ref<GraphEdge[]>([])
  const viewMode = ref<ViewMode>('tech')
  const loading = ref(false)

  async function fetchGraph() {
    loading.value = true
    try {
      const resp = await fetch('/api/v1/graph/query')
      const data = await resp.json()
      nodes.value = data.nodes ?? []
      edges.value = data.edges ?? []
    } finally {
      loading.value = false
    }
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
  }

  return { nodes, edges, viewMode, loading, fetchGraph, setViewMode }
})
