/**
 * Graph node management store — extracted from datasource.ts (Phase 7 admin domain split).
 * Manages Neo4j graph node CRUD for admin panel.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import type { GraphNodeItem } from '@/composables/useGraphNodeList'

import { useResponseValidation } from '@/validation/useResponseValidation'
import adminSchema from '../../../starmap-contracts/schemas/admin.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateAdmin } = useResponseValidation()

interface AdminGraphNodesResponse {
  items: GraphNodeItem[]
}

export const useGraphNodeStore = defineStore('graphNode', () => {
  const graphNodes = ref<GraphNodeItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchGraphNodes(
    offset: number = 0,
    limit: number = 20,
    search: string = '',
    nodeType: string = '',
  ) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (offset > 0) params.append('offset', String(offset))
      if (limit !== 20) params.append('limit', String(limit))
      if (search) params.append('search', search)
      if (nodeType) params.append('node_type', nodeType)

      const queryString = params.toString()
      const url = queryString ? `/admin/graph/nodes?${queryString}` : '/admin/graph/nodes'

      const data = validateAdmin(
        await request.get(url) as AdminGraphNodesResponse,
        adminSchema, url, 'GraphNodeListResponse',
      ) as AdminGraphNodesResponse
      graphNodes.value = data.items ?? []
      return data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取图谱节点失败'
      error.value = msg
      if (import.meta.env.DEV) console.error('[GraphNode] fetchGraphNodes failed:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createGraphNode(payload: Record<string, unknown>) {
    await request.post('/admin/graph/nodes', payload)
    await fetchGraphNodes()
  }

  async function updateGraphNode(id: string, payload: Record<string, unknown>) {
    await request.put(`/admin/graph/nodes/${id}`, payload)
    await fetchGraphNodes()
  }

  async function deleteGraphNode(id: string) {
    await request.delete(`/admin/graph/nodes/${id}`)
    await fetchGraphNodes()
  }

  async function approveGraphNode(id: string) {
    await request.post(`/admin/graph/nodes/${id}/approve`)
    await fetchGraphNodes()
  }

  async function rejectGraphNode(id: string) {
    await request.post(`/admin/graph/nodes/${id}/reject`)
    await fetchGraphNodes()
  }

  return {
    graphNodes,
    loading,
    error,
    fetchGraphNodes,
    createGraphNode,
    updateGraphNode,
    deleteGraphNode,
    approveGraphNode,
    rejectGraphNode,
  }
})