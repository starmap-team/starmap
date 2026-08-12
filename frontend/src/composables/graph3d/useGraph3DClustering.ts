/**
 * useGraph3DClustering — overflow-based node grouping for 3D graphs
 *
 * 镜像 useGraphClustering.ts (graph2d) 但输出 3d-force-graph 兼容节点 schema:
 *   { id, labels, color, position_count, properties }
 *
 * 节点数 > effectiveLimit * clusterThreshold 时,超出部分折叠为 1 个 cluster
 * meta-node (id='cluster-overflow', color='#999999', properties.name='{N} more nodes')。
 *
 * 2026-08-13: Phase 1 (M1 全景图谱) Plan 01-03 Task 2 — 镜像 2D useGraphClustering
 * 但 3D 暂不实现"点击展开 cluster"(避免引入 watch + _destructor 重建复杂度;沿
 * Phase 13 R3 防御路径)。后续 phase 增强。
 */
import { computed, type Ref } from 'vue'

export interface GraphNode3D {
  id: string
  labels?: string[]
  color?: string
  position_count?: number
  properties?: Record<string, unknown>
}

export interface GraphNode3DCluster extends GraphNode3D {
  id: 'cluster-overflow'  // 固定 ID
  labels: ['Cluster']
  color: '#999999'
  position_count: number
  properties: { name: string; children_ids: string[] }
}

/**
 * clusterNodes3D — 纯函数:输入 nodes + effectiveLimit + clusterThreshold,
 * 输出 { visible, cluster } (cluster 为 null 表示不折叠)。
 */
export function clusterNodes3D(
  nodes: GraphNode3D[],
  effectiveLimit: number = 30,
  clusterThreshold: number = 0.8,
): { visible: GraphNode3D[]; cluster: GraphNode3DCluster | null } {
  // 按 position_count 降序排序,top effectiveLimit 保留
  const sorted = [...nodes].sort((a, b) => (b.position_count ?? 0) - (a.position_count ?? 0))
  const shouldCluster = nodes.length > effectiveLimit * clusterThreshold
  if (!shouldCluster) return { visible: nodes, cluster: null }
  const visible = sorted.slice(0, effectiveLimit)
  const overflow = sorted.slice(effectiveLimit)
  const cluster: GraphNode3DCluster = {
    id: 'cluster-overflow',
    labels: ['Cluster'],
    color: '#999999',
    position_count: overflow.reduce((s, n) => s + (n.position_count ?? 0), 0),
    properties: {
      name: `${overflow.length} more nodes`,
      children_ids: overflow.map((n) => n.id),
    },
  }
  return { visible: [...visible, cluster], cluster }
}

/**
 * Vue composable wrapper: 接收 Ref<nodes> + effectiveLimit,返回 computed { visible, cluster }。
 */
export function useGraph3DClustering(nodes: Ref<GraphNode3D[]>, effectiveLimit = 30) {
  return computed(() => clusterNodes3D(nodes.value, effectiveLimit))
}