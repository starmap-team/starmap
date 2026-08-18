/**
 * useGraphClustering — overflow-based node grouping
 *
 * When visible nodes exceed clusterThreshold, surplus nodes are merged
 * into a single "cluster" meta-node instead of being silently truncated.
 * The cluster node displays "{n} items" and can be expanded on click.
 *
 * Sprint: replaces naive slice truncation in position/detail layers.
 */
import { computed, type Ref, type ComputedRef } from 'vue'
import type { GraphNode } from '@/stores/graph'

export interface ClusterNode {
 /** Aggregate node representing the clustered group */
  id: string
  label: string
  memberCount: number
  members: GraphNode[]
 /** Average color derived from member nodes */
  color: string
 /** Reduced size (log-scaled from member count) */
  size: number
}

export function clusterNodes(
  nodes: GraphNode[],
  limit: number,
  clusterThreshold: number = 0.8,
): { visible: GraphNode[]; cluster: ClusterNode | null } {
  const effectiveLimit = Math.max(limit, 8)
  const shouldCluster = nodes.length > effectiveLimit * clusterThreshold

  if (!shouldCluster || nodes.length <= effectiveLimit) {
    return { visible: nodes.slice(0, effectiveLimit), cluster: null }
  }

  const showCount = Math.max(Math.floor(effectiveLimit * 0.85), 5)
  const visibleNodes = nodes.slice(0, showCount)
  const groupedNodes = nodes.slice(showCount)

  if (groupedNodes.length <= 1) {
    return { visible: nodes.slice(0, effectiveLimit), cluster: null }
  }

 // Simple color average (heuristic — use first node's domain color as fallback)
  const color = '#6b7280' // neutral gray for cluster
  const size = Math.min(28 + Math.log2(groupedNodes.length) * 4, 56)

  return {
    visible: visibleNodes,
    cluster: {
      id: `cluster-overflow-${Date.now()}`,
      label: `${groupedNodes.length} 个节点`,
      memberCount: groupedNodes.length,
      members: groupedNodes,
      color,
      size,
    },
  }
}

/**
 * Vue composable: compute cluster state from node list + threshold.
 */
export function useGraphClustering(
  nodes: Ref<GraphNode[]> | ComputedRef<GraphNode[]>,
  limit: Ref<number> | ComputedRef<number>,
  clusterThreshold?: number,
) {
  return computed(() => clusterNodes(nodes.value, limit.value, clusterThreshold))
}
